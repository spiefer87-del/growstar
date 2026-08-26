"""Growstar release node 3.13.7 / SF.PS1.3a."""

RELEASE = {
    "version": "3.13.7",
    "date": "2026-08-26",
    "phase": "SF.PS1.3a",
    "title": "Power-Strip-Regressionstest an SF.PS1.3 synchronisieren",
    "summary": (
        "Der ältere SF.PS1.2-Route-Test verlangte weiterhin zwingend eine "
        "bereits vorhandene echte DOWN-Subscription. Seit SF.PS1.3 ist "
        "zusätzlich die eng begrenzte Ableitung aus einem eindeutig beobachteten "
        "PS/PS5/PS10-UP-Topic derselben PID zulässig. Der Regressionstest wird "
        "an diese neue Sicherheitsregel angepasst."
    ),
    "changes": (
        "Nur der veraltete Power-Strip-Route-Test wird synchronisiert.",
        "Echte DOWN-Subscriptions bleiben weiterhin bevorzugt.",
        "Mehrere DOWN-Subscriptions bleiben fail-closed.",
        "Fallback bleibt auf beobachtete UP-Topics derselben PID begrenzt.",
        "Nur PS, PS5 und PS10 bleiben als Power-Strip-Topicfamilie zulässig.",
        "Keine Änderung an Bridge-Laufzeit, Outlet-Payload, Shelly, GGS-Controller, Regelung, Safety oder Netzwerk.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_powerstrip_route_ps1_2.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_topic_ps1_3.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ui_ps1_1.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
