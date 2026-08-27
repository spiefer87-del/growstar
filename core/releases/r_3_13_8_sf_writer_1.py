"""Growstar release node 3.13.8 / SF Writer Reconnect Guard."""

RELEASE = {
    "version": "3.13.8",
    "date": "2026-08-26",
    "phase": "SF.WRITER.1",
    "title": "Spider-Farmer Writer bei Reconnect stabil halten",
    "summary": (
        "Eine alte Spider-Farmer-TLS-Verbindung konnte beim verspäteten Cleanup "
        "den bereits neu registrierten Writer derselben Controller-ID löschen. "
        "Dadurch blieb MQTT-Readback aktiv, während Steuerbefehle mit "
        "'Controller ist nicht aktiv mit der Bridge verbunden' abgewiesen wurden."
    ),
    "changes": (
        "Writer-Cleanup prüft jetzt die Identität der schließenden Verbindung.",
        "Eine alte/stale Verbindung darf einen neu registrierten Writer derselben Controller-ID nicht mehr entfernen.",
        "Subscriptions der neuen Verbindung bleiben bei stale Cleanup erhalten.",
        "Normaler Disconnect entfernt den eigenen Writer und seine Subscriptions weiterhin vollständig.",
        "Keine Änderung an Fan-, Blower-, Light- oder Power-Strip-Payloads.",
        "Keine Änderung an Shelly, Grow-Control-Regelung, Safety oder Netzwerk.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_topic_ps1_3.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
