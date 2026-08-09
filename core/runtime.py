# core/runtime.py

from copy import deepcopy
from dataclasses import dataclass, field
import threading

import core.context as ctx
import core.state as legacy_state

from core.config import DEFAULT_CONFIG, config as legacy_config, save_config
from core.tents import (
    DEFAULT_TENT_ID,
    DEFAULT_TENT_NAME,
    manager as tent_manager,
)


@dataclass
class TentRuntime:
    """Laufzeit-Abhängigkeiten eines einzelnen Zeltes.

    Phase 2 verwendet für ``tent_1`` weiterhin die bestehenden globalen
    State-/Config-Objekte. Die Regelmodule bekommen sie nun aber über diesen
    Kontext übergeben. Dadurch können spätere Zelte eigene State-, Config-
    und Lock-Instanzen erhalten, ohne die Regelalgorithmen erneut umzubauen.
    """

    tent_id: str
    name: str
    state: object
    config: dict
    state_lock: object
    energy_state: dict = field(default_factory=dict)
    energy_lock: object = field(default_factory=threading.RLock)
    _save_config_callback: object = None

    def persist_config(self):
        """Speichert die Runtime-Konfiguration, sofern ein Store hinterlegt ist."""

        if self._save_config_callback is None:
            return False

        self._save_config_callback(self.config)
        return True


_registry_lock = threading.RLock()
_runtimes = {}


def _tent_name(tent_id):
    tent = tent_manager.get(tent_id) or {}
    return tent.get("name") or (
        DEFAULT_TENT_NAME if tent_id == DEFAULT_TENT_ID else tent_id
    )


def _build_default_runtime():
    return TentRuntime(
        tent_id=DEFAULT_TENT_ID,
        name=_tent_name(DEFAULT_TENT_ID),
        state=legacy_state,
        config=legacy_config,
        state_lock=ctx.state_lock,
        energy_state=ctx.energy_state,
        energy_lock=ctx.energy_lock,
        _save_config_callback=save_config,
    )


def get_default_runtime():
    with _registry_lock:
        runtime = _runtimes.get(DEFAULT_TENT_ID)
        if runtime is None:
            runtime = _build_default_runtime()
            _runtimes[DEFAULT_TENT_ID] = runtime
        else:
            # tents.json wird erst beim App-Start initialisiert. Den Namen
            # danach noch einmal aktualisieren, ohne die Runtime zu ersetzen.
            runtime.name = _tent_name(DEFAULT_TENT_ID)
        return runtime


def register_runtime(runtime, replace=False):
    if not isinstance(runtime, TentRuntime):
        raise TypeError("runtime muss eine TentRuntime-Instanz sein")

    if not runtime.tent_id:
        raise ValueError("tent_id darf nicht leer sein")

    with _registry_lock:
        if runtime.tent_id in _runtimes and not replace:
            raise ValueError(
                f"Runtime für {runtime.tent_id} ist bereits registriert"
            )
        _runtimes[runtime.tent_id] = runtime
        return runtime


def unregister_runtime(tent_id):
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError("Die Default-Runtime kann nicht entfernt werden")

    with _registry_lock:
        return _runtimes.pop(tent_id, None)


def get_runtime(tent_id=DEFAULT_TENT_ID):
    if tent_id == DEFAULT_TENT_ID:
        return get_default_runtime()

    with _registry_lock:
        runtime = _runtimes.get(tent_id)

    if runtime is None:
        raise KeyError(f"Keine Runtime für Zelt '{tent_id}' registriert")

    return runtime


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
):
    """Erzeugt eine unabhängige Runtime, ohne sie automatisch zu registrieren.

    Diese Funktion wird in Phase 2 bereits getestet. Produktiv wird ein
    zweites Zelt erst aktiviert, wenn Phase 3 die persistente Config-/Geräte-
    Zuordnung pro Zelt ergänzt hat.
    """

    if not tent_id:
        raise ValueError("tent_id darf nicht leer sein")

    cfg = deepcopy(DEFAULT_CONFIG)
    if config_data:
        cfg.update(deepcopy(config_data))

    return TentRuntime(
        tent_id=tent_id,
        name=name or _tent_name(tent_id),
        state=legacy_state.create_runtime_state(),
        config=cfg,
        state_lock=threading.RLock(),
        energy_state={},
        energy_lock=threading.RLock(),
        _save_config_callback=save_config_callback,
    )
