#!/usr/bin/env python3
"""Regression checks for Raspberry-to-Pico VIVOSUN source handover."""

from copy import deepcopy
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
    import core.state as controller_state
    from core.hardware.vivosun import (
        canonical_source_id,
        source_id_from_address,
    )
    from core.mqtt_sensor_devices import clear_mqtt_sensor_devices
    from core.sensor_sources import get_sensor_source, update_sensor_source

    address = "EE:65:C7:00:00:00"
    canonical = source_id_from_address(address, "main")
    require(
        canonical == "vivosun:ee65c7000000:main"
        and canonical_source_id(
            "hardware:vivosun_ee65c7000000:main"
        ) == canonical
        and canonical_source_id(
            "mqtt:vivosun_ee65c7000000_main"
        ) == canonical,
        "Raspberry- und Pico-IDs werden auf dieselbe VIVOSUN-Quelle abgebildet",
    )

    previous_sources = deepcopy(controller_state.live_state.get("sensor_sources", {}))
    try:
        controller_state.live_state["sensor_sources"] = {}
        clear_mqtt_sensor_devices()

        update_sensor_source(
            canonical,
            label="VIVOSUN AeroLab · Interner Sensor",
            source_type="hardware",
            temperature=19.0,
            humidity=52.0,
        )
        require(
            get_sensor_source(
                "hardware:vivosun_ee65c7000000:main"
            )["temperature"] == 19.0,
            "Bestehende Raspberry-Zuweisungen lesen die kanonische Quelle weiter",
        )

        routes_source = (ROOT / "routes" / "sensors.py").read_text(
            encoding="utf-8"
        )
        mqtt_source = (ROOT / "services" / "mqtt.py").read_text(
            encoding="utf-8"
        )
        require(
            "def _merge_source(sources, source):" in routes_source
            and "source_id = vivosun_source_id(address, channel)" in mqtt_source,
            "Sensorenseite zeigt denselben AeroLab-Kanal nur einmal",
        )
        require(
            'source_id.startswith("vivosun:aabbccddeeff:")' in routes_source,
            "Sensorenseite blendet die alte Beispiel-MAC vollständig aus",
        )
    finally:
        clear_mqtt_sensor_devices()
        controller_state.live_state["sensor_sources"] = previous_sources

    print("✅ VIVOSUN-Quellenübergabe vollständig erfolgreich")


if __name__ == "__main__":
    main()
