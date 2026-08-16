# core/devices.py

from copy import deepcopy
from core.runtime import resolve_runtime


AUX_DEVICE_NAMES = ("aux1", "aux2", "aux3", "aux4")

DEVICE_META = {
    "heating": {"label": "Heizung", "icon": "🔥", "auxiliary": False},
    "fan": {"label": "Abluft / Lüfter", "icon": "💨", "auxiliary": False},
    "light": {"label": "Beleuchtung", "icon": "💡", "auxiliary": False},
    "vent": {"label": "Ventilator", "icon": "🌀", "auxiliary": False},
    "irrigation": {"label": "Bewässerung", "icon": "💧", "auxiliary": False},
    "humidifier": {"label": "Luftbefeuchter", "icon": "💦", "auxiliary": False},
    "dehumidifier": {"label": "Entfeuchter", "icon": "🌬️", "auxiliary": False},
    "light2": {"label": "Licht 2", "icon": "💡", "auxiliary": False},
    "vent2": {"label": "Ventilator 2", "icon": "🌀", "auxiliary": False},
    "aux1": {"label": "Wasserpumpen", "icon": "💧", "auxiliary": True},
    "aux2": {"label": "Zusatzgerät 2", "icon": "🔌", "auxiliary": True},
    "aux3": {"label": "Zusatzgerät 3", "icon": "🔌", "auxiliary": True},
    "aux4": {"label": "Zusatzgerät 4", "icon": "🔌", "auxiliary": True},
}

DEVICE_NAMES = tuple(DEVICE_META)
DEVICE_MODES = {"OFF", "ON", "TIME", "INTERVAL", "ENV"}
DEVICE_LABEL_MAX_LENGTH = 48


class DeviceHardwareRequiredError(ValueError):
    """Aktiver Gerätemodus ohne vollständige Hardware-Zuordnung."""

    def __init__(self, device, *, mode, assignment=None):
        self.device = str(device)
        self.mode = str(mode or "OFF").upper()
        self.assignment = deepcopy(assignment or {})
        super().__init__(
            f"{self.device}: Für den Modus {self.mode} ist zuerst eine "
            "Hardware-Zuordnung (IP/Hostname + Relay) erforderlich."
        )


def validate_device_name(device):
    if device not in DEVICE_NAMES:
        raise ValueError(f"Unbekanntes Gerät: {device}")
    return device


def get_device_default_label(device):
    validate_device_name(device)
    return DEVICE_META[device]["label"]


def get_device_icon(device):
    validate_device_name(device)
    return DEVICE_META[device]["icon"]


def is_aux_device(device):
    validate_device_name(device)
    return bool(DEVICE_META[device].get("auxiliary"))


def normalize_device_label(device, value):
    """Normalisiert einen frei vergebenen Anzeigenamen.

    Technische Geräte-IDs bleiben unverändert. Ein leerer Name fällt auf den
    sicheren Standardnamen des Slots zurück.
    """
    validate_device_name(device)

    if value is None:
        return get_device_default_label(device)

    label = " ".join(str(value).split()).strip()
    if not label:
        return get_device_default_label(device)

    if len(label) > DEVICE_LABEL_MAX_LENGTH:
        raise ValueError(
            f"{device}: Gerätename darf höchstens "
            f"{DEVICE_LABEL_MAX_LENGTH} Zeichen lang sein"
        )

    return label


def get_device_label(device, runtime=None, *, config=None):
    """Liefert den stationsbezogenen Anzeigenamen eines Aktors."""
    validate_device_name(device)

    # Nur die vier Universal-Slots sind absichtlich frei benennbar.
    if not is_aux_device(device):
        return get_device_default_label(device)

    if config is None:
        config = resolve_runtime(runtime).config

    labels = config.get("DEVICE_LABELS") if isinstance(config, dict) else None
    if not isinstance(labels, dict):
        labels = {}

    try:
        return normalize_device_label(device, labels.get(device))
    except (TypeError, ValueError):
        # UI/Diagnose bleibt selbst bei manuell beschädigter Config benutzbar.
        return get_device_default_label(device)


def get_device_mode(device, runtime=None):
    validate_device_name(device)
    rt = resolve_runtime(runtime)
    modes = rt.config.setdefault("DEVICE_MODES", {})
    value = modes.get(device, "OFF")
    if isinstance(value, dict):
        return str(value.get("mode", "OFF") or "OFF").upper()
    return str(value or "OFF").upper()


def get_device_params(device, runtime=None):
    validate_device_name(device)
    rt = resolve_runtime(runtime)
    params = rt.config.setdefault("DEVICE_PARAMS", {})
    if device in params and isinstance(params[device], dict):
        return params[device]
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


def _assert_hardware_for_active_mode(device, mode, runtime):
    mode = _normalize_mode(mode)
    if mode == "OFF":
        return

    # Lazy Import vermeidet einen Modulzyklus mit hardware_assignments.
    from core.hardware_assignments import device_assignment

    assignment = device_assignment(runtime.tent_id, device)
    if not assignment.get("configured"):
        raise DeviceHardwareRequiredError(
            device,
            mode=mode,
            assignment=assignment,
        )


def update_device_config(device, data, runtime=None):
    """Aktualisiert genau ein Gerät atomar in genau einer TentRuntime.

    Phase 4L:
    OFF bleibt immer möglich. ON/TIME/INTERVAL/ENV werden dagegen nur
    gespeichert, wenn bereits IP/Hostname + Relay zugeordnet sind.
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

    if isinstance(data.get("DEVICE_MODES"), dict):
        mode = data["DEVICE_MODES"].get(device, mode)
    if isinstance(data.get("DEVICE_PARAMS"), dict):
        params = data["DEVICE_PARAMS"].get(device, params)
    if isinstance(data.get("DEVICE_ENV_CONFIG"), dict):
        env = data["DEVICE_ENV_CONFIG"].get(device, env)

    changed = []

    if mode is not None:
        normalized_mode = _normalize_mode(mode)
        _assert_hardware_for_active_mode(device, normalized_mode, rt)
        working["DEVICE_MODES"][device] = normalized_mode
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
