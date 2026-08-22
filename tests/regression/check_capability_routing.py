#!/usr/bin/env python3
"""Regression for SF.4A provider-neutral capability routing."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.capability_routing import (
    CAPABILITY_LEVEL,
    CAPABILITY_OSCILLATION,
    CAPABILITY_POWER,
    CapabilityRouteConflictError,
    control_target_inventory,
    normalize_route_patch,
    routing_snapshot_for_config,
    spiderfarmer_control_targets,
)


CONTROLLER = "744dbd59d734"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def sample_controllers():
    return [{
        "id": CONTROLLER,
        "pid": "744DBD59D734",
        "online": True,
        "devices": [
            {
                "id": "light",
                "label": "Licht 1",
                "capabilities": ["power", "level", "mode"],
            },
            {
                "id": "fan",
                "label": "Ventilator",
                "capabilities": [
                    "power",
                    "level",
                    "mode",
                    "oscillation_level",
                ],
            },
            {
                "id": "blower",
                "label": "Gebläse",
                "capabilities": ["power", "level", "mode"],
            },
            {
                "id": "outlet",
                "label": "Steckdosenleiste",
                "capabilities": ["channels"],
                "channels": [
                    {
                        "id": "outlet:O1",
                        "label": "O1",
                        "capabilities": ["power", "mode"],
                    }
                ],
            },
        ],
    }]


def target_by_device(targets, device_id):
    return next(
        item
        for item in targets
        if item["device_id"] == device_id
    )


def main():
    targets = spiderfarmer_control_targets(
        sample_controllers()
    )

    require(
        len(targets) == 4,
        "SF.4A erkennt Licht, Fan, Blower und zukünftigen Outlet-Power-Target",
    )

    light = target_by_device(targets, "light")
    fan = target_by_device(targets, "fan")
    blower = target_by_device(targets, "blower")
    outlet = target_by_device(targets, "outlet:O1")

    require(
        light["capabilities"] == [CAPABILITY_LEVEL],
        "Spider-Farmer-Licht wird nur als Modulationsziel für level angeboten",
    )

    require(
        set(fan["capabilities"])
        == {CAPABILITY_LEVEL, CAPABILITY_OSCILLATION},
        "Spider-Farmer-Fan bietet level und oscillation unabhängig an",
    )

    require(
        blower["capabilities"] == [CAPABILITY_LEVEL],
        "Spider-Farmer-Blower bietet level als eigene Capability an",
    )

    require(
        outlet["capabilities"] == [CAPABILITY_POWER]
        and outlet["assignment_enabled"] is False
        and outlet["role"] == "future_power_actor",
        "Spider-Farmer-Steckdose ist als zukünftiger Power-Aktor modelliert, aber noch gesperrt",
    )

    require(
        all(item["writable"] is False for item in targets),
        "SF.4A markiert sämtliche Spider-Farmer-Ziele weiterhin als nicht schreibbar",
    )

    inventory = control_target_inventory(
        sample_controllers()
    )

    require(
        inventory["phase"] == "SF.4A"
        and inventory["read_only"] is True
        and inventory["command_transport_enabled"] is False,
        "Control-Target-Inventar besitzt ausdrücklich noch keinen Command-Transport",
    )

    fan_target = fan["id"]
    blower_target = blower["id"]

    normalized = normalize_route_patch(
        {
            "routes": {
                # Ein Spider-Farmer-Fan ist nicht fest an Growstars "vent"
                # gekoppelt. Derselbe physische Controller darf einem beliebigen
                # logisch kompatiblen Growstar-Gerät zugeordnet werden.
                "vent2": {
                    "level": {"target_id": fan_target},
                    "oscillation": {"target_id": fan_target},
                },
                "fan": {
                    "level": {"target_id": blower_target},
                },
            }
        },
        targets,
    )

    require(
        normalized["vent2"]["level"]["target_id"] == fan_target
        and normalized["vent2"]["oscillation"]["target_id"] == fan_target,
        "Fan-Controller kann frei einem anderen kompatiblen Growstar-Aktor zugeordnet werden",
    )

    require(
        normalized["fan"]["level"]["target_id"] == blower_target,
        "Blower-Level kann unabhängig einem Growstar-Aktor zugeordnet werden",
    )

    try:
        normalize_route_patch(
            {
                "light": {
                    "oscillation": {
                        "target_id": fan_target,
                    }
                }
            },
            targets,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Licht darf keine logische oscillation-Capability erhalten"
        )
    print("✅ Logische Gerätefähigkeiten verhindern semantisch falsche Zuordnungen")

    try:
        normalize_route_patch(
            {
                "vent": {
                    "oscillation": {
                        "target_id": blower_target,
                    }
                }
            },
            targets,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Blower darf nicht als Oszillationsziel akzeptiert werden"
        )
    print("✅ Physisches Target muss die angeforderte Capability wirklich anbieten")

    try:
        normalize_route_patch(
            {
                "vent": {
                    "level": {"target_id": fan_target},
                },
                "vent2": {
                    "level": {"target_id": fan_target},
                },
            },
            targets,
        )
    except CapabilityRouteConflictError:
        pass
    else:
        raise AssertionError(
            "Dasselbe Target/Capability darf nicht zwei Aktoren gleichzeitig gehören"
        )
    print("✅ Target/Capability-Konflikte werden vor Persistenz blockiert")

    cfg = {
        "IP_LIGHT": "192.168.178.70",
        "RELAY_LIGHT": 0,
        "CAPABILITY_ROUTES": {
            "light": {
                "level": {
                    "provider": "spiderfarmer",
                    "target_id": light["id"],
                }
            },
            "vent2": {
                "level": {
                    "provider": "spiderfarmer",
                    "target_id": fan_target,
                },
                "oscillation": {
                    "provider": "spiderfarmer",
                    "target_id": fan_target,
                },
            },
        },
    }

    snapshot = routing_snapshot_for_config(
        cfg,
        targets=targets,
    )

    light_routes = snapshot["devices"]["light"]["routes"]
    vent2_routes = snapshot["devices"]["vent2"]["routes"]

    require(
        light_routes["power"]["provider"] == "shelly"
        and light_routes["power"]["configured"] is True
        and light_routes["power"]["editable_here"] is False,
        "Bestehender Shelly bleibt alleinige Power-Zuordnung im SF.4A-Modell",
    )

    require(
        light_routes["level"]["provider"] == "spiderfarmer",
        "Licht-Dimmung liegt unabhängig vom Shelly auf dem Controller-Target",
    )

    require(
        vent2_routes["level"]["target_id"] == fan_target
        and vent2_routes["oscillation"]["target_id"] == fan_target,
        "Level und Oszillation werden als getrennte Capability-Routen dargestellt",
    )

    require(
        snapshot["command_transport_enabled"] is False
        and snapshot["read_only_control_plane"] is True,
        "Routing-Snapshot ist Konfigurationsmodell ohne Hardware-Schreibpfad",
    )

    source_files = (
        ROOT / "core/capability_routing.py",
        ROOT / "routes/capability_routing.py",
    )

    forbidden = (
        "asyncio.open_connection",
        "socket.send",
        "writer.write",
        "build_publish",
        "encode_publish",
        "setConfigField(",
        "requests.post(",
        "requests.get(",
        "paho",
    )

    for path in source_files:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))

        for token in forbidden:
            require(
                token not in source,
                f"{path.name} besitzt keinen Hardware-/Command-Transport: {token}",
            )

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    require(
        "register_capability_routing_routes(app)" in app_source,
        "Capability-Routing-API wird von Growstar registriert",
    )

    route_source = (
        ROOT / "routes/capability_routing.py"
    ).read_text(encoding="utf-8")

    require(
        '"/api/control-targets"' in route_source
        and '"/api/tents/<tent_id>/capability-routing"' in route_source,
        "SF.4A stellt Target-Inventar und stationsbezogene Routing-API bereit",
    )

    release_path = (
        ROOT / "core/releases/r_3_11_12_sf_4a.py"
    )

    require(
        release_path.is_file(),
        "SF.4A besitzt genau einen neuen Einzeldatei-Release-Node",
    )

    print(
        "✅ Spider Farmer SF.4A Capability-Routing Regression vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
