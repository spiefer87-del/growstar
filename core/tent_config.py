# core/tent_config.py

from copy import deepcopy
import json
import os
import tempfile
import threading

from core.config import DEFAULT_CONFIG, migrate_vpd_phase_config
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

    return os.path.join(
        TENT_CONFIG_DIR,
        f"{tent_id}.json",
    )


def _atomic_write_json(path, data):
    """Schreibt JSON atomar, damit eine Config nie halb geschrieben bleibt."""

    directory = os.path.dirname(
        os.path.abspath(path)
    ) or "."

    os.makedirs(
        directory,
        exist_ok=True,
    )

    fd, temp_path = tempfile.mkstemp(
        prefix=".config-",
        suffix=".tmp",
        dir=directory,
        text=True,
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(
            temp_path,
            path,
        )

    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

        raise


def _remove_hardware_defaults(cfg):
    """Entfernt IP-/Relay-Werte aus einer Config-Kopie.

    Hardware-Zuordnungen dürfen bei zusätzlichen Stationen niemals aus der
    globalen DEFAULT_CONFIG geerbt werden. Sie müssen ausdrücklich in der
    jeweiligen Stationsconfig gespeichert sein.
    """

    for key in list(cfg):
        if key.startswith("IP_") or key.startswith("RELAY_"):
            cfg.pop(key, None)

    return cfg


def create_safe_tent_config():
    """Erzeugt die sichere Startkonfiguration einer zusätzlichen Station.

    Ein neues Zelt / eine neue Station erbt:
    - keine Sensorzuweisungen,
    - keine Hardware-Adressen,
    - keine aktiven Gerätemodi.

    Die Rampe startet ebenfalls deaktiviert.
    """

    cfg = deepcopy(DEFAULT_CONFIG)

    # Zusätzliche Stationen bekommen Sensoren ausschließlich explizit
    # über ihre eigene SENSOR_ASSIGNMENTS-Konfiguration zugewiesen.
    cfg["SENSOR_ASSIGNMENTS"] = {}

    # Eine neue Station darf nicht sofort mit einer laufenden Rampe starten.
    cfg["RAMP_ENABLED"] = 0

    # Alle bekannten Geräte sicher auf OFF setzen. Falls DEFAULT_CONFIG später
    # zusätzliche Geräte enthält, werden auch diese automatisch berücksichtigt.
    device_names = set(_SAFE_DEVICE_NAMES)
    device_names.update(
        (cfg.get("DEVICE_MODES") or {}).keys()
    )

    cfg["DEVICE_MODES"] = {
        device: "OFF"
        for device in sorted(device_names)
    }

    # Keine Zeit-/Intervallparameter eines anderen Zeltes übernehmen.
    cfg["DEVICE_PARAMS"] = {}

    # Entscheidender Multi-Station-Schutz:
    # IP_* und RELAY_* gehören immer nur zu der Station, in deren Config sie
    # ausdrücklich gespeichert wurden.
    _remove_hardware_defaults(cfg)

    return cfg


def _with_defaults(data):
    """Ergänzt fehlende allgemeine Top-Level-Defaults sicher.

    WICHTIG:
    Hardware-Zuordnungen aus DEFAULT_CONFIG werden VOR dem Merge entfernt.
    Dadurch kann eine zusätzliche Station niemals versehentlich die Shelly-
    Adressen von tent_1 erben.

    Bereits ausdrücklich in der Stationsdatei gespeicherte IP_*/RELAY_*-Werte
    bleiben dagegen erhalten, weil ``data`` erst danach darübergelegt wird.

    Ein absichtlich leeres SENSOR_ASSIGNMENTS={} bleibt ebenfalls leer; es
    findet bewusst kein rekursiver Merge statt.
    """

    result = deepcopy(DEFAULT_CONFIG)

    # Niemals globale Hardware-Zuordnungen in zusätzliche Stationen übernehmen.
    _remove_hardware_defaults(result)

    if isinstance(data, dict):
        loaded = deepcopy(data)
        migrate_vpd_phase_config(loaded)
        result.update(loaded)

    return result


def load_tent_config(tent_id):
    """Lädt die persistente Config einer zusätzlichen Station."""

    tent_id = validate_tent_id(tent_id)

    if tent_id == DEFAULT_TENT_ID:
        raise ValueError(
            "tent_1 wird über core.config verwaltet"
        )

    path = _config_path(tent_id)

    with _CONFIG_LOCK:
        if not os.path.exists(path):
            return create_safe_tent_config()

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                f"Ungültige Config für {tent_id}: JSON-Objekt erwartet"
            )

        return _with_defaults(data)


def save_tent_config(tent_id, cfg):
    """Speichert ausschließlich die Config einer zusätzlichen Station."""

    tent_id = validate_tent_id(tent_id)

    if tent_id == DEFAULT_TENT_ID:
        raise ValueError(
            "tent_1 wird über core.config.save_config gespeichert"
        )

    if not isinstance(cfg, dict):
        raise TypeError(
            "cfg muss ein dict sein"
        )

    path = _config_path(tent_id)

    with _CONFIG_LOCK:
        _atomic_write_json(
            path,
            cfg,
        )

    return path


def ensure_tent_config(tent_id):
    """Erzeugt die sichere Config-Datei einer zusätzlichen Station bei Bedarf."""

    tent_id = validate_tent_id(tent_id)

    if tent_id == DEFAULT_TENT_ID:
        return None

    path = _config_path(tent_id)

    with _CONFIG_LOCK:
        if not os.path.exists(path):
            _atomic_write_json(
                path,
                create_safe_tent_config(),
            )

    return path
