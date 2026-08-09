# core/runtime.py

from copy import deepcopy
from dataclasses import dataclass, field
import threading
import time

import core.context as ctx
import core.state as legacy_state

from core.config import DEFAULT_CONFIG, config as legacy_config, save_config
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
    """Laufzeit-Abhängigkeiten eines einzelnen Zeltes."""

    tent_id: str
    name: str
    state: object
    config: dict
    state_lock: object
    energy_state: dict = field(default_factory=dict)
    energy_lock: object = field(default_factory=threading.RLock)
    enabled: bool = True
    shadow_enabled: bool = False
    control_enabled: bool = False
    controller_id: str = "local"

    # Phase 3B: Shadow-Ausgänge werden bewusst getrennt vom realen
    # Gerätezustand gespeichert. Ein Shadow-Loop darf dadurch Entscheidungen
    # berechnen, ohne den tatsächlichen State eines Shelly-Relais vorzutäuschen.
    shadow_outputs: dict = field(default_factory=dict)
    loop_mode: str = "inactive"
    last_loop_ts: object = None

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
    controller_id="local",
):
    """Erzeugt einen vollständig getrennten State/Config/Lock-Kontext."""

    tent_id = validate_tent_id(tent_id)

    cfg = deepcopy(DEFAULT_CONFIG)
    if config_data:
        cfg.update(deepcopy(config_data))

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
        controller_id=controller_id or "local",
        _save_config_callback=save_config_callback,
    )


def _save_callback_for(tent_id):
    return lambda cfg: save_tent_config(tent_id, cfg)


def init_runtimes():
    """Lädt alle aktivierten Zelte als getrennte Runtimes in den Prozess.

    Phase 3B erlaubt für zusätzliche Zelte ausschließlich Shadow-Control.
    Selbst wenn ``tents.json`` versehentlich/manuell ``control_enabled=true``
    enthält, wird die Runtime hier noch hart auf ``False`` gesetzt. Erst eine
    spätere, ausdrücklich getestete Phase darf diese Sicherheitsbarriere
    entfernen.
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
        if requested_control:
            print(
                f"🚫 [{tent_id}] Hardware-Control angefordert, "
                "aber in Phase 3B weiterhin gesperrt"
            )

        runtime = create_isolated_runtime(
            tent_id,
            name=tent.get("name") or tent_id,
            config_data=cfg,
            save_config_callback=_save_callback_for(tent_id),
            enabled=True,
            shadow_enabled=bool(tent.get("shadow_enabled", False)),
            # Harte Phase-3B-Sicherheitsbarriere:
            control_enabled=False,
            controller_id=tent.get("controller_id") or "local",
        )
        register_runtime(runtime, replace=True)
        loaded_ids.add(tent_id)

        mode = "Shadow bereit" if runtime.shadow_enabled else "inaktiv"
        print(
            f"🧩 [{tent_id}] Runtime geladen "
            f"({mode}; Hardware-Control gesperrt)"
        )

    # Runtimes entfernen, deren Zelt aus tents.json verschwunden/disabled ist.
    with _registry_lock:
        for tent_id in list(_runtimes):
            if tent_id not in loaded_ids and tent_id != DEFAULT_TENT_ID:
                _runtimes.pop(tent_id, None)

    return list_runtimes()
