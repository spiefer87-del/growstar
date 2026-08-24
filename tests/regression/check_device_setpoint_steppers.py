#!/usr/bin/env python3
"""Growstar 3.12.4 / UI.5 regression guard for controller +/- steppers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    script = (ROOT / "static/js/device-setpoint-stepper.js").read_text(encoding="utf-8")
    device = (ROOT / "templates/device_control.html").read_text(encoding="utf-8")

    require(
        "device-setpoint-stepper.js" in base,
        "Base lädt den generischen Controller-Stepper",
    )
    require(
        "?v=3.12.4-ui5" in base,
        "Static-Asset besitzt Cache-Buster für UI.5",
    )
    require(
        '".js-state-number, .js-controller-number"' in script,
        "Stepper unterstützt aktuelle und kompatible Controller-Zahlenfelder",
    )
    require(
        '".js-state-range, .js-controller-range"' in script,
        "Stepper koppelt sich an die vorhandenen Slider",
    )
    require(
        'button.textContent = direction < 0 ? "−" : "+"' in script,
        "Minus- und Plus-Tasten werden erzeugt",
    )
    require(
        'const step = Number.isFinite(parsedStep) && parsedStep > 0 ? parsedStep : 1;' in script,
        "Controller-Schema-Step bestimmt die Schrittweite",
    )
    require(
        "Math.max(minimum, Math.min(maximum, next))" in script,
        "Min/Max-Grenzen werden eingehalten",
    )
    require(
        'number.dispatchEvent(new Event("input", { bubbles: true }))' in script,
        "Stepper nutzt den bestehenden Growstar-Input-/Dirty-Pfad",
    )
    require(
        'grid-template-columns: 40px minmax(0, 1fr) 40px 70px' in script,
        "Mobile Darstellung bleibt kompakt",
    )
    require(
        'class="js-state-range"' in device and 'class="js-state-number"' in device,
        "Geräteoberfläche besitzt weiterhin die generischen Controller-Felder",
    )
    require(
        'onclick="saveDevice()"' in device,
        "Speichern bleibt bewusst separate Hauptaktion",
    )

    print("✅ Growstar 3.12.4 / UI.5 Stepper vollständig geprüft")


if __name__ == "__main__":
    main()
