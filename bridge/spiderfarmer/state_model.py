"""Canonical Spider Farmer read model for Growstar SF.2.

This module never creates MQTT packets and never sends commands. It only turns
already-observed Spider Farmer JSON payloads into a compact, stable Growstar
state model.

Observed sources:
- UP/getDevSta: current live state
- DOWN/setConfigField: full configuration blocks sent by the Spider Farmer cloud

The normalized state intentionally contains only known operational fields. Raw
payloads remain exclusively in the private SF.1 diagnostics capture.
"""

from __future__ import annotations

from copy import deepcopy
import re


_TOPIC_RE = re.compile(
    r"^SF/GGS/(?P<prefix>[^/]+)/API/(?P<direction>UP|DOWN)/(?P<pid>[0-9A-Fa-f]+)$"
)


def new_state():
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {},
    }


def apply_publish(state, session_id, *, direction, topic, payload, timestamp):
    """Apply one already-decoded MQTT PUBLISH to the canonical state.

    Returns True when the canonical state changed.
    """

    if not isinstance(state, dict):
        raise TypeError("state must be a dict")

    controllers = state.setdefault("controllers", {})

    session_id = str(session_id or "unknown").strip().lower() or "unknown"
    controller = controllers.setdefault(
        session_id,
        {
            "id": session_id,
            "pid": None,
            "prefix": None,
            "last_seen": None,
            "live": {},
            "config": {},
        },
    )

    changed = False

    topic_info = parse_topic(topic)
    if topic_info:
        if controller.get("pid") != topic_info["pid"]:
            controller["pid"] = topic_info["pid"]
            changed = True
        if controller.get("prefix") != topic_info["prefix"]:
            controller["prefix"] = topic_info["prefix"]
            changed = True

    if controller.get("last_seen") != timestamp:
        controller["last_seen"] = timestamp
        changed = True

    if not isinstance(payload, dict):
        return changed

    method = payload.get("method")

    if direction == "up" and method == "getDevSta":
        data = payload.get("data")
        if isinstance(data, dict):
            live = normalize_live_state(data)
            if live:
                changed |= _deep_merge(controller.setdefault("live", {}), live)

    if direction == "down" and method == "setConfigField":
        params = payload.get("params")
        if isinstance(params, dict):
            config = normalize_config(params)
            if config:
                changed |= _deep_merge(controller.setdefault("config", {}), config)

    return changed


def parse_topic(topic):
    match = _TOPIC_RE.match(str(topic or ""))
    if not match:
        return None

    return {
        "prefix": match.group("prefix"),
        "direction": match.group("direction").lower(),
        "pid": match.group("pid").upper(),
    }


def normalize_live_state(data):
    result = {}

    sensor = _normalize_sensor(data.get("sensor"))
    if sensor:
        result["sensor"] = sensor

    for module in ("light", "light2", "fan", "blower"):
        normalized = _normalize_live_module(data.get(module))
        if normalized:
            result[module] = normalized

    # Power strips use outlet/O1..On in some firmware variants.
    outlet = data.get("outlet")
    normalized_outlet = _normalize_outlet_live(outlet)
    if normalized_outlet:
        result["outlet"] = normalized_outlet

    # Some PS firmwares expose O1..On directly below data.
    direct_outlets = {}
    for key, value in data.items():
        if _is_outlet_key(key) and isinstance(value, dict):
            direct_outlets[key] = _normalize_outlet_entry(value)
    direct_outlets = {k: v for k, v in direct_outlets.items() if v}
    if direct_outlets:
        result.setdefault("outlet", {}).setdefault("channels", {}).update(direct_outlets)

    return result


def normalize_config(params):
    result = {}

    key_path = params.get("keyPath")
    module_name = None

    if isinstance(key_path, list) and len(key_path) >= 2:
        module_name = str(key_path[-1])

    candidate_names = []
    if module_name:
        candidate_names.append(module_name)

    for name in (
        "light",
        "light2",
        "fan",
        "blower",
        "heater",
        "humidifier",
        "dehumidifier",
    ):
        if name in params and name not in candidate_names:
            candidate_names.append(name)

    for name in candidate_names:
        block = params.get(name)
        if not isinstance(block, dict):
            continue

        if name in ("fan", "blower"):
            normalized = _normalize_fan_config(block)
        elif name in ("light", "light2"):
            normalized = _normalize_light_config(block)
        else:
            normalized = _copy_known(
                block,
                {
                    "modeType": "mode_type",
                    "mOnOff": "on",
                    "mLevel": "level",
                },
            )

        if normalized:
            result[name] = normalized

    # Power-strip writes address one outlet through keyPath ["outlet", "O3"].
    if (
        isinstance(key_path, list)
        and len(key_path) >= 2
        and str(key_path[0]) == "outlet"
        and _is_outlet_key(key_path[1])
    ):
        outlet_name = str(key_path[1])
        block = params.get(outlet_name)
        if isinstance(block, dict):
            normalized = _normalize_outlet_config(block)
            if normalized:
                result.setdefault("outlet", {}).setdefault("channels", {})[
                    outlet_name
                ] = normalized

    return result


