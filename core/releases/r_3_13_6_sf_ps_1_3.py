"""Growstar release node 3.13.6 / SF.PS1.3."""

RELEASE = {
    "version": "3.13.6",
    "date": "2026-08-26",
    "phase": "SF.PS1.3",
    "title": "PS5-DOWN-Topic sicher aus beobachtetem UP-Prefix ableiten",
    "summary": (
        "Der reale PS5 publiziert auf PS5/API/UP, stellt Growstar aber keine "
        "eindeutige DOWN-Subscription bereit. Growstar übernimmt jetzt das "
        "Prefix-symmetrische Verfahren der Referenz-Bridge."
    ),
    "changes": (
        "PS, PS5 und PS10 werden als bekannte Power-Strip-Topicfamilie validiert.",
        "Eine echte DOWN-Subscription hat weiterhin Vorrang.",
        "Ohne DOWN-Subscription darf nur ein eindeutig beobachtetes UP-Topic derselben PID als Grundlage dienen.",
        "Aus SF/GGS/PS5/API/UP/<PID> wird ausschließlich SF/GGS/PS5/API/DOWN/<PID> abgeleitet.",
        "Mehrere Prefixe, fremde PID oder CB bleiben fail-closed.",
        "Outlet-Payload, Shelly, GGS-Controller, Regelung und Safety bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_powerstrip_topic_ps1_3.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
