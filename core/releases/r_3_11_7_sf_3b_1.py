"""Growstar release node 3.11.7 / SF.3B.1."""

RELEASE = {'version': '3.11.7',
 'date': '2026-08-23',
 'phase': 'SF.3B.1',
 'title': 'Spider-Farmer Konfiguration über Bridge-Neustarts erhalten',
 'summary': 'Growstar trennt beim Spider-Farmer-Neustart jetzt bewusst zwischen flüchtigem '
            'Live-State und bereits beobachteter normalisierter Controller-Konfiguration. '
            'Live-Werte werden weiterhin ausschließlich aus frischem getDevSta-Traffic aufgebaut. '
            'Konfigurationswerte wie Run-Level, Standby-Level, Oszillation, Natural Wind und '
            'Zyklus bleiben dagegen über einen Bridge-Neustart erhalten, weil Spider Farmer '
            'setConfigField nicht zwingend nach jedem Reconnect erneut sendet.',
 'changes': ('BridgeDiagnostics restauriert beim Start ausschließlich normalisierte config-Blöcke '
             'aus der privaten spiderfarmer_state.json.',
             'Persistierte live-Blöcke werden absichtlich nicht restauriert und last_seen wird auf '
             'None gesetzt, damit alte Messwerte niemals als frisch erscheinen.',
             'Controller-PID und Prefix dürfen zusammen mit der Config wiederhergestellt werden, '
             'ohne einen Online- oder Frischezustand vorzutäuschen.',
             'Neue getDevSta-Pakete füllen den Live-State nach dem Neustart wie bisher neu auf und '
             'lassen die restaurierte Config unangetastet.',
             'Neue setConfigField-Pakete aktualisieren die restaurierte Config weiterhin über den '
             'bestehenden normalisierten Deep-Merge.',
             'Nicht lesbare, ungültige oder nicht read-only markierte Persistenzdateien werden '
             'nicht vertraut; in diesem Fall startet Growstar mit einem leeren SF.2-State.',
             'Der Fix fügt keinen Spider-Farmer-Schreib-, MQTT-Publish- oder Netzwerkpfad hinzu.'),
 'tests': ('check_spiderfarmer_state.py simuliert jetzt explizit einen Bridge-Neustart mit vorher '
           'beobachtetem Live- und Config-State.',
           'Die Regression verlangt, dass Live-State und last_seen nach dem Neustart leer '
           'beziehungsweise None sind.',
           'Run-Level 8, Standby-Level 2, Oszillation 5, Natural Wind und der '
           '90/270-Sekunden-Zyklus müssen den Neustart dagegen vollständig überstehen.',
           'Frischer getDevSta-Traffic muss nach dem Neustart den Live-State neu befüllen, ohne '
           'die restaurierte Config zu löschen.',
           'Ein nicht-read-only Persistenz-State darf nicht übernommen werden.',
           'Statische Guards bestätigen weiterhin das Fehlen von Command- und Transportpfaden.')}
