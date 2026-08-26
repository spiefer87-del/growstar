"""Growstar release node 3.13.5 / SF.PS1.2."""

RELEASE = {
    "version": "3.13.5",
    "date": "2026-08-26",
    "phase": "SF.PS1.2",
    "title": "Power-Strip-Schreibroute an robuste Geräteerkennung angleichen",
    "summary": (
        "Die UI erkannte den PS5 bereits korrekt, die serverseitige Outlet-POST-"
        "Route verlangte jedoch weiterhin ausschließlich ein vorhandenes "
        "prefix=PS-Feld. Die Route nutzt nun dieselbe konservative Klassifikation."
    ),
    "changes": (
        "Prefix PS bleibt kanonischer Power-Strip-Indikator.",
        "Normalisiertes outlet-Gerät mit gültigem O1..O10-Inventar dient als Fallback.",
        "Die MQTT-Bridge bleibt unverändert und verlangt weiterhin ein echtes aktives PS-DOWN-Topic.",
        "Shelly, GGS-Controller, Regelung, Safety und Netzwerk bleiben unverändert.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_powerstrip_route_ps1_2.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ui_ps1_1.py",
        "python3 tests/regression/check_spiderfarmer_powerstrip_ps1.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
