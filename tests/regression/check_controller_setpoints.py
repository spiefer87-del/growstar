#!/usr/bin/env python3
"""Regression for controller setpoints in the existing device detail UI."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.controller_setpoints import (
    controller_schema,
    controller_schema_for_family,
    normalize_controller_setpoints,
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    fan = {
        "family": "fan",
        "capabilities": ["level", "oscillation"],
    }
    schema = controller_schema(fan)

    require(
        set(schema) == {"level", "oscillation"},
        "Ventilator-Controller stellt Level und Oszillation gemeinsam bereit",
    )
    require(
        schema["level"]["min"] == 1
        and schema["level"]["max"] == 10
        and schema["oscillation"]["min"] == 1
        and schema["oscillation"]["max"] == 10,
        "Ventilator-Sollwerte verwenden die beobachtete GGS-L1-bis-L10-Skala",
    )

    require(
        controller_schema_for_family("fan") == schema,
        "UI/API und Bridge können dieselbe zentrale Fan-Schemaquelle verwenden",
    )

    normalized = normalize_controller_setpoints(
        {"level": 7, "oscillation": 4},
        schema,
    )
    require(
        normalized == {"level": 7, "oscillation": 4},
        "Gültige Ventilator-Sollwerte werden normalisiert",
    )

    for bad in (
        {"level": 0, "oscillation": 4},
        {"level": 11, "oscillation": 4},
        {"level": 60, "oscillation": 4},
        {"level": 7, "oscillation": 99},
        {"level": 7, "unknown": 1},
    ):
        try:
            normalize_controller_setpoints(bad, schema)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"Ungültiger Sollwert akzeptiert: {bad}")
    print("✅ Bereichs- und Capability-Validierung blockiert ungültige Fan-Sollwerte einschließlich L60")

    light_schema = controller_schema({
        "family": "light",
        "capabilities": ["level"],
    })
    blower_schema = controller_schema({
        "family": "blower",
        "capabilities": ["level"],
    })

    require(
        light_schema["level"]["min"] == 0
        and light_schema["level"]["max"] == 100,
        "Lichtstärke bleibt auf 0 bis 100 Prozent modelliert",
    )
    require(
        blower_schema["level"]["min"] == 0
        and blower_schema["level"]["max"] == 100,
        "Gebläsestärke bleibt auf 0 bis 100 Prozent modelliert",
    )
    require(
        normalize_controller_setpoints({"level": 60}, light_schema) == {"level": 60}
        and normalize_controller_setpoints({"level": 60}, blower_schema) == {"level": 60},
        "60 bleibt für Licht und Gebläse gültig und wird nicht global auf Fan-Skala begrenzt",
    )

    route_text = (ROOT / "routes/device.py").read_text(encoding="utf-8")
    ui_text = (ROOT / "templates/device_control.html").read_text(encoding="utf-8")

    require(
        '"controller": _controller_context(runtime, device)' in route_text,
        "Bestehende Geräte-API liefert Controller-Zuordnung und Sollwertschema mit",
    )
    require(
        '"controller_setpoints"' in route_text
        and 'params["controller"] = normalized' in route_text,
        "Controller-Sollwerte werden atomar im bestehenden DEVICE_PARAMS-Pfad gespeichert",
    )
    require(
        'id="controller-card"' in ui_text
        and "Controller-Gerät" not in ui_text,
        "Bestehende Gerätekachel führt direkt auf die vorhandene Detailseite mit Controller-Sollwertkarte",
    )
    require(
        "js-controller-range" in ui_text
        and "js-controller-number" in ui_text,
        "Controller-Werte sind mobil per Slider und Zahleneingabe einstellbar",
    )
    require(
        "payload.controller_setpoints = readControllerSetpoints()" in ui_text,
        "Geräte-Speichern nimmt Controller-Sollwerte im selben Formular mit",
    )
    require(
        "SF.4D speichert diese Werte und sendet sie über die lokale Growstar-Bridge" in ui_text,
        "UI kennzeichnet den aktiven SF.4D-Schreibpfad ausdrücklich",
    )

    require(
        'id="controller-apply-feedback"' in ui_text
        and "controller_apply" in ui_text,
        "UI besitzt einen getrennten Rückkanal für lokalen Speicher- und Controller-Sendestatus",
    )

    require(
        "Controller-Werte an Spider Farmer gesendet" in ui_text
        and "Controller lokal gespeichert, aber nicht gesendet" in ui_text,
        "UI unterscheidet erfolgreichen Hardware-Sendestatus von lokaler Persistenz bei Bridge-Fehlern",
    )

    forbidden = (
        "setConfigField(",
        "asyncio.open_connection",
        "socket.send",
        "writer.write",
        "build_publish",
        "encode_publish",
        "requests.post(",
        "paho",
    )

    for path in (
        ROOT / "core/controller_setpoints.py",
        ROOT / "routes/device.py",
        ROOT / "templates/device_control.html",
    ):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            require(
                token not in text,
                f"{path.name} besitzt keinen Spider-Farmer-Command-/Transportpfad: {token}",
            )

    print("✅ Spider Farmer SF.4D.3 Controller-Sollwerte Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
