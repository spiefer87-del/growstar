"""Growstar release node 3.13.3 / SF.PS1."""

RELEASE = {
    "version": "3.13.3",
    "date": "2026-08-25",
    "phase": "SF.PS1",
    "title": "Spider Farmer Power Strip als eigene Hardwarefamilie",
    "summary": (
        "Growstar trennt Spider-Farmer-Power-Strips jetzt ausdrücklich von "
        "Shelly und vom bestehenden GGS-Controller. PS5/PS10-Outlet-Readback "
        "bleibt kanonisch; beobachtete O1..O10-Kanäle können über den aktiven "
        "PS-DOWN-Pfad manuell EIN/AUS geschaltet werden."
    ),
    "changes": (
        "Eigener Power-Strip-Command-Compiler statt Erweiterung des bestehenden Controller-Compilers.",
        "PS-DOWN-Topic wird ausschließlich aus der aktiven MQTT-Subscription der konkreten Session übernommen.",
        "Outlet-Befehl verwendet den referenzbestätigten keyPath ['outlet','On'] mit modeType=0 und mOnOff.",
        "Spider-Farmer-UID wird nicht erfunden, sondern aus bereits beobachtetem Traffic desselben PID übernommen.",
        "Eigene Growstar-Service- und API-Schicht für Power-Strip-Outlets.",
        "Spider-Farmer-Systemseite erkennt Prefix PS und zeigt O1..On mit EIN/AUS-Steuerung.",
        "Nach Befehlen bleibt getDevSta der maßgebliche Readback; UI aktualisiert den Zustand erneut.",
        "Bestehender CB-Controllerpfad, Shelly, Regelung, Safety, Netzwerk und Restart-Kopplung bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_dashboard_controller_readback.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
