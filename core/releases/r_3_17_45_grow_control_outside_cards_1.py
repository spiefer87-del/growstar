"""Growstar 3.17.45 / GROW.CONTROL.OUTSIDE.CARDS.1."""

RELEASE = {
    "version": "3.17.45",
    "date": "2026-10-19",
    "phase": "GROW.CONTROL.OUTSIDE.CARDS.1",
    "title": "Stationskacheln mit vollständigen Außenwerten",
    "summary": "Grow Control zeigt Außentemperatur, Außenfeuchte und Außen-VPD in drei Kacheln.",
    "changes": [
        "Die komplette Stationskachel öffnet die zugehörige Station; der kleine Öffnen-Link entfällt.",
        "Unter Temperatur, Feuchte und VPD innen stehen gleichwertige, blau abgesetzte Außenkacheln.",
        "Die Stationsliste liefert Außenfeuchte und berechnet Außen-VPD nur aus gültigen Werten.",
        "Fehlende Messwerte werden als Strich statt als null Grad oder null Prozent angezeigt.",
    ],
    "tests": [
        "python3 tests/regression/check_grow_control_overview_outside.py",
        "node tests/regression/check_grow_control_overview_outside.js",
        "python3 tests/regression/check_vpd_chart.py",
        "python3 tests/regression/check_grow_control_quick_menu.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ],
}
