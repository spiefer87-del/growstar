"""Growstar 3.14.0 / LIGHT.SUN.1 release metadata."""

RELEASE = {
    "version": "3.14.0",
    "date": "2026-08-28",
    "phase": "LIGHT.SUN.1",
    "title": "Sonnenaufgang und Sonnenuntergang per Lichtdimmung",
    "summary": (
        "Die bestehende Profil-Beleuchtung kann optional morgens von einer "
        "Mindestleistung auf den vorhandenen ENV-Lichtlevel hochdimmen und "
        "abends vor Nacht Start wieder herunterdimmen."
    ),
    "changes": (
        "Neue provider-neutrale Sonnenverlauf-Berechnung.",
        "Tag Start ist Beginn des Sonnenaufgangs.",
        "Nacht Start ist Ende des Sonnenuntergangs und Licht AUS.",
        "Der bestehende ENV-Controller-Level bleibt die maximale Tagesleistung.",
        "Sonnenaufgang, Sonnenuntergang und Mindestleistung sind stationsbezogen einstellbar.",
        "Feature ist standardmäßig deaktiviert und auf der Profilseite schaltbar.",
        "Ohne dimmbaren ENV-Controller bleibt das bisherige EIN/AUS-Verhalten erhalten.",
        "Shelly Power, Safety, Shadow/LIVE und Spider-Farmer-Transport bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_spiderfarmer_ps_controller_transport.py",
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
