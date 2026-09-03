# core/runtime.py

from copy import deepcopy
from dataclasses import dataclass, field
import threading
import time

import core.context as ctx
import core.state as legacy_state

from core.config import (
    DEFAULT_CONFIG,
    config as legacy_config,
    migrate_vpd_phase_config,
    save_config,
)
from core.tent_config import (
    ensure_tent_config,
    load_tent_config,
    save_tent_config,
)
from core.tents import (
    DEFAULT_TENT_ID,
    DEFAULT_TENT_NAME,
    manager as tent_manager,
    validate_tent_id,
)


@dataclass
class TentRuntime:
    """Laufzeit-Abhängigkeiten einer einzelnen lokalen Grow-Station."""

    tent_id: str
    name: str
    state: object
    config: dict
    state_lock: object
    energy_state: dict = field(default_factory=dict)
    energy_lock: object = field(default_factory=threading.RLock)
    enabled: bool = True
    shadow_enabled: bool = False

    # ``control_enabled`` is the ACTUAL in-process hardware gate.  For an
    # additional persisted LIVE station it always starts False after boot and
    # is opened only by the Phase-4H preflight/arming service.
    control_enabled: bool = False
    live_requested: bool = False
    arming: bool = False
    # Transient guard during a controlled LIVE -> SHADOW transition.
    # While true, normal controller/failsafe writes are blocked so they cannot
    # race against the explicit relay-off verification.
    disarming: bool = False
    last_live_preflight: object = None

    controller_id: str = "local"

    # Shadow outputs stay separate from real relay state.
    shadow_outputs: dict = field(default_factory=dict)
    loop_mode: str = "inactive"
    last_loop_ts: object = None

    # Phase 4I: stationsbezogener Safety-Supervisor. Overrides gelten nur
    # in-process und werden nach jedem Neustart frisch aus Runtime-State,
    # Sensor-Freshness und zentralem Aktor-Health-Cache berechnet.
    safety_overrides: dict = field(default_factory=dict)
    safety_status: object = None
    last_safety_ts: object = None
    safety_lock: object = field(default_factory=threading.RLock)

    _save_config_callback: object = None

    def persist_config(self):
        """Speichert ausschließlich die Config dieser Runtime."""
        if self._save_config_callback is None:
            return False
        self._save_config_callback(self.config)
        return True

    def mark_loop(self, mode):
        self.loop_mode = mode
        self.last_loop_ts = time.time()


_registry_lock = threading.RLock()
_runtimes = {}


def _tent_meta(tent_id):
    tent = tent_manager.get(tent_id) or {}
    return {
        "name": tent.get("name") or (
            DEFAULT_TENT_NAME if tent_id == DEFAULT_TENT_ID else tent_id
        ),
        "enabled": bool(tent.get("enabled", True)),
        "shadow_enabled": bool(tent.get("shadow_enabled", False)),
        "control_enabled": bool(
            tent.get("control_enabled", tent_id == DEFAULT_TENT_ID)
        ),
        "controller_id": tent.get("controller_id") or "local",
    }


def _build_default_runtime():
    meta = _tent_meta(DEFAULT_TENT_ID)
    return TentRuntime(
        tent_id=DEFAULT_TENT_ID,
        name=meta["name"],
        state=legacy_state,
        config=legacy_config,
        state_lock=ctx.state_lock,
        energy_state=ctx.energy_state,
        energy_lock=ctx.energy_lock,
        enabled=True,
        shadow_enabled=False,
        control_enabled=True,
        live_requested=True,
        arming=False,
        controller_id=meta["controller_id"],
        _save_config_callback=save_config,
    )


def get_default_runtime():
    with _registry_lock:
        runtime = _runtimes.get(DEFAULT_TENT_ID)
        meta = _tent_meta(DEFAULT_TENT_ID)

        if runtime is None:
            runtime = _build_default_runtime()
            _runtimes[DEFAULT_TENT_ID] = runtime
        else:
            runtime.name = meta["name"]
            runtime.enabled = True
            runtime.shadow_enabled = False
            runtime.control_enabled = True
            runtime.live_requested = True
            runtime.arming = False
            runtime.controller_id = meta["controller_id"]

        return runtime


def register_runtime(runtime, replace=False):
    if not isinstance(runtime, TentRuntime):
        raise TypeError("runtime muss eine TentRuntime-Instanz sein")

    runtime.tent_id = validate_tent_id(runtime.tent_id)

    with _registry_lock:
        if runtime.tent_id in _runtimes and not replace:
            raise ValueError(
                f"Runtime für {runtime.tent_id} ist bereits registriert"
            )
        _runtimes[runtime.tent_id] = runtime
        return runtime


