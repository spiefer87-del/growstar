# core/tent_config.py

from copy import deepcopy
import json
import os
import tempfile
import threading

from core.config import DEFAULT_CONFIG
from core.tents import DEFAULT_TENT_ID, validate_tent_id


TENT_CONFIG_DIR = "tent_configs"

_CONFIG_LOCK = threading.RLock()

_SAFE_DEVICE_NAMES = (
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


def _config_path(tent_id):
    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError("tent_1 verwendet weiterhin config.json")
    return os.path.join(TENT_CONFIG_DIR, f"{tent_id}.json")


def _atomic_write_json(path, data):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".config-",
        suffix=".tmp",
        dir=directory,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def create_safe_tent_config():
    """Erzeugt die absichtlich inaktive Startkonfiguration eines neuen Zeltes.

    Wichtig: Ein neues Zelt erbt weder Sensorzuweisungen noch Hardware-Adressen
    von tent_1. Alle Gerätemodi stehen auf OFF und die Rampe ist deaktiviert.
    """

    cfg = deepcopy(DEFAULT_CONFIG)

    cfg["SENSOR_ASSIGNMENTS"] = {}
    cfg["RAMP_ENABLED"] = 0

    device_names = set(_SAFE_DEVICE_NAMES)
    device_names.update((cfg.get("DEVICE_MODES") or {}).keys())
    cfg["DEVICE_MODES"] = {
        device: "OFF"
        for device in sorted(device_names)
    }
    cfg["DEVICE_PARAMS"] = {}

    # Falls spätere DEFAULT_CONFIG-Versionen Hardware-Adressen enthalten,
    # dürfen sie niemals automatisch in ein neues Zelt übernommen werden.
    for key in list(cfg):
        if key.startswith("IP_") or key.startswith("RELAY_"):
            cfg.pop(key, None)

    return cfg


def _with_defaults(data):
    """Ergänzt nur fehlende Top-Level-Defaults.

    Ein absichtlich leeres SENSOR_ASSIGNMENTS={} muss leer bleiben und darf
    nicht durch einen rekursiven Merge wieder mit Legacy-Sensoren gefüllt
    werden.
    """

    result = deepcopy(DEFAULT_CONFIG)
    if isinstance(data, dict):
        result.update(deepcopy(data))
    return result


def load_tent_config(tent_id):
    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError("tent_1 wird über core.config verwaltet")

    path = _config_path(tent_id)

    with _CONFIG_LOCK:
        if not os.path.exists(path):
            return create_safe_tent_config()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Ungültige Config für {tent_id}: JSON-Objekt erwartet")

        return _with_defaults(data)


def save_tent_config(tent_id, cfg):
    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        raise ValueError("tent_1 wird über core.config.save_config gespeichert")
    if not isinstance(cfg, dict):
        raise TypeError("cfg muss ein dict sein")

    path = _config_path(tent_id)
    with _CONFIG_LOCK:
        _atomic_write_json(path, cfg)
    return path


def ensure_tent_config(tent_id):
    """Erzeugt die sichere Config-Datei eines zusätzlichen Zeltes bei Bedarf."""

    tent_id = validate_tent_id(tent_id)
    if tent_id == DEFAULT_TENT_ID:
        return None

    path = _config_path(tent_id)
    with _CONFIG_LOCK:
        if not os.path.exists(path):
            _atomic_write_json(path, create_safe_tent_config())
    return path
