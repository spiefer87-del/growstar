# core/config_update.py

from copy import deepcopy

from core.config import (
    DEFAULT_CONFIG,
    VPD_LEGACY_SHARED_KEYS,
    migrate_vpd_phase_config,
)
from core.devices import AUX_DEVICE_NAMES, normalize_device_label
from core.environment_limits import validate_environment_limits
from core.profile import get_active_profile
from core.ramp import resync_active_ramp, stop_ramp
from core.runtime import resolve_runtime
from core.vpd import reset_vpd_control, validate_vpd_environment_alignment


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
    "VPD_EFFECT_WINDOW_MIN",
    "VPD_FAN_STEP",
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
    migrate_vpd_phase_config(snapshot)
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

    # Ein noch im Browser geöffneter 3.16.0-Client kann die fünf gemeinsamen
    # Felder senden. Sie werden atomar auf Tag und Nacht gespiegelt. Neue
    # phasenbezogene Felder haben Vorrang, falls beide Schemas vorkommen.
    incoming = deepcopy(data)
    migrate_vpd_phase_config(incoming, remove_legacy=True)

    rt = resolve_runtime(runtime)
    cfg = rt.config
    st = rt.state
    working = deepcopy(cfg)

    tracked_keys = {
        key for key in incoming
        if key != "ACTIVE_PROFILE"
    }

    for key, value in incoming.items():
        if key == "ACTIVE_PROFILE":
            # Profilwechsel läuft über den expliziten Profil-Endpunkt, damit
            # Rampen-/Persistenzzustand konsistent zurückgesetzt wird.
            continue

        if key in _NESTED_DEVICE_KEYS:
            _merge_nested_config(working, key, value)
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

            continue

        if key.startswith(_PASSTHROUGH_PREFIXES):
            working[key] = deepcopy(value)
            continue

        if key == "SENSOR_ASSIGNMENTS":
            if not isinstance(value, dict):
                raise TypeError("SENSOR_ASSIGNMENTS muss ein JSON-Objekt sein")
            working[key] = deepcopy(value)
            continue

        working[key] = _coerce_scalar(key, value)

    if any(
        key.startswith("VPD_")
        for key in incoming
    ):
        for legacy_key in VPD_LEGACY_SHARED_KEYS:
            working.pop(legacy_key, None)
            tracked_keys.add(legacy_key)

    # Browserformulare senden absichtlich einen vollständigen Snapshot. Nur
    # tatsächlich veränderte, bereits normalisierte Werte dürfen jedoch
    # Seiteneffekte wie Rampen-Neustart oder VPD-Reset auslösen. Insbesondere
    # ein reines Speichern des Beobachtungsmodus darf eine laufende Rampe nicht
    # anfassen.
    missing = object()
    changed_keys = {
        key for key in tracked_keys
        if cfg.get(key, missing) != working.get(key, missing)
    }

    # Phase 4V.2: Klima-/Alarmgrenzen werden VOR dem Commit validiert.
    validate_environment_limits(working)
    vpd_validation = deepcopy(DEFAULT_CONFIG)
    vpd_validation.update(working)
    validate_vpd_environment_alignment(vpd_validation)

    # Erst nach vollständiger Validierung den vorhandenen Dict in-place
    # aktualisieren. Referenzen auf runtime.config bleiben dadurch gültig.
    cfg.clear()
    cfg.update(working)

    if st.ramp_active:
        if not cfg.get("RAMP_ENABLED", 0):
            stop_ramp(runtime=rt)
            st.live_state["ramp_active"] = False
            st.live_state["ramp_target"] = None
        elif changed_keys.intersection({
            "DAY_TEMP",
            "NIGHT_TEMP",
            "DAY_START_MIN",
            "NIGHT_START_MIN",
            "RAMP_DURATION_MIN",
        }):
            # Ein einziger, phasenbewusster Neustart übernimmt Ziel und Ende.
            # Zwei aufeinanderfolgende Restarts konnten die Abendrampe bisher
            # erst verlängern und anschließend sogar in Richtung TAG drehen.
            resync_active_ramp(runtime=rt)

    elif not cfg.get("RAMP_ENABLED", 0) and st.live_state.get("ramp_active"):
        st.live_state["ramp_active"] = False
        st.live_state["ramp_target"] = None

    vpd_schedule_changed = changed_keys.intersection({
        "DAY_START_MIN",
        "NIGHT_START_MIN",
        "RAMP_ENABLED",
        "RAMP_DURATION_MIN",
    })
    vpd_mode = str(cfg.get("VPD_CONTROL_MODE", "OFF") or "OFF").upper()

    if any(key.startswith("VPD_") for key in changed_keys):
        reset_vpd_control(runtime=rt, reason="VPD-Einstellungen geändert")
    elif vpd_mode in {"MONITOR", "AUTO"} and vpd_schedule_changed:
        reset_vpd_control(runtime=rt, reason="VPD-Rampenplan geändert")
    elif changed_keys.intersection({
        "SENSOR_ASSIGNMENTS",
        "TEMP_OFFSET",
        "HUM_OFFSET",
        "OUTSIDE_TEMP_OFFSET",
        "OUTSIDE_HUM_OFFSET",
    }):
        reset_vpd_control(runtime=rt, reason="VPD-Sensorbasis geändert")

    rt.persist_config()

    return {
        "changed_keys": sorted(changed_keys),
        "config": config_snapshot(rt),
    }
