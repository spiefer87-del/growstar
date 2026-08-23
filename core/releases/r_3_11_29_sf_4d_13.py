"""Growstar release node 3.11.29 / SF.4D.13."""

RELEASE = {
    "version": "3.11.29",
    "date": "2026-08-23",
    "phase": "SF.4D.13",
    "title": "Spider-Farmer Licht produktiv über mLevel",
    "summary": (
        "SF.4D.13 übernimmt den am realen GGS-Controller bestätigten manuellen "
        "Lichtpfad in die Growstar-Produktion. Licht 1 wird mit modeType=0, "
        "mOnOff=1 und mLevel=11..100 gesteuert. Die Growstar-Lichtskala beginnt "
        "bewusst bei 11 Prozent, weil reale Tests mit mLevel 9 und 10 vom "
        "Controller beziehungsweise der Spider-Farmer-App ebenfalls als "
        "11 Prozent dargestellt wurden."
    ),
    "changes": (
        "Zentrale Licht-Skala wird von 0..100 auf 11..100 Prozent begrenzt.",
        "light.level bleibt auf das bestätigte Spider-Farmer-Feld mLevel gemappt.",
        "Produktionsbefehle für light erzwingen modeType=0 und mOnOff=1.",
        "Alte Licht-Zeitpläne, PPFD- und Temperatur-Automatikfelder werden nicht aus Capture-Templates zurückgesendet.",
        "Bei fehlendem Capture-Template nutzt light den hardwarebestätigten stabilen manuellen Fallback.",
        "Der private manuelle Licht-Test nutzt jetzt ebenfalls ausschließlich 11..100.",
        "light2 erhält noch keinen capture-unabhängigen Produktions-Fallback, bis es separat hardwaregetestet wurde.",
    ),
    "tests": (
        "check_spiderfarmer_manual_light.py prüft 11..100, den manuellen Payload, den Produktions-Fallback und das Entfernen alter Automatikfelder.",
        "Realer Hardwaretest bestätigt mLevel 50, 15 und 100; mLevel 9/10 werden vom Controller als 11 Prozent dargestellt.",
        "Nach Installation den normalen Growstar-Lichtslider bei 11, 50 und 100 Prozent testen.",
    ),
}
