#!/usr/bin/env python3
"""Statische Regression für das exklusive Verbindungs-Akkordeon."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "connections.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    text = TEMPLATE.read_text(encoding="utf-8")

    for module_id, panel_id in (
        ("growcam-connection", "camera-connection-panel"),
        ("power-connections", "power-connection-panel"),
        ("controller-connections", "controller-connection-panel"),
    ):
        require(
            f'id="{module_id}"' in text
            and f'aria-controls="{panel_id}"' in text
            and f'id="{panel_id}" hidden' in text,
            f"Modul {module_id} besitzt einen geschlossenen, verknüpften Bereich",
        )

    require(
        'class="connection-toggle"' in text
        and text.count('aria-expanded="false"') == 3,
        "Alle drei Verbindungsgruppen besitzen zugängliche Klappschalter",
    )
    require(
        "connectionModules.forEach" in text
        and "setConnectionModuleState(item, item === module)" in text,
        "Beim Öffnen eines Moduls werden alle anderen Module geschlossen",
    )
    require(
        "if(wasOpen)" in text
        and "setConnectionModuleState(module, false)" in text,
        "Das aktuell geöffnete Modul lässt sich wieder vollständig schließen",
    )
    require(
        'openConnectionModule(requestedModule || "power")' in text,
        "Stromversorgung öffnet standardmäßig und URL-Anker wählen ihr Zielmodul",
    )
    require(
        ".connection-panel>.actions{position:sticky" in text,
        "Speicheraktionen bleiben innerhalb eines langen geöffneten Moduls erreichbar",
    )

    print("✅ CONNECTIONS.ACCORDION.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
