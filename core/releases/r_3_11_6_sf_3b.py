"""Growstar release node 3.11.6 / SF.3B."""

RELEASE = {'version': '3.11.6',
 'date': '2026-08-22',
 'phase': 'SF.3B',
 'title': 'Spider-Farmer Controller-Realitätscheck',
 'summary': 'Growstar erhält einen strikt read-only Diagnose-Layer für den normalisierten '
            'Spider-Farmer-Gerätestand. Damit kann das in SF.3A eingeführte Geräte- und '
            'Konfigurationsmodell auf dem echten GGS-Controller kontrolliert werden, bevor '
            'irgendein Schreibpfad hinzukommt. Die Ausgabe ist bewusst kompakt und für die Nutzung '
            'über ein Mobiltelefon-Terminal geeignet.',
 'changes': ('bridge/spiderfarmer/readout.py erzeugt aus services.spiderfarmer einen kompakten '
             'Controller-/Geräte-Readout ohne Raw-MQTT oder Command-Transport.',
             'Der Readout zeigt Controller-ID, PID, Online-Status, Zeitstempel, Device-Count, '
             'Capabilities und alle bereits normalisierten effective-Werte.',
             'Ventilator-Konfigurationen wie run_level, standby_level, oscillation_level, '
             'natural_wind und cycle werden im echten Controller-Readout sichtbar.',
             'Power-Strip-Kanäle werden einschließlich ihrer stabilen outlet:O*-IDs getrennt '
             'dargestellt.',
             'bridge/spiderfarmer/readout_cli.py stellt eine telefonfreundliche Textausgabe sowie '
             'optional JSON bereit.',
             'SF.3B öffnet keine Netzwerkverbindung, erzeugt kein MQTT-Paket, schreibt keinen '
             'Controller-State und führt keinen setConfigField-Befehl aus.'),
 'tests': ('check_spiderfarmer_readout.py prüft einen vollständigen Testcontroller mit Sensor, '
           'Licht, Ventilator, Gebläse und zwei Outlet-Kanälen.',
           'Die Regression verlangt Run-Level 8, Standby-Level 2, Oszillation 5, Natural Wind und '
           'den 90/270-Sekunden-Zyklus im Readout.',
           'Controller-Lookup über PID sowie die telefonfreundliche Textausgabe werden geprüft.',
           'Statische Guards verbieten Socket-, MQTT-Publish-, writer.write- und '
           'setConfigField-Pfade im SF.3B-Layer.',
           'Bestehende Repository-, Release-Split-, SF.2A- und SF.3A-Regressionen bleiben '
           'zusätzlich auszuführen.')}
