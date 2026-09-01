"""Growstar 3.15.9 / PROFILE.MANAGEMENT.1 release metadata."""

RELEASE = {
    "version": "3.15.9",
    "date": "2026-09-01",
    "phase": "PROFILE.MANAGEMENT.1",
    "title": "Profilentwürfe getrennt speichern und aktivieren",
    "summary": (
        "Klimaänderungen werden erst gesammelt gespeichert. Eine eigene "
        "Profilverwaltung erlaubt das Vorbereiten jedes Presets, ohne das "
        "laufende Stationsprofil sofort zu verändern."
    ),
    "changes": (
        "Klima-, Grenzwert-, Zeit-, Rampen- und Sonnenwerte besitzen einen gemeinsamen Speichern-Button.",
        "Plus/Minus, Eingaben und Schalter verändern bis zur Bestätigung nur den Browserentwurf.",
        "Ungespeicherte Klimaänderungen können verworfen werden und sind beim Verlassen geschützt.",
        "Eingaben bleiben während des Ladens gesperrt, damit keine verspätete Antwort einen neuen Entwurf überschreibt.",
        "Eine neue Profilseite lädt alle vorhandenen Presets dynamisch aus dem Profilkatalog.",
        "Vegetation, Blüte und Trocknung lassen sich unabhängig vom aktiven Stationsprofil bearbeiten.",
        "Profil speichern ändert ausschließlich die controllerweite Vorlage und niemals die Runtime.",
        "Profil aktivieren bleibt eine getrennte bestätigte Aktion für genau eine Station.",
        "Das aktive Profil kann nach einer Bearbeitung bewusst erneut angewendet werden.",
        "Die Dashboard-Profilkarte zeigt das aktive Preset und die aktuelle Tag-/Nachtphase getrennt.",
        "Profilwerte werden vollständig, streng und serverseitig validiert.",
        "profiles.json wird atomar ersetzt; Dateirechte und importierte PROFILES-Referenzen bleiben erhalten.",
        "Fehlende Lichtcontroller führen beim Speichern anderer Klimawerte zu keiner stillen Sonnenwert-Änderung.",
        "Neue Seiten und APIs verwenden die bestehenden settings.view/grow.configure-Berechtigungen.",
        "Der bestehende sichere Rampen-Reset findet weiterhin ausschließlich bei der Aktivierung statt.",
    ),
    "tests": (
        "python3 tests/regression/check_profile_draft_management.py",
        "python3 tests/regression/check_light_sunrise_sunset.py",
        "python3 tests/regression/check_light_sun_controller_guard.py",
        "python3 tests/regression/check_light_sun_controller_guard_2.py",
        "python3 tests/regression/check_morning_ramp_profile_sync.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
