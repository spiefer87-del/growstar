"""Growstar release node 3.11.5 / SF.3A."""

RELEASE = {'version': '3.11.5',
 'date': '2026-08-22',
 'phase': 'SF.3A',
 'title': 'Spider-Farmer Geräte- und Konfigurationsmodell',
 'summary': 'Growstar bildet den bereits normalisierten Spider-Farmer-State jetzt als stabiles '
            'read-only Geräteinventar ab. Licht, Ventilator, Gebläse, optionale Klima-Geräte und '
            'Steckdosenkanäle erhalten eine gemeinsame Growstar-Darstellung aus Live-State und '
            'beobachteter Controller-Konfiguration. Der Ventilator stellt dabei unter anderem '
            'Run-Level, Standby-Level, Oszillation, Natural Wind und Zyklusparameter bereit. Es '
            'wird weiterhin kein Spider-Farmer-Schreibbefehl erzeugt oder gesendet.',
 'changes': ('bridge/spiderfarmer/device_model.py führt ein reines read-only Projektionsmodell für '
             'Spider-Farmer-Geräte ein.',
             'Umweltsensor, Licht 1/2, Ventilator, Gebläse, Heizung, Luftbe-/entfeuchter und '
             'Power-Strip-Kanäle werden nur dann modelliert, wenn dafür bereits normalisierte '
             'Live- oder Config-Daten beobachtet wurden.',
             'Ventilator und Gebläse kombinieren Live-Werte für on/level/mode_type mit '
             'beobachteten Config-Werten für standby_level, run_level, oscillation_level, '
             'natural_wind, cycle und schedule.',
             'shakeLevel bleibt ausschließlich als normalisiertes oscillation_level sichtbar; '
             'SF.3A führt noch keinen Encoder und keinen setConfigField-Schreibpfad ein.',
             'services/spiderfarmer.py ergänzt Controller um devices/device_count sowie '
             'list_devices() und device() für zukünftige Growstar-API/UI-Nutzung.',
             'public_snapshot() meldet SF.3A als Projektionsphase und hält gleichzeitig die '
             'zugrunde liegende SF.2-Bridge-Phase als source_phase fest.',
             'Die bestehende SF.2A Sensorquellen-Synchronisierung bleibt unverändert stale-safe '
             'und read-only.'),
 'tests': ('check_spiderfarmer_devices.py simuliert einen realistischen GGS-State mit Sensor, '
           'Licht, Ventilator, Gebläse und Power-Strip.',
           'Die Regression verlangt Run-Level 8, Standby-Level 2, oscillation_level 5, Natural '
           'Wind sowie den beobachteten 90/270-Sekunden-Zyklus.',
           'Outlet-Kanäle erhalten stabile IDs wie outlet:O1 und können einzeln über den '
           'Growstar-Service gelesen werden.',
           'Statische Guards verbieten Socket-, MQTT-Publish-, writer.write- und '
           'setConfigField-Commandpfade in SF.3A.',
           'Bestehende Repository-, Release-Split- und SF.2A-Regressionen bleiben zusätzlich '
           'auszuführen.')}
