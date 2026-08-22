"""Growstar release node 3.11.3 / CORE.R1."""

RELEASE = {'version': '3.11.3',
 'date': '2026-08-22',
 'phase': 'CORE.R1',
 'title': 'Release-Historie aus core/release.py ausgelagert',
 'summary': 'Growstars inzwischen sehr große Release-Historie wird aus der öffentlichen '
            'core.release-Schnittstelle ausgelagert. Die bisherige Historie bleibt vollständig und '
            'unverändert erhalten, während neue Patch-Einträge künftig in kleinen, separat '
            'verwaltbaren Release-Modulen liegen. Runtime-, Hardware-, Sensor-, Netzwerk- und '
            'Spider-Farmer-Verhalten werden durch diesen Strukturpatch nicht verändert.',
 'changes': ('Die bisherige vollständige core/release.py wird bytegleich als '
             'core/releases/legacy.py erhalten; kein historischer Release-Eintrag wird neu '
             'geschrieben, gekürzt oder gelöscht.',
             'core/releases/current.py enthält ab 3.11.3 ausschließlich neue Release-Nodes und '
             'bleibt dadurch für zukünftige mobile GitHub-Patches klein.',
             'core/releases/__init__.py setzt CURRENT_RELEASES und die unveränderte '
             'LEGACY_RELEASES-Historie zu genau einem RELEASES-Tupel zusammen.',
             'core/release.py bleibt die stabile öffentliche Schnittstelle mit RELEASES, '
             'current_release(), release_history(), release_summary(), GROWSTAR_VERSION, '
             'GROWSTAR_RELEASE_DATE und GROWSTAR_INTERNAL_PHASE.',
             'Bestehende Importe aus core.release sowie routes/release.py müssen dadurch nicht '
             'angepasst werden.',
             'Der direkte Vorgänger des Strukturpatches bleibt Growstar 3.11.2 / SF.2A; dessen '
             'vollständige Patch-Note liegt unverändert im Legacy-Modul.',
             'Der Patch verändert keine Growstar-Konfiguration, keine Sensorzuordnung, keine '
             'Shelly-Funktion, keinen MQTT-Pfad, keine Netzwerkgrenze und keine '
             'Spider-Farmer-Bridge.'),
 'tests': ('check_release_split.py verlangt die getrennte aktuelle/historische Release-Struktur '
           'und prüft die öffentliche core.release-Schnittstelle versionsunabhängig.',
           'Die Regression bestätigt, dass RELEASES exakt aus CURRENT_RELEASES plus '
           'LEGACY_RELEASES besteht und keine Versions-/Phasen-Duplikate enthält.',
           'Der vollständige Legacy-Bestand muss weiterhin 3.11.2 / SF.2A als ersten Eintrag '
           'besitzen.',
           'Die öffentliche core.release-API wird auf defensive Kopien, deutsches Datumslabel und '
           'unveränderte Summary-Felder geprüft.',
           'Die alte monolithische Historie wurde bei der Migration vor jedem Schreibzugriff über '
           'ihren Git-Blob-SHA verifiziert.')}