def unregister_runtime(tent_id):
    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError("Die Default-Runtime kann nicht entfernt werden")

    with _registry_lock:
        return _runtimes.pop(tent_id, None)


def get_runtime(tent_id=DEFAULT_TENT_ID):
    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        return get_default_runtime()

    with _registry_lock:
        runtime = _runtimes.get(tent_id)

    if runtime is None:
        raise KeyError(f"Keine Runtime für Zelt '{tent_id}' registriert")

    return runtime


def list_runtimes():
    with _registry_lock:
        return list(_runtimes.values())


def resolve_runtime(runtime=None):
    """Akzeptiert None, eine Tent-ID oder eine TentRuntime."""
    if runtime is None:
        return get_default_runtime()
    if isinstance(runtime, str):
        return get_runtime(runtime)
    if not isinstance(runtime, TentRuntime):
        raise TypeError("Ungültiger Runtime-Kontext")
    return runtime


def create_isolated_runtime(
    tent_id,
    *,
    name=None,
    config_data=None,
    save_config_callback=None,
    enabled=True,
    shadow_enabled=False,
    control_enabled=False,
    live_requested=False,
    controller_id="local",
):
    """Erzeugt einen vollständig getrennten State/Config/Lock-Kontext."""

    tent_id = validate_tent_id(tent_id)

    # Additional runtimes may inherit general control defaults, but NEVER
    # hardware endpoints from the legacy/default config. Explicit IP_/RELAY_
    # values from this station's own config_data are applied afterwards.
    cfg = deepcopy(DEFAULT_CONFIG)
    for key in list(cfg):
        if key.startswith("IP_") or key.startswith("RELAY_"):
            cfg.pop(key, None)

    if config_data:
        loaded_config = deepcopy(config_data)
        migrate_vpd_phase_config(loaded_config)
        cfg.update(loaded_config)

    return TentRuntime(
        tent_id=tent_id,
        name=name or _tent_meta(tent_id)["name"],
        state=legacy_state.create_runtime_state(),
        config=cfg,
        state_lock=threading.RLock(),
        energy_state={},
        energy_lock=threading.RLock(),
        enabled=bool(enabled),
        shadow_enabled=bool(shadow_enabled),
        control_enabled=bool(control_enabled),
        live_requested=bool(live_requested),
        arming=bool(live_requested and not control_enabled),
        controller_id=controller_id or "local",
        _save_config_callback=save_config_callback,
    )


def _save_callback_for(tent_id):
    return lambda cfg: save_tent_config(tent_id, cfg)


def init_runtimes():
    """Lädt alle aktivierten lokalen Stationen.

    Additional stations persisted as LIVE are intentionally NOT granted
    hardware access while loading.  They start with ``control_enabled=False``
    and ``live_requested=True``.  Phase 4H's arming service opens the gate only
    after the runtime heartbeat, required sensors and assigned actuator health
    are all green again.  This prevents blind hardware actuation after reboot.
    """

    loaded_ids = {DEFAULT_TENT_ID}
    get_default_runtime()

    for tent in tent_manager.list_tents():
        tent_id = validate_tent_id(tent.get("id"))
        if tent_id == DEFAULT_TENT_ID:
            continue

        if not tent.get("enabled", True):
            with _registry_lock:
                _runtimes.pop(tent_id, None)
            continue

        ensure_tent_config(tent_id)
        cfg = load_tent_config(tent_id)
        requested_control = bool(tent.get("control_enabled", False))

        runtime = create_isolated_runtime(
            tent_id,
            name=tent.get("name") or tent_id,
            config_data=cfg,
            save_config_callback=_save_callback_for(tent_id),
            enabled=True,
            # A persisted LIVE station runs safely in ARMING until its gate is
            # reopened.  A normal shadow station keeps shadow_enabled=True.
            shadow_enabled=bool(tent.get("shadow_enabled", False)) and not requested_control,
            control_enabled=False,
            live_requested=requested_control,
            controller_id=tent.get("controller_id") or "local",
        )
        register_runtime(runtime, replace=True)
        loaded_ids.add(tent_id)

        if requested_control:
            mode = "ARMING; Hardware-Control noch gesperrt"
        elif runtime.shadow_enabled:
            mode = "Shadow bereit; Hardware-Control gesperrt"
        else:
            mode = "inaktiv"

        print(f"🧩 [{tent_id}] Runtime geladen ({mode})")

    with _registry_lock:
        for tent_id in list(_runtimes):
            if tent_id not in loaded_ids and tent_id != DEFAULT_TENT_ID:
                _runtimes.pop(tent_id, None)

    return list_runtimes()
