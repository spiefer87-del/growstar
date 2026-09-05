"""Growstar 3.16.18 / SHELL.4 release metadata."""

RELEASE = {
    "version": "3.16.18",
    "date": "2026-09-05",
    "phase": "SHELL.4",
    "title": "Eigene Energiekategorie und linke Menüpfeile",
    "summary": (
        "Energie wird als eigenständige dritte Hauptkategorie unter dem "
        "Pflanzenmanagement geführt. Die Aufklapppfeile aller modularen "
        "Navigationsbereiche liegen nun links in einer größeren Touchfläche."
    ),
    "changes": (
        "Energie wurde aus dem Technik-Untermenü von Grow Control entfernt.",
        "Die neue Hauptkategorie Energie steht nach Grow Control und Pflanzenmanagement an dritter Stelle vor Administration.",
        "Das Energie-Untermenü verlinkt Übersicht, Energie-Diagramme und Energie-Einstellungen getrennt.",
        "Energieübersicht, Diagramme und Einstellungen aktivieren automatisch die neue Kategorie und den Appbar-Kontext Energie.",
        "Die Aufklapppfeile von Grow Control, Pflanzenmanagement und Energie stehen links vor dem jeweiligen Modul-Link.",
        "Die linke Pfeiltaste besitzt eine 42 mal 44 Pixel große Touchfläche für eine bequemere Daumenbedienung.",
        "Bestehende ARIA-Verknüpfungen, unabhängige Aufklappzustände und Tastaturbedienung bleiben erhalten.",
        "Ein neuer Stylesheet-Cache-Buster stellt sicher, dass die mobile Layoutänderung direkt geladen wird.",
    ),
    "tests": (
        "python3 tests/regression/check_energy_navigation_category.py",
        "python3 tests/regression/check_vpd_cultivation_guide.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
