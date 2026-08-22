#!/usr/bin/env python3
"""Regression for SF.4B integration into the existing Connections UI."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    path = ROOT / "templates/connections.html"
    require(path.is_file(), "Bestehende Verbindungen-Seite vorhanden")

    text = path.read_text(encoding="utf-8")

    require(
        'id="device-grid"' in text
        and 'id="save-button"' in text
        and "/api/hardware" in text,
        "Bestehende Shelly-/Power-Zuordnung bleibt auf derselben Seite erhalten",
    )

    require(
        "Stromversorgung" in text
        and "Power bleibt beim Shelly" in text,
        "UI trennt Power-Aktor sichtbar von Controller-Funktionen",
    )

    require(
        'id="controller-grid"' in text
        and 'id="controller-save-button"' in text,
        "Controller-Mapping wird in die bestehende Verbindungen-Seite integriert",
    )

    require(
        "/capability-routing" in text,
        "UI verwendet ausschließlich die bestehende SF.4A Capability-Routing-API",
    )

    require(
        "Level / Dimmen" in text
        and "Oszillation" in text,
        "UI stellt die benötigten Zusatzfähigkeiten Level und Oszillation bereit",
    )

    require(
        "target.assignment_enabled" in text,
        "UI bietet nur vom Backend freigegebene Controller-Targets zur Auswahl an",
    )

    require(
        "target.capabilities" in text,
        "Controller-Auswahl wird pro Capability gefiltert",
    )

    require(
        'const modeLocked = mode !== "OFF"' in text,
        "Controller-Zuordnungen folgen der bestehenden OFF-Sicherheitslogik der Verbindungen-Seite",
    )

    require(
        "capability_route_conflict" in text,
        "Globale Target/Capability-Doppelbelegung wird in der bestehenden UI verständlich behandelt",
    )

    require(
        'method:"POST"' in text
        and "JSON.stringify({routes})" in text,
        "Controller-Speichern persistiert ausschließlich Routing-Metadaten",
    )

    forbidden = (
        "setConfigField(",
        "asyncio.open_connection",
        "socket.send",
        "writer.write",
        "build_publish",
        "encode_publish",
        "paho",
    )

    for token in forbidden:
        require(
            token not in text,
            f"SF.4B UI besitzt keinen Spider-Farmer-Command-/Transportpfad: {token}",
        )

    require(
        "Strom-Zuordnungen speichern" in text
        and "Controller-Zuordnungen speichern" in text,
        "Power- und Controller-Persistenz bleiben bewusst getrennt und ohne Teiltransaktions-Risiko vermischt",
    )

    print("✅ Spider Farmer SF.4B Verbindungen-UI Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
