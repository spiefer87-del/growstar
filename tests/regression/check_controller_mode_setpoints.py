#!/usr/bin/env python3
"""Regression for CTRL.3 mode-specific controller setpoints."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.controller_states import resolve_control_state


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    params = {
        "controller": {"level": 6},
        "control_states": {
            "on": {"power": True, "controller": {"level": 7}},
            "time": {"power": True, "controller": {"level": 5}},
            "env": {"power": True, "controller": {"level": 4}},
            "interval_a": {"power": True, "controller": {"level": 8}},
            "interval_b": {"power": True, "controller": {"level": 3}},
        },
    }

    require(
        resolve_control_state(params, "on")["controller"] == {"level": 7},
        "Dauerbetrieb besitzt einen eigenen Controller-Sollwert",
    )
    require(
        resolve_control_state(params, "time")["controller"] == {"level": 5},
        "Zeitsteuerung besitzt einen eigenen Controller-Sollwert",
    )
    require(
        resolve_control_state(params, "env")["controller"] == {"level": 4},
        "ENV besitzt einen eigenen Controller-Sollwert",
    )
    require(
        resolve_control_state(params, "interval_a")["controller"] == {"level": 8}
        and resolve_control_state(params, "interval_b")["controller"] == {"level": 3},
        "Intervall A/B bleiben getrennte Controller-Zustände",
    )

    legacy = {"controller": {"level": 6}}
    for state in ("on", "time", "env", "interval_a"):
        require(
            resolve_control_state(legacy, state)["controller"] == {"level": 6},
            f"Legacy-Sollwert bleibt als Fallback für {state} kompatibel",
        )

    require(
        resolve_control_state(params, "off") == {
            "power": False,
            "controller": {},
        },
        "OFF bleibt controllerfrei und damit Shelly-autoritativ",
    )

    template = (ROOT / "templates/device_control.html").read_text(encoding="utf-8")

    require(
        'id="controller-setpoints"' not in template,
        "Globaler Controller-Slider wurde aus dem Kopfbereich entfernt",
    )
    require(
        'id="on-controller"' in template
        and 'id="time-controller"' in template
        and 'id="env-controller"' in template,
        "Dauerbetrieb, Zeitsteuerung und ENV besitzen eigene Sliderbereiche",
    )
    require(
        'id="interval-a-controller"' in template
        and 'id="interval-b-controller"' in template,
        "Intervall A/B behalten ihre eigenen Sliderbereiche",
    )
    require(
        "payload.controller_setpoints" not in template,
        "Speichern sendet keinen globalen Controller-Sollwert mehr",
    )
    require(
        "Power / Ein-Aus bleibt immer beim Shelly" in template,
        "Shelly-Priorität bleibt sichtbar dokumentiert",
    )

    print("✅ CTRL.3 Modus-Sollwerte vollständig erfolgreich")


if __name__ == "__main__":
    main()
