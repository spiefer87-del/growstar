"""Growstar 3.16.5 / SF.RESTART.1 release metadata."""

RELEASE = {
    "version": "3.16.5",
    "date": "2026-09-03",
    "phase": "SF.RESTART.1",
    "title": "D734-Sensorwerte sicher über den Growstar-Neustart erhalten",
    "summary": (
        "Ein Growstar-/Bridge-Neustart setzt eine frisch empfangene D734-Probe "
        "nicht mehr künstlich auf unverfügbar. Der ursprüngliche Messzeitpunkt "
        "bleibt maßgeblich und neue Bridge-Werte werden im Zwei-Sekunden-Takt übernommen."
    ),
    "changes": (
        "Die Spider-Farmer-Bridge erhält den letzten normalisierten Livewert zusammen mit seinem ursprünglichen last_seen über einen Prozessneustart.",
        "Persistierte Werte werden beim Einlesen niemals mit der lokalen Neustartzeit aufgefrischt.",
        "Der Growstar-Sensoradapter reicht den echten Bridge-Zeitstempel bis zur controllerweiten Sensorquelle durch.",
        "Ein verzögert eingelesener Persistenzstand kann keine bereits neuere Liveprobe überschreiben.",
        "Zeitstempel aus der Zukunft gelten nicht als frische Sensorwerte.",
        "Der normale SENSOR_TIMEOUT von 120 Sekunden bleibt unverändert die einzige Frischegrenze.",
        "Growstar seedet Spider-Farmer-Quellen vor dem Start von Safety- und Regelthreads.",
        "Ein eigener read-only Thread übernimmt neue Spider-Farmer-Proben alle zwei Sekunden statt erst mit dem 30-Sekunden-Hardware-Scan.",
        "Die gespeicherte D734-Zuweisung funktioniert nach einem Neustart ohne zwischenzeitliche Auswahl eines Pico-Sensors.",
        "Die bestehende PartOf-Kopplung und der Schutz gegen alte Controller-Writer bleiben unverändert erhalten.",
        "Es gibt keine Konfigurationsmigration und keine Änderung an Sensor-Offsets, Profilen oder VPD-Regelparametern.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_restart_sensor_continuity.py",
        "python3 tests/regression/check_spiderfarmer_state.py",
        "python3 tests/regression/check_spiderfarmer_growstar_adapter.py",
        "python3 tests/regression/check_spiderfarmer_writer_reconnect_guard.py",
        "python3 tests/regression/check_spiderfarmer_restart_coupling.py",
        "python3 tests/regression/check_safety_supervisor_thread.py",
        "python3 tests/regression/check_release_loader.py",
        "python3 tests/regression/check_repository_baseline.py",
    ),
}
