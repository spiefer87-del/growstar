#!/usr/bin/env python3
"""Statische Regression für das exklusive Hardware-Akkordeon."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "devices.html"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    text = TEMPLATE.read_text(encoding="utf-8")

    for module_id, panel_id in (
        ("hardware-new-devices", "hardware-new-devices-panel"),
        ("hardware-sensors", "hardware-sensors-panel"),
        ("hardware-actuators", "hardware-actuators-panel"),
    ):
        require(
            f'id="{module_id}"' in text
            and f'aria-controls="{panel_id}"' in text
            and f'id="{panel_id}" hidden' in text,
            f"Hardware-Modul {module_id} besitzt einen verknüpften Klappbereich",
        )

    new_start = text.index('id="hardware-new-devices-panel"')
    sensor_start = text.index('id="hardware-sensors-panel"')
    actuator_start = text.index('id="hardware-actuators-panel"')
    status_start = text.index('class="hardware-status-heading"')
    require(
        new_start
        < text.index('id="scan-gateway"')
        < text.index('id="scan-provisioning"')
        < text.index('id="scan-vivosun"')
        < sensor_start,
        "Neue Geräte bündelt LAN-, Shelly- und VIVOSUN-Suche",
    )
    require(
        sensor_start
        < text.index('id="device-grid"')
        < text.index('id="mqtt-device-grid"')
        < text.index('id="spiderfarmer-sensor-grid"')
        < actuator_start,
        "Sensorbereich bündelt Bluetooth, MQTT und Spider Farmer",
    )
    require(
        actuator_start < text.index('id="actuator-grid"') < status_start,
        "Aktoren bilden den dritten Klappbereich",
    )
    require(
        text.index('</div>\n\n\n\n<h3 class="hardware-status-heading"') < status_start,
        "Hardware-Status bleibt außerhalb des Akkordeons permanent sichtbar",
    )
    require(
        "hardwareModules.forEach" in text
        and "setHardwareModuleState(item, item === module)" in text,
        "Beim Öffnen eines Hardware-Moduls schließen alle anderen",
    )
    require(
        "if(wasOpen)" in text
        and "setHardwareModuleState(module, false)" in text,
        "Ein geöffnetes Hardware-Modul lässt sich vollständig schließen",
    )
    require(
        'if(requestedHardwareModule) openHardwareModule(requestedHardwareModule)' in text
        and '|| "new-devices"' not in text,
        "Normalansicht startet geschlossen; URL-Anker öffnen gezielt ihr Modul",
    )
    require(
        'id="gateway-inventory-toggle"' in text
        and 'aria-expanded="false"' in text
        and 'id="gateway-inventory-panel" class="gateway-inventory-panel" hidden' in text
        and 'id="discovered-gateway-grid"' in text,
        "Gefundene Shelly-Geräte liegen in einem geschlossenen Untermenü",
    )
    require(
        "gatewayInventoryPanel.hidden = !open" in text
        and 'document.getElementById("gateway-inventory-count")' in text
        and "discoveredGrid.appendChild" in text,
        "Shelly-Untermenü ist klappbar, zeigt die Trefferzahl und enthält die Geräte",
    )

    print("✅ HARDWARE.ACCORDION.2 vollständig erfolgreich")


if __name__ == "__main__":
    main()
