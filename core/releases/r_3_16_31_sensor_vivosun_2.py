"""Growstar 3.16.31 / SENSOR.VIVOSUN.2 release metadata."""

RELEASE = {
    "version": "3.16.31",
    "date": "2026-09-10",
    "phase": "SENSOR.VIVOSUN.2",
    "title": "Namenlose VS-THB1S zuverlässig per Raspberry-BLE erkennen",
    "summary": (
        "Growstar erkennt neuere VIVOSUN AeroLab VS-THB1S auch dann, wenn sie "
        "nicht mehr mit dem lokalen Bluetooth-Namen ThermoBeacon2 werben. "
        "Die Erkennung verwendet zusätzlich die beobachtete, eng begrenzte "
        "BLE-Service- und ManufacturerData-Signatur."
    ),
    "changes": (
        "Die Raspberry-Suche fordert mit Bleak 0.22.3 vollständige AdvertisementData an.",
        "Der bisherige Bluetooth-Name ThermoBeacon2 bleibt vollständig kompatibel.",
        "Namenlose VS-THB1S werden über Service UUID FFF0, ManufacturerData 0x0019 beziehungsweise 0x8019 und exakt 20 Byte Nutzdaten erkannt.",
        "Die Geräteauflösung vor dem GATT-Read verwendet dieselbe Signaturprüfung wie die Discovery.",
        "RSSI und lokaler Name werden direkt aus den Bleak-AdvertisementData übernommen.",
        "Fremde Geräte mit unvollständigen Daten oder ohne passende FFF0-Servicekennung werden weiterhin abgewiesen.",
        "Die Hardwareoberfläche erklärt die kompatible Namens- und Signaturerkennung korrekt.",
        "Pico-W-Firmware, WLAN-Zugangsdaten, Pairing, Konfiguration und Relaissteuerung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_vivosun_thb1s_integration.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 -m compileall -q core/hardware/vivosun.py services/hardware.py core/releases/r_3_16_31_sensor_vivosun_2.py",
    ),
}
