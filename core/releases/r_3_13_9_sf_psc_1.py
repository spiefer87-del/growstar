"""Growstar release node 3.13.9 / SF.PSC1."""

RELEASE = {
    "version": "3.13.9",
    "date": "2026-08-27",
    "phase": "SF.PSC1",
    "title": "C5B8 Controller über PS5-Transport steuern",
    "summary": (
        "Für tatsächlich als PS/PS5/PS10 beobachtete PIDs werden Light-, Fan- "
        "und Blower-Controllerbefehle über den bereits validierten Power-Strip-"
        "DOWN-Transport gesendet, während D734/CB unverändert bleibt."
    ),
    "changes": (
        "C5B8 Light/Fan/Blower verwenden den beobachteten PS5-DOWN-Transport.",
        "Der bestehende Controller-Payload-Compiler bleibt unverändert.",
        "Fan-Oszillation bleibt über oscillaton->shakeLevel erhalten.",
        "D734 und andere CB/GGS-Controller bleiben auf dem bestehenden Command-Pfad.",
        "O1-O5 bleiben auf dem separaten Power-Strip-Outlet-Pfad.",
        "Keine Änderung an Shelly, Regelung, Safety oder Netzwerk.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_ps_controller_transport.py",
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_topic_ps1_3.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
