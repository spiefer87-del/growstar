#!/usr/bin/env python3
"""Regression for the corrected SF.4B.1 Connections UI."""

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
        and "Strom-Zuordnungen speichern" in text,
        "Bestehender Shelly-/Power-Bereich bleibt unverändert vorhanden",
    )

    require(
        'class="cap-select js-controller"' in text,
        "Pro Growstar-Gerät existiert genau eine Controller-Auswahl",
    )

    require(
        "Level / Dimmen" in text
        and "Oszillation" in text,
        "Controller-Funktionsumfang wird sichtbar beschrieben",
    )

    require(
        "Funktionen des gewählten Controllers werden immer gemeinsam diesem Gerät zugeordnet." in text,
        "UI erklärt die unteilbare Geräte-Zuordnung ausdrücklich",
    )

    require(
        "controller.family" in text
        and "required_capabilities" in text,
        "UI filtert Controller nach Gerätefamilie und vollständigem Funktionssatz",
    )

    require(
        'BELEGT:' in text
        and 'disabled data-occupied="1"' in text,
        "Bereits einem anderen Gerät zugeordneter Controller ist sichtbar aber gesperrt",
    )

    require(
        'JSON.stringify({controllers})' in text,
        "UI speichert ein gerätegebundenes Controller-Mapping",
    )

    require(
        "js-capability" not in text,
        "Alte getrennte Capability-Dropdowns wurden vollständig entfernt",
    )

    require(
        'const modeLocked = mode !== "OFF"' in text,
        "Bestehende OFF-Sicherheitslogik bleibt für Controller-Wechsel erhalten",
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
            f"SF.4B.1 UI besitzt weiterhin keinen Command-Transport: {token}",
        )

    print("✅ Spider Farmer SF.4B.1 Geräte-Zuordnungs-UI Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
