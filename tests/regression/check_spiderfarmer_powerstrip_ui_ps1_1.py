#!/usr/bin/env python3
"""Growstar 3.13.4 / SF.PS1.1 UI classification regression."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "templates" / "spiderfarmer.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    text = UI.read_text(encoding="utf-8")

    require(
        'function isPowerStrip(controller)' in text,
        "Power-Strip-Erkennung besitzt eine zentrale Helper-Funktion",
    )
    require(
        'prefix === "PS" || hasOutletDevice(controller)' in text,
        "PS-Prefix bleibt kanonisch und Outlet-Inventar dient als Read-UI-Fallback",
    )
    require(
        'controllers.filter(isPowerStrip).length' in text,
        "Statuszeile zählt Power Strips über dieselbe zentrale Erkennung",
    )
    require(
        'const isPS = isPowerStrip(controller);' in text,
        "Controller-Karte verwendet dieselbe Power-Strip-Erkennung",
    )
    require(
        'isPowerStrip(controller) &&' in text,
        "Outlet-Steuerbarkeit verwendet dieselbe Power-Strip-Erkennung",
    )
    require(
        'function normalizedOutletChannels(channels)' in text,
        "Outlet-Kanäle werden vor dem Rendern normalisiert",
    )
    require(
        'unique.set(name' in text and 'O${number}' in text,
        "O1..O10 werden in der UI eindeutig dedupliziert",
    )
    require(
        'cache:"no-store"' in text,
        "Spider-Farmer-Readback wird ohne Browser-Cache abgefragt",
    )
    require(
        'SF.PS1.1' in text,
        "UI besitzt einen sichtbaren SF.PS1.1 Build-Marker",
    )

    print("✅ Growstar 3.13.4 / SF.PS1.1 vollständig geprüft")


if __name__ == "__main__":
    main()
