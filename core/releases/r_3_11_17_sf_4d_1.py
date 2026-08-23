"""Growstar release node 3.11.17 / SF.4D.1."""

RELEASE = {
    "version": "3.11.17",
    "date": "2026-08-23",
    "phase": "SF.4D.1",
    "title": "Controller-Sollwert-Regression auf aktiven SF.4D-Schreibpfad aktualisiert",
    "summary": (
        "Der bestehende SF.4C-Regressionscheck erwartete noch ausdrücklich, "
        "dass Controller-Sollwerte nicht an Spider Farmer gesendet werden. "
        "Seit SF.4D ist diese Annahme absichtlich veraltet. Der Test wird deshalb "
        "auf den neuen kontrollierten Schreibpfad aktualisiert, ohne die fachlichen "
        "Sollwert-, Bereichs- oder Transportgrenzen abzuschwächen."
    ),
    "changes": (
        "check_controller_setpoints.py erwartet nicht mehr den historischen SF.4C-Hinweis 'sendet noch nicht'.",
        "Der Test verlangt stattdessen die sichtbare SF.4D-Kennzeichnung des aktiven lokalen Bridge-Schreibpfads.",
        "Die UI muss weiterhin einen getrennten controller_apply-Rückkanal für den tatsächlichen Sendestatus besitzen.",
        "Erfolgreiches Senden und 'lokal gespeichert, aber nicht gesendet' müssen als getrennte Zustände dargestellt werden.",
        "Die bestehenden Sollwertgrenzen für Fan, Licht und Blower bleiben unverändert bestehen.",
        "Die bestehenden statischen Guards bleiben erhalten: routes/device.py und die UI dürfen keinen direkten MQTT-/Socket-/setConfigField-Transport implementieren.",
        "Der eigentliche Spider-Farmer-Command-Transport bleibt ausschließlich im SF.4D-Bridge-/Provider-Pfad.",
    ),
    "tests": (
        "check_controller_setpoints.py passt jetzt semantisch zu SF.4D.",
        "check_spiderfarmer_command_path.py bleibt der maßgebliche Regressionstest für den tatsächlichen Command-Pfad.",
        "Beide Tests ergänzen sich: Geräte-/Sollwertmodell einerseits, beobachtetes GGS-Command-Template und MQTT-Injektion andererseits.",
    ),
}