def _normalize_sensor(value):
    if not isinstance(value, dict):
        return {}

    mapping = {
        "temp": "temperature_c",
        "humi": "humidity_percent",
        "vpd": "vpd_kpa",
        "co2": "co2_ppm",
        "ppfd": "ppfd",
        "tempSoil": "soil_temperature_c",
        "humiSoil": "soil_moisture_percent",
        "ECSoil": "soil_ec",
        "isDayEnvTarget": "day_environment_target",
        "isDaySensor": "day_sensor",
    }
    return _copy_known(value, mapping)


def _normalize_live_module(value):
    if not isinstance(value, dict):
        return {}

    result = _copy_known(
        value,
        {
            "modeType": "mode_type",
            "mOnOff": "on",
            "on": "on",
            "mLevel": "level",
            "level": "level",
        },
    )

    # Observed GGS light payloads omit "on" when switched off and report level=0.
    # Derive an effective on/off state without overwriting an explicit field.
    if "on" not in result and "level" in result:
        try:
            result["on"] = 1 if float(result["level"]) > 0 else 0
        except (TypeError, ValueError):
            pass

    return result


def _normalize_fan_config(block):
    result = _copy_known(
        block,
        {
            "modeType": "mode_type",
            "lastAutoModeType": "last_auto_mode_type",
            "mOnOff": "on",
            "mLevel": "level",
            "minSpeed": "standby_level",
            "maxSpeed": "run_level",
            "shakeLevel": "oscillation_level",
            "natural": "natural_wind",
        },
    )

    cycle = block.get("cycleTime")
    if isinstance(cycle, dict):
        normalized_cycle = _copy_known(
            cycle,
            {
                "weekmask": "weekmask",
                "startTime": "start_time_s",
                "openDur": "run_duration_s",
                "closeDur": "off_duration_s",
                "times": "executions",
            },
        )
        if normalized_cycle:
            result["cycle"] = normalized_cycle

    periods = _normalize_periods(block.get("timePeriod"))
    if periods:
        result["schedule"] = periods

    return result


def _normalize_light_config(block):
    result = _copy_known(
        block,
        {
            "modeType": "mode_type",
            "lastAutoModeType": "last_auto_mode_type",
            "mOnOff": "on",
            "mLevel": "level",
            "darkTemp": "dark_temperature_c",
            "offTemp": "off_temperature_c",
            "ppfdMinBrightness": "ppfd_min_level",
            "ppfdMaxBrightness": "ppfd_max_level",
        },
    )

    periods = _normalize_periods(block.get("timePeriod"))
    if periods:
        result["schedule"] = periods

    ppfd_periods = _normalize_periods(block.get("ppfdPeriod"))
    if ppfd_periods:
        result["ppfd_schedule"] = ppfd_periods

    return result


def _normalize_periods(value):
    if not isinstance(value, list):
        return []

    result = []
    for item in value:
        if not isinstance(item, dict):
            continue

        normalized = _copy_known(
            item,
            {
                "enabled": "enabled",
                "weekmask": "weekmask",
                "startTime": "start_time_s",
                "endTime": "end_time_s",
                "brightness": "level",
                "fadeTime": "fade_time_s",
            },
        )
        if normalized:
            result.append(normalized)

    return result


def _normalize_outlet_live(value):
    if not isinstance(value, dict):
        return {}

    result = {}
    if "psmode" in value:
        result["ps_mode"] = deepcopy(value["psmode"])

    channels = {}
    for key, item in value.items():
        if _is_outlet_key(key) and isinstance(item, dict):
            normalized = _normalize_outlet_entry(item)
            if normalized:
                channels[key] = normalized

    if channels:
        result["channels"] = channels

    return result


def _normalize_outlet_entry(value):
    return _copy_known(
        value,
        {
            "on": "on",
            "mOnOff": "on",
            "modeType": "mode_type",
        },
    )


def _normalize_outlet_config(value):
    result = _copy_known(
        value,
        {
            "mOnOff": "on",
            "on": "on",
            "modeType": "mode_type",
            "tempAdd": "temperature_offset",
            "humiAdd": "humidity_offset",
        },
    )

    cycle = value.get("cycleTime")
    if isinstance(cycle, dict):
        normalized_cycle = _copy_known(
            cycle,
            {
                "weekmask": "weekmask",
                "startTime": "start_time_s",
                "openDur": "run_duration_s",
                "closeDur": "off_duration_s",
                "times": "executions",
            },
        )
        if normalized_cycle:
            result["cycle"] = normalized_cycle

    periods = _normalize_periods(value.get("timePeriod"))
    if periods:
        result["schedule"] = periods

    # Bind/wateringEnv can become large and firmware-specific. Keep only a
    # boolean hint for now; raw diagnostics remain available privately.
    if value.get("bind") is not None:
        result["sensor_binding_present"] = True
    if value.get("wateringEnv") is not None:
        result["watering_automation_present"] = True

    return result


def _copy_known(source, mapping):
    if not isinstance(source, dict):
        return {}

    result = {}
    for source_key, target_key in mapping.items():
        if source_key in source:
            result[target_key] = deepcopy(source[source_key])
    return result


def _is_outlet_key(value):
    text = str(value or "")
    return len(text) >= 2 and text[0] == "O" and text[1:].isdigit()


def _deep_merge(target, source):
    changed = False

    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            if _deep_merge(target[key], value):
                changed = True
            continue

        if target.get(key) != value:
            target[key] = deepcopy(value)
            changed = True

    return changed
