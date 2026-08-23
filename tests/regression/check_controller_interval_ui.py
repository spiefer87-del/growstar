#!/usr/bin/env python3
"""Static regression for CTRL.2 interval-state UI."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "device_control.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    text = TEMPLATE.read_text(encoding="utf-8")

    require(
        'id="interval-a-minutes"' in text
        and 'id="interval-b-minutes"' in text,
        "Intervall besitzt getrennte Dauerfelder für Phase A und B",
    )
    require(
        'id="interval-a-power"' in text
        and 'id="interval-b-power"' in text,
        "Intervall besitzt getrennte Shelly-Power-Zustände A und B",
    )
    require(
        "stateSetpointField" in text
        and 'data-state="${escapeHtml(stateName)}"' in text,
        "Controllerwerte werden pro Intervallzustand getrennt gerendert",
    )
    require(
        "control_states:" in text
        and "interval_a:" in text
        and "interval_b:" in text,
        "UI speichert die CTRL.1-Struktur control_states.interval_a/b",
    )
    require(
        "minutesToSeconds" in text
        and "secondsToMinutes" in text,
        "Minuten-UI bleibt mit der bestehenden Sekunden-Regellogik kompatibel",
    )
    require(
        'document.getElementById("interval-b-power").value = b.power === true ? "on" : "off"' in text,
        "Bestehende Intervalle bleiben standardmäßig in Phase B AUS",
    )
    require(
        "Controller-Werte dürfen den Shelly-Powerzustand niemals überstimmen" in text
        and "Shelly besitzt immer" in text,
        "Shelly-Priorität ist in der Bedienoberfläche eindeutig dokumentiert",
    )
    require(
        'controllerCard.classList.contains("visible") && bPower' in text,
        "Phase B speichert Controllerwerte nur bei Shelly-Power EIN",
    )

    print("✅ CTRL.2 Intervall-UI vollständig erfolgreich")


if __name__ == "__main__":
    main()
