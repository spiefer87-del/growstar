"""Growstar 3.15.6 / ENV.TOOLTIP.1 release metadata."""

RELEASE = {
    "version": "3.15.6",
    "date": "2026-08-30",
    "phase": "ENV.TOOLTIP.1",
    "title": "Diagramm-Tooltip: korrekte Einheiten und Auto-Hide",
    "summary": (
        "Die Diagramm-Infobox verwendet nun immer die Einheit der aktuell "
        "gewählten Messgröße und schließt sich automatisch."
    ),
    "changes": (
        "Temperatur-Tooltip zeigt °C.",
        "Luftfeuchte-Tooltip zeigt %.",
        "VPD-Tooltip zeigt kPa.",
        "PPFD-Tooltip zeigt µmol/m²/s.",
        "Sollwert-Zeilen verwenden die korrekte Einheit der Messgröße.",
        "Tooltip schließt sich nach 2,5 Sekunden automatisch.",
        "Metrik- und Zeitraumwechsel schließen offene Tooltips sofort.",
        "Pointer- und Touch-Bedienung werden unterstützt.",
        "History-API und Messwertaufzeichnung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_environment_tooltip.py",
        "python3 tests/regression/check_environment_charts.py",
        "python3 tests/regression/check_chart_stability.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
