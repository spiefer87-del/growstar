"""Spider Farmer device inventory model for Growstar SF.3A.

This module is deliberately read-only. It derives stable Growstar-facing device
records from the canonical SF.2 controller state and never opens sockets,
publishes MQTT packets, builds command payloads or writes controller state.

The canonical SF.2 state already normalizes observed live/config fields. SF.3A
adds a second projection that answers a different question:

    "Which Spider Farmer devices exist on this controller, what is their live
     state, and which observed configuration values are available?"

The model is intentionally conservative. A capability is exposed only when the
corresponding normalized field was actually observed.
"""

from __future__ import annotations

from copy import deepcopy


_DEVICE_ORDER = (
    "environment",
    "light",
    "light2",
    "fan",
    "blower",
    "heater",
    "humidifier",
    "dehumidifier",
    "outlet",
)


def build_controller_devices(controller):
    """Return a stable, read-only device inventory for one controller."""

    if not isinstance(controller, dict):
        return []

    live = controller.get("live")
    config = controller.get("config")

    if not isinstance(live, dict):
        live = {}

    if not isinstance(config, dict):
        config = {}

    result = []

    environment = _environment_device(live.get("sensor"))
    if environment:
        result.append(environment)

    for name in ("light", "light2"):
        device = _light_device(
            name,
            live.get(name),
            config.get(name),
        )
        if device:
            result.append(device)

    for name in ("fan", "blower"):
        device = _air_device(
            name,
            live.get(name),
            config.get(name),
        )
        if device:
            result.append(device)

    for name in ("heater", "humidifier", "dehumidifier"):
        device = _generic_device(
            name,
            live.get(name),
            config.get(name),
        )
        if device:
            result.append(device)

    outlet = _outlet_device(
        live.get("outlet"),
        config.get("outlet"),
    )
    if outlet:
        result.append(outlet)

    order = {
        name: index
        for index, name in enumerate(_DEVICE_ORDER)
    }

    result.sort(
        key=lambda item: (
            order.get(item.get("kind"), 999),
            str(item.get("id") or ""),
        )
    )

    return result


def device_by_id(controller, device_id):
    wanted = str(device_id or "").strip().lower()

    if not wanted:
        return None

    for item in build_controller_devices(controller):
        if str(item.get("id") or "").lower() == wanted:
            return deepcopy(item)

        for channel in item.get("channels") or []:
            if str(channel.get("id") or "").lower() == wanted:
                return deepcopy(channel)

    return None


def _environment_device(sensor):
    if not isinstance(sensor, dict) or not sensor:
        return None

    values = _copy_present(
        sensor,
        (
            "temperature_c",
            "humidity_percent",
            "vpd_kpa",
            "co2_ppm",
            "ppfd",
            "soil_temperature_c",
            "soil_moisture_percent",
            "soil_ec",
            "day_environment_target",
            "day_sensor",
        ),
    )

    if not values:
        return None

    return {
        "id": "environment",
        "kind": "environment",
        "label": "GGS Sensor",
        "read_only": True,
        "available": True,
        "capabilities": sorted(values.keys()),
        "live": values,
        "config": {},
        "effective": deepcopy(values),
    }


def _light_device(name, live_block, config_block):
    live = _safe_dict(live_block)
    config = _safe_dict(config_block)

    if not live and not config:
        return None

    effective = _effective(
        live,
        config,
        live_first=("on", "level", "mode_type"),
        config_only=(
            "last_auto_mode_type",
            "dark_temperature_c",
            "off_temperature_c",
            "ppfd_min_level",
            "ppfd_max_level",
            "schedule",
            "ppfd_schedule",
        ),
    )

    capabilities = _capabilities_from_fields(
        effective,
        {
            "on": "power",
            "level": "level",
            "mode_type": "mode",
            "last_auto_mode_type": "last_auto_mode",
            "dark_temperature_c": "dark_temperature",
            "off_temperature_c": "off_temperature",
            "ppfd_min_level": "ppfd_min_level",
            "ppfd_max_level": "ppfd_max_level",
            "schedule": "schedule",
            "ppfd_schedule": "ppfd_schedule",
        },
    )

    return {
        "id": name,
        "kind": name,
        "label": "Licht 1" if name == "light" else "Licht 2",
        "read_only": True,
        "available": True,
        "capabilities": capabilities,
        "live": deepcopy(live),
        "config": deepcopy(config),
        "effective": effective,
    }


