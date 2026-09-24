"""Growstar 3.17.29 / PREDICTIVE-HEATING.1 release metadata."""

RELEASE = {
    "version": "3.17.29",
    "date": "2026-09-24",
    "phase": "PREDICTIVE-HEATING.1",
    "title": "Vorausschauende Heizregelung und Sollwert-Hinweis",
    "summary": "Stationsweise einschaltbare Heizprognose mit Schaltabständen und belegter 30-Minuten-Meldung.",
    "changes": [
        "Der Heizungs-ENV-Modus bietet eine pro Station einschaltbare vorausschauende Regelung.",
        "Temperaturtrend und beobachtetes Nachheizen bestimmen begrenzte frühe Schaltpunkte.",
        "Vier Minuten Mindestabstand gelten nahe Soll; deutlich unter Soll läuft die Heizung weiter.",
        "Unveränderte Sicherheitsgrenzen, Sensor-Schutz und VPD-Vorrang bleiben erhalten.",
        "Nach 30 Minuten bestätigtem Heizen unter Soll erscheint ein einmaliger Grow-Intelligence-Hinweis mit Entwarnung.",
        "Alte Regelung ist Standard; die neue Option muss je Station eingeschaltet werden.",
    ],
    "tests": [
        "python3 tests/regression/check_predictive_heating.py",
        "python3 tests/regression/check_grow_intelligence_cycle_context.py",
        "python3 tests/regression/check_grow_intelligence_insights.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
