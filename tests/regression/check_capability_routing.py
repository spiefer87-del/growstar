#!/usr/bin/env python3
"""Regression for SF.4B.1 device-bound controller assignment."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_routing import (
    CAPABILITY_LEVEL,
    CAPABILITY_OSCILLATION,
    CapabilityRouteConflictError,
    annotate_target_usage,
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
                "channels": [{
                    "id": "outlet:O1",
                    "label": "O1",
                    "capabilities": ["power", "mode"],
                }],
            },
        ],
    }]


def by_device(targets, device_id):
    return next(
        item for item in targets
        if item["device_id"] == device_id
    )


def main():
    targets = spiderfarmer_control_targets(sample_controllers())

    light = by_device(targets, "light")
    fan = by_device(targets, "fan")
    blower = by_device(targets, "blower")
    outlet = by_device(targets, "outlet:O1")

    require(
        fan["family"] == "fan"
        and set(fan["capabilities"]) == {
            CAPABILITY_LEVEL,
            CAPABILITY_OSCILLATION,
        },
        "Spider-Farmer-Ventilator wird als EIN Controller-Gerät mit Level und Oszillation modelliert",
    )

    require(
        light["family"] == "light"
        and light["capabilities"] == [CAPABILITY_LEVEL],
        "Spider-Farmer-Licht ist ein eigenes Light-Controller-Gerät",
    )

    require(
        blower["family"] == "blower"
        and blower["capabilities"] == [CAPABILITY_LEVEL],
        "Spider-Farmer-Gebläse ist ein eigenes Blower-Controller-Gerät",
    )

    require(
        outlet["assignment_enabled"] is False
        and outlet["role"] == "future_power_actor",
        "Spider-Farmer-Steckdose bleibt zukünftiger gesperrter Power-Aktor",
    )

    normalized = normalize_route_patch(
        {
            "controllers": {
                "vent": {
                    "target_id": fan["id"],
                },
                "fan": {
                    "target_id": blower["id"],
                },
                "light": {
                    "target_id": light["id"],
                },
            }
        },
        targets,
    )

    require(
        normalized["vent"]["target_id"] == fan["id"],
        "Ventilator erhält den kompletten physischen Fan-Controller",
    )

    require(
        normalized["fan"]["target_id"] == blower["id"],
        "Abluft/Lüfter erhält den kompletten Blower-Controller",
    )

    try:
        normalize_route_patch(
            {
                "routes": {
                    "vent": {
                        "level": {"target_id": fan["id"]},
                        "oscillation": {"target_id": light["id"]},
                    }
                }
            },
            targets,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Level und Oszillation dürfen nicht auf zwei Controller verteilt werden"
        )
    print("✅ Split-Zuordnung von Level und Oszillation wird ausdrücklich blockiert")

    try:
        normalize_route_patch(
            {"controllers": {"vent": {"target_id": blower["id"]}}},
            targets,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Blower darf keinen Ventilator ersetzen, dem Oszillation fehlt"
        )
    print("✅ Controller-Familie und vollständiger Funktionssatz müssen passen")

    try:
        normalize_route_patch(
            {
                "controllers": {
                    "vent": {"target_id": fan["id"]},
                    "vent2": {"target_id": fan["id"]},
                }
            },
            targets,
        )
    except CapabilityRouteConflictError:
        pass
    else:
        raise AssertionError(
            "Ein physisches Controller-Gerät darf nicht zwei Growstar-Geräten gehören"
        )
    print("✅ Physisches Controller-Gerät ist global als Einheit eindeutig")

    cfg = {
        "IP_VENT": "192.168.178.70",
        "RELAY_VENT": 0,
        "CONTROLLER_ASSIGNMENTS": {
            "vent": {
                "provider": "spiderfarmer",
                "target_id": fan["id"],
            }
        },
    }

    snapshot = routing_snapshot_for_config(cfg, targets=targets)
    vent = snapshot["devices"]["vent"]

    require(
        vent["power"]["provider"] == "shelly"
        and vent["power"]["configured"] is True,
        "Shelly bleibt unverändert der Power-Aktor",
    )

    require(
        vent["controller"]["target_id"] == fan["id"]
        and set(vent["controller"]["effective_capabilities"]) == {
            CAPABILITY_LEVEL,
            CAPABILITY_OSCILLATION,
        },
        "Controller-Zuordnung bringt Level und Oszillation gemeinsam mit",
    )

    legacy_cfg = {
        "CAPABILITY_ROUTES": {
            "vent": {
                "level": {
                    "provider": "spiderfarmer",
                    "target_id": fan["id"],
                },
                "oscillation": {
                    "provider": "spiderfarmer",
                    "target_id": fan["id"],
                },
            }
        }
    }

    migrated = routing_snapshot_for_config(
        legacy_cfg,
        targets=targets,
    )

    require(
        migrated["devices"]["vent"]["controller"]["target_id"] == fan["id"],
        "Bestehende saubere SF.4B-Zuordnung wird automatisch als Geräte-Zuordnung gelesen",
    )

    owners = annotate_target_usage(
        targets,
        {
            fan["id"]: {
                "tent_id": "tent_1",
                "device": "vent",
            }
        },
    )
    used_fan = by_device(owners, "fan")

    require(
        used_fan["in_use"] is True
        and used_fan["owner"]["device"] == "vent",
        "Belegung gilt für das gesamte Controller-Gerät und nicht pro Capability",
    )

    forbidden = (
        "asyncio.open_connection",
        "socket.send",
        "writer.write",
        "build_publish",
        "encode_publish",
        "setConfigField(",
        "requests.post(",
        "paho",
    )

    source = (ROOT / "core/capability_routing.py").read_text(encoding="utf-8")
    for token in forbidden:
        require(
            token not in source,
            f"Routing-Layer besitzt weiterhin keinen Command-Transport: {token}",
        )

    print("✅ Spider Farmer SF.4B.1 Geräte-Controller-Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
