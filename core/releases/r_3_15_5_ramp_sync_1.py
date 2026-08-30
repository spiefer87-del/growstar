"""Growstar 3.15.5 / RAMP.SYNC.1 release metadata."""

RELEASE = {
    "version": "3.15.5",
    "date": "2026-08-30",
    "phase": "RAMP.SYNC.1",
    "title": "Heizungs-Morgenrampe mit Profilbeginn synchronisieren",
    "summary": (
        "Die Morgenrampe der Heizung startet jetzt exakt mit DAY_START_MIN "
        "und läuft anschließend über RAMP_DURATION_MIN zum Tages-Sollwert."
    ),
    "changes": (
        "Morgenrampe startet nicht mehr RAMP_DURATION_MIN vor DAY_START_MIN.",
        "Bei DAY_START_MIN 05:30 und 30 Minuten Rampendauer läuft sie 05:30–06:00.",
        "Der Sonnenaufgang kann damit synchron um 05:30 bei seinem Mindestlevel beginnen.",
        "Die Abendrampe bleibt unverändert und endet weiterhin bei NIGHT_START_MIN.",
        "Aktive Morgenrampen verwenden beim Resync das neue Rampenende.",
    ),
    "tests": (
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
