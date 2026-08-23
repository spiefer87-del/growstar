"""Growstar release node 3.11.15 / SF.4C."""

RELEASE = {
    "version": "3.11.15",
    "date": "2026-08-23",
    "phase": "SF.4C",
    "title": "Controller-Sollwerte direkt in der bestehenden Geräte-Detailseite",
    "summary": (
        "Beim Öffnen einer Growstar-Gerätekachel erscheint für zugeordnete "
        "Controller jetzt direkt eine zusätzliche Sollwertkarte. Ventilator, "
        "Licht und Gebläse behalten ihre bestehende Power-/Modusregelung, "
        "erhalten aber die zum zugewiesenen physischen Controller passenden "
        "Einstellwerte. SF.4C persistiert diese Werte bereits sauber und "
        "provider-neutral, sendet sie jedoch noch nicht an die Hardware."
    ),
    "changes": (
        "Die bestehende device_control.html bleibt die zentrale Detailseite hinter den Gerätekacheln.",
        "Ein zugeordneter Controller erscheint automatisch als zusätzliche Controller-Karte auf derselben Seite.",
        "Spider-Farmer-Fan bietet gemeinsam Ventilatorstufe und Oszillation auf der GGS-L1-bis-L10-Skala.",
        "Spider-Farmer-Light bietet Lichtstärke von 0 bis 100 Prozent.",
        "Spider-Farmer-Blower bietet Gebläsestärke von 0 bis 100 Prozent.",
        "Controller-Eingaben werden mit Slider und Zahleneingabe mobil bedienbar dargestellt.",
        "Die Geräte-API liefert Controller-Target, Online-Status, Fähigkeiten, Setpoint-Schema und gespeicherte Sollwerte.",
        "Controller-Sollwerte werden generisch unter DEVICE_PARAMS[device].controller gespeichert.",
        "Die Sollwerte werden gemeinsam mit Modus, Intervall und ENV-Einstellungen über den bestehenden Geräte-Speicherpfad persistiert.",
        "Power bleibt unverändert beim Shelly und die bestehende Hardware-/Safety-Logik bleibt erhalten.",
        "SF.4C besitzt bewusst noch keinen Spider-Farmer-Command-/Transportpfad.",
    ),
    "tests": (
        "check_controller_setpoints.py validiert GGS-Fan-Level und Oszillation von L1 bis L10.",
        "Licht- und Blower-Level werden auf 0 bis 100 Prozent validiert.",
        "Unbekannte Capabilities und Werte außerhalb des Bereichs werden blockiert.",
        "Die Regression verlangt die Integration in die bestehende device_control.html statt einer neuen Sonderseite.",
        "Statische Guards bestätigen erneut, dass kein Hardware-/MQTT-/Socket-Schreibpfad eingeführt wird.",
    ),
}
