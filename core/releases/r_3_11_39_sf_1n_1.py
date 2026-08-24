"""Growstar release node 3.11.39 / SF.1N.1."""

RELEASE = {
    "version": "3.11.39",
    "date": "2026-08-24",
    "phase": "SF.1N.1",
    "title": "Spider-Farmer-AP nach wlan0-Reconnect automatisch wiederherstellen",
    "summary": (
        "SF.1N.1 korrigiert das bestaetigte Autoconnect-Problem des dedizierten "
        "Growstar-SF NetworkManager-Profils. Der Network-Helper setzt bestehende "
        "und neue AP-Profile nicht mehr auf autoconnect=no, sondern auf yes. "
        "Dadurch kann NetworkManager Growstar-SF nach einer kurzen wlan0-"
        "Neuinitialisierung selbststaendig wieder aktivieren."
    ),
    "changes": (
        "Growstar-SF wird in _ensure_profile() mit connection.autoconnect=yes gespeichert.",
        "Bereits vorhandene Growstar-SF-Profile mit autoconnect=no werden beim naechsten Network-Service-Start automatisch korrigiert.",
        "AP-Modus, feste wlan0-Bindung, IPv4-shared-Netz, never-default und WPA2-Konfiguration bleiben unveraendert.",
        "nftables NAT-/Guard-Regeln werden nicht geaendert.",
        "Keine Aenderung an Spider-Farmer-MQTT, Sensoren, Ventilator-/Geblaese-Kommandos oder Shelly-Prioritaet.",
        "Neue Offline-Regression prueft vorhandene und neu angelegte NetworkManager-Profile.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_network_autoconnect.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
