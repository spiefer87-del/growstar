"""Growstar release node 3.11.28 / SF.4D.12."""

RELEASE = {
    "version": "3.11.28",
    "date": "2026-08-23",
    "phase": "SF.4D.12",
    "title": "Spider-Farmer Licht mLevel Hardwaretest",
    "summary": (
        "SF.4D.12 ergänzt einen bewusst privaten manuellen Licht-Test. "
        "Die bestehende Licht-Abbildung level -> mLevel und die zentrale "
        "0-bis-100-Prozent-Skala bleiben unverändert. Der neue Diagnosepfad "
        "sendet modeType=0, mOnOff=1 und mLevel=0..100 direkt über die bereits "
        "bestehende Controller-Verbindung, ohne den Produktionspfad vorzeitig "
        "als hardwarebestätigt zu markieren."
    ),
    "changes": (
        "Privater Command test_controller_manual_light wird ergänzt.",
        "compile_manual_light_command validiert mLevel über das bestehende light-Schema 0..100.",
        "Der Licht-Test nutzt das stabile DOWN-Topic und keyPath [\"device\", \"light\"].",
        "Der normale set_controller-Produktionspfad für light bleibt unverändert.",
        "Kein Capture-Fallback für Licht wird in diesem Release freigeschaltet.",
        "Neues CLI-Testtool tools/test_spiderfarmer_manual_light.py.",
        "Neue Regression für Payload, Wertebereich und Diagnosekennung.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_manual_light.py",
        "python3 -m py_compile bridge/spiderfarmer/command_model.py bridge/spiderfarmer/command_proxy.py tools/test_spiderfarmer_manual_light.py core/releases/r_3_11_28_sf_4d_12.py",
        "Realer Hardwaretest zunächst mit mLevel 50, danach 25 und 75.",
        "mLevel=0 erst separat prüfen, nachdem 25/50/75 sicher bestätigt wurden.",
    ),
}
