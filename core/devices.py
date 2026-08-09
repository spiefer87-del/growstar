# core/devices.py

from core.runtime import resolve_runtime


# =========================================
# 🔌 GENERIC DEVICE CONTROL SYSTEM
# =========================================

def get_device_mode(device, runtime=None):
    rt = resolve_runtime(runtime)
    modes = rt.config.setdefault("DEVICE_MODES", {})
    value = modes.get(device, "OFF")

    # Kompatibilität mit dem DEFAULT_CONFIG-Schema, das ältere Einträge als
    # {"mode": "ENV", "params": {...}} enthalten kann.
    if isinstance(value, dict):
        return value.get("mode", "OFF")

    return value or "OFF"


def get_device_params(device, runtime=None):
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