def _air_device(name, live_block, config_block):
    live = _safe_dict(live_block)
    config = _safe_dict(config_block)

    if not live and not config:
        return None

    effective = _effective(
        live,
        config,
        live_first=("on", "level", "mode_type"),
        config_only=(
            "last_auto_mode_type",
            "standby_level",
            "run_level",
            "oscillation_level",
            "natural_wind",
            "cycle",
            "schedule",
        ),
    )

    capabilities = _capabilities_from_fields(
        effective,
        {
            "on": "power",
            "level": "level",
            "mode_type": "mode",
            "last_auto_mode_type": "last_auto_mode",
            "standby_level": "standby_level",
            "run_level": "run_level",
            "oscillation_level": "oscillation_level",
            "natural_wind": "natural_wind",
            "cycle": "cycle",
            "schedule": "schedule",
        },
    )

    return {
        "id": name,
        "kind": name,
        "label": "Ventilator" if name == "fan" else "Gebläse",
        "read_only": True,
        "available": True,
        "capabilities": capabilities,
        "live": deepcopy(live),
        "config": deepcopy(config),
        "effective": effective,
    }


def _generic_device(name, live_block, config_block):
    live = _safe_dict(live_block)
    config = _safe_dict(config_block)

    if not live and not config:
        return None

    effective = _effective(
        live,
        config,
        live_first=("on", "level", "mode_type"),
        config_only=(),
    )

    label = {
        "heater": "Heizung",
        "humidifier": "Luftbefeuchter",
        "dehumidifier": "Luftentfeuchter",
    }.get(name, name)

    capabilities = _capabilities_from_fields(
        effective,
        {
            "on": "power",
            "level": "level",
            "mode_type": "mode",
        },
    )

    return {
        "id": name,
        "kind": name,
        "label": label,
        "read_only": True,
        "available": True,
        "capabilities": capabilities,
        "live": deepcopy(live),
        "config": deepcopy(config),
        "effective": effective,
    }


def _outlet_device(live_block, config_block):
    live = _safe_dict(live_block)
    config = _safe_dict(config_block)

    live_channels = _safe_dict(live.get("channels"))
    config_channels = _safe_dict(config.get("channels"))

    names = sorted(
        set(live_channels) | set(config_channels),
        key=_outlet_sort_key,
    )

    if not names and not live and not config:
        return None

    channels = []

    for name in names:
        live_channel = _safe_dict(live_channels.get(name))
        config_channel = _safe_dict(config_channels.get(name))

        effective = _effective(
            live_channel,
            config_channel,
            live_first=("on", "mode_type"),
            config_only=(
                "temperature_offset",
                "humidity_offset",
                "cycle",
                "schedule",
                "sensor_binding_present",
                "watering_automation_present",
            ),
        )

        capabilities = _capabilities_from_fields(
            effective,
            {
                "on": "power",
                "mode_type": "mode",
                "temperature_offset": "temperature_offset",
                "humidity_offset": "humidity_offset",
                "cycle": "cycle",
                "schedule": "schedule",
                "sensor_binding_present": "sensor_binding",
                "watering_automation_present": "watering_automation",
            },
        )

        channels.append({
            "id": f"outlet:{name}",
            "channel": name,
            "kind": "outlet_channel",
            "label": name,
            "read_only": True,
            "available": True,
            "capabilities": capabilities,
            "live": deepcopy(live_channel),
            "config": deepcopy(config_channel),
            "effective": effective,
        })

    capabilities = []

    if "ps_mode" in live:
        capabilities.append("ps_mode")

    if channels:
        capabilities.append("channels")

    return {
        "id": "outlet",
        "kind": "outlet",
        "label": "Steckdosenleiste",
        "read_only": True,
        "available": True,
        "capabilities": capabilities,
        "live": _copy_present(live, ("ps_mode",)),
        "config": {},
        "effective": _copy_present(live, ("ps_mode",)),
        "channels": channels,
    }


def _effective(live, config, *, live_first, config_only):
    result = {}

    for field in live_first:
        if field in live:
            result[field] = deepcopy(live[field])
        elif field in config:
            result[field] = deepcopy(config[field])

    for field in config_only:
        if field in config:
            result[field] = deepcopy(config[field])

    return result


def _capabilities_from_fields(effective, mapping):
    result = []

    for field, capability in mapping.items():
        if field in effective:
            result.append(capability)

    return result


def _copy_present(source, fields):
    if not isinstance(source, dict):
        return {}

    return {
        field: deepcopy(source[field])
        for field in fields
        if field in source
    }


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _outlet_sort_key(value):
    text = str(value or "")

    if len(text) > 1 and text[0] == "O" and text[1:].isdigit():
        return (0, int(text[1:]))

    return (1, text)
