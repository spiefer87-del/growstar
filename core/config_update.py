# core/config_update.py

from copy import deepcopy

from core.devices import AUX_DEVICE_NAMES, normalize_device_label
from core.environment_limits import validate_environment_limits
from core.profile import get_active_profile
from core.ramp import resync_active_ramp, stop_ramp, update_ramp_duration
from core.runtime import resolve_runtime


_NESTED_DEVICE_KEYS = {
    "DEVICE_MODES",
    "DEVICE_PARAMS",
    "DEVICE_ENV_CONFIG",
}

_INTEGER_KEYS = {
    "DAY_START_MIN",
    "NIGHT_START_MIN",
    "RAMP_DURATION_MIN",
    "RAMP_ENABLED",
    "LIGHT_SUN_ENABLED",
    "LIGHT_SUNRISE_DURATION_MIN",
    "LIGHT_SUNSET_DURATION_MIN",
    "LIGHT_SUN_MIN_LEVEL",
    "SENSOR_UPDATE_INTERVAL_SEC",
    "ENERGY_DAY_RESET_MIN",
}

# UI-/Dashboard-Strukturen bleiben JSON-Objekte/Listen und werden nicht
# numerisch umgewandelt.
_PASSTHROUGH_PREFIXES = ("DASH_",)


def active_profile_for_runtime(runtime=None):
    """Return the selected preset name for one runtime."""

    rt = resolve_runtime(runtime)
    configured = rt.config.get("ACTIVE_PROFILE")
    if configured:
        return configured
    return get_active_profile(runtime=rt)


def config_snapshot(runtime=None):
    rt = resolve_runtime(runtime)
    snapshot = deepcopy(rt.config)
    snapshot["ACTIVE_PROFILE"] = active_profile_for_runtime(rt)
    return snapshot


def _merge_nested_config(cfg, key, value):
    if not isinstance(value, dict):
        raise TypeError(f"{key} muss ein JSON-Objekt sein")

    target = cfg.setdefault(key, {})
    if not isinstance(target, dict):
        target = {}
        cfg[key] = target

    if key == "DEVICE_MODES":
        target.update(deepcopy(value))
        return

    for item_name, item_data in value.items():
        if not isinstance(item_data, dict):
            target[item_name] = deepcopy(item_data)
            continue
        current = target.setdefault(item_name, {})
        if not isinstance(current, dict):
            current = {}
            target[item_name] = current
        current.update(deepcopy(item_data))


def _coerce_scalar(key, value):
    if key.startswith("IP_"):
        return str(value).strip()

    if key.startswith("RELAY_") or key in _INTEGER_KEYS:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} muss eine Ganzzahl sein") from exc

    if isinstance(value, (dict, list, tuple, bool)) or value is None:
        return deepcopy(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def apply_config_patch(data, runtime=None):
    """Merge a JSON config patch into exactly one TentRuntime.

    Der Merge ist in-memory atomar: erst wenn der komplette Payload validiert
    ist, wird die Runtime-Config ersetzt. So kann ein fehlerhafter Wert nicht
    die Hälfte eines Updates im laufenden Regelkreis hinterlassen.

    Presets werden hier absichtlich nicht verändert. Sie sind Vorlagen; die
    laufende Konfiguration gehört immer der ausgewählten Station.
    """

    if not isinstance(data, dict):
        raise TypeError("Config-Update muss ein JSON-Objekt sein")

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state
    working = deepcopy(cfg)

    changed_keys = set()

    for key, value in data.items():
        if key == "ACTIVE_PROFILE":
            # Profilwechsel läuft über den expliziten Profil-Endpunkt, damit
            # Rampen-/Persistenzzustand konsistent zurückgesetzt wird.
            continue

        if key in _NESTED_DEVICE_KEYS:
            _merge_nested_config(working, key, value)
            changed_keys.add(key)
            continue

        if key == "DEVICE_LABELS":
            if not isinstance(value, dict):
                raise TypeError("DEVICE_LABELS muss ein JSON-Objekt sein")

            unknown = sorted(set(value) - set(AUX_DEVICE_NAMES))
            if unknown:
                raise ValueError(
                    "Unbekannte Gerätenamen-Slots: " + ", ".join(unknown)
                )

            target = working.setdefault("DEVICE_LABELS", {})
            if not isinstance(target, dict):
                target = {}
                working["DEVICE_LABELS"] = target

            for device, label in value.items():
                target[device] = normalize_device_label(device, label)

            changed_keys.add(key)
            continue

        if key.startswith(_PASSTHROUGH_PREFIXES):
            working[key] = deepcopy(value)
            changed_keys.add(key)
            continue

        if key == "SENSOR_ASSIGNMENTS":
            if not isinstance(value, dict):
                raise TypeError("SENSOR_ASSIGNMENTS muss ein JSON-Objekt sein")
            working[key] = deepcopy(value)
            changed_keys.add(key)
            continue

        working[key] = _coerce_scalar(key, value)
        changed_keys.add(key)

    # Phase 4V.2: Klima-/Alarmgrenzen werden VOR dem Commit validiert.
    validate_environment_limits(working)

    # Erst nach vollständiger Validierung den vorhandenen Dict in-place
    # aktualisieren. Referenzen auf runtime.config bleiben dadurch gültig.
    cfg.clear()
    cfg.update(working)

    if st.ramp_active:
        if "RAMP_DURATION_MIN" in changed_keys:
            update_ramp_duration(runtime=rt)

        if {"DAY_TEMP", "NIGHT_TEMP"}.intersection(changed_keys):
            resync_active_ramp(runtime=rt)

    if not cfg.get("RAMP_ENABLED", 0):
        stop_ramp(runtime=rt)
        st.live_state["ramp_active"] = False
        st.live_state["ramp_target"] = None

    rt.persist_config()

    return {
        "changed_keys": sorted(changed_keys),
        "config": config_snapshot(rt),
    }
