# core/devices.py

from copy import deepcopy

from core.runtime import resolve_runtime


# =========================================
# 🔌 GENERIC DEVICE CONTROL SYSTEM
# =========================================

DEVICE_NAMES = (
    "heating",
    "fan",
    "light",
    "vent",
    "irrigation",
    "humidifier",
    "dehumidifier",
    "light2",
    "vent2",
)

DEVICE_MODES = {"OFF", "ON", "TIME", "INTERVAL", "ENV"}


def validate_device_name(device):
    if device not in DEVICE_NAMES:
        raise ValueError(f"Unbekanntes Gerät: {device}")
    return device


def get_device_mode(device, runtime=None):
    validate_device_name(device)
    rt = resolve_runtime(runtime)
    modes = rt.config.setdefault("DEVICE_MODES", {})
    value = modes.get(device, "OFF")

    # Kompatibilität mit dem DEFAULT_CONFIG-Schema, das ältere Einträge als
    # {"mode": "ENV", "params": {...}} enthalten kann.
    if isinstance(value, dict):
        return str(value.get("mode", "OFF") or "OFF").upper()

    return str(value or "OFF").upper()


def get_device_params(device, runtime=None):
    validate_device_name(device)
    rt = resolve_runtime(runtime)

    params = rt.config.setdefault("DEVICE_PARAMS", {})
    if device in params and isinstance(params[device], dict):
        return params[device]

    # Legacy-/Default-Schema unterstützen.
    mode_entry = rt.config.setdefault("DEVICE_MODES", {}).get(device)
    if isinstance(mode_entry, dict):
        legacy_params = mode_entry.get("params")
        if isinstance(legacy_params, dict):
            return legacy_params

    return params.setdefault(device, {})


def get_device_env_config(device, runtime=None):
    validate_device_name(device)
    rt = resolve_runtime(runtime)
    env = rt.config.setdefault("DEVICE_ENV_CONFIG", {})
    current = env.setdefault(device, {})
    if not isinstance(current, dict):
        current = {}
        env[device] = current
    return current


def _normalize_mode(mode):
    mode = str(mode or "OFF").upper()
    if mode not in DEVICE_MODES:
        raise ValueError(f"Ungültiger Gerätemodus: {mode}")
    return mode


def update_device_config(device, data, runtime=None):
    """Aktualisiert genau ein Gerät in genau einer TentRuntime.

    Unterstützt sowohl den neuen kompakten Payload (`mode`, `params`,
    `env_config`) als auch die bisherige DEVICE_* Struktur. Der Merge ist
    in-memory atomar und schaltet bewusst keine Hardware direkt; der jeweilige
    Regelkreis übernimmt die Änderung im nächsten Zyklus.
    """

    validate_device_name(device)
    if not isinstance(data, dict):
        raise TypeError("Geräte-Update muss ein JSON-Objekt sein")

    rt = resolve_runtime(runtime)
    cfg = rt.config
    working = deepcopy(cfg)
    working.setdefault("DEVICE_MODES", {})
    working.setdefault("DEVICE_PARAMS", {})
    working.setdefault("DEVICE_ENV_CONFIG", {})

    mode = data.get("mode")
    params = data.get("params")
    env = data.get("env_config", data.get("env"))

    # Kompatibilität mit den bisherigen JSON-Bodies.
    if isinstance(data.get("DEVICE_MODES"), dict):
        mode = data["DEVICE_MODES"].get(device, mode)
    if isinstance(data.get("DEVICE_PARAMS"), dict):
        params = data["DEVICE_PARAMS"].get(device, params)
    if isinstance(data.get("DEVICE_ENV_CONFIG"), dict):
        env = data["DEVICE_ENV_CONFIG"].get(device, env)

    changed = []

    if mode is not None:
        working["DEVICE_MODES"][device] = _normalize_mode(mode)
        changed.append("mode")

    if params is not None:
        if not isinstance(params, dict):
            raise TypeError("params muss ein JSON-Objekt sein")
        current = working["DEVICE_PARAMS"].setdefault(device, {})
        if not isinstance(current, dict):
            current = {}
            working["DEVICE_PARAMS"][device] = current
        current.update(deepcopy(params))
        changed.append("params")

    if env is not None:
        if not isinstance(env, dict):
            raise TypeError("env_config muss ein JSON-Objekt sein")
        current = working["DEVICE_ENV_CONFIG"].setdefault(device, {})
        if not isinstance(current, dict):
            current = {}
            working["DEVICE_ENV_CONFIG"][device] = current
        current.update(deepcopy(env))
        changed.append("env_config")

    cfg.clear()
    cfg.update(working)
    rt.persist_config()
    return changed
