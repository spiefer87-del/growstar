"""Growstar release node 3.11.4 / CORE.R2."""

RELEASE = {'version': '3.11.4',
 'date': '2026-08-22',
 'phase': 'CORE.R2',
 'title': 'Repository-Baseline an Release-Paketstruktur angepasst',
 'summary': 'Der Repository-Baseline-Test lädt core.release nach dem CORE.R1-Split jetzt als '
            'reguläres Python-Paketmodul. Dadurch funktionieren die relativen Importe aus '
            'core.release auch im Regressionstest, ohne die neue Release-Struktur zurückzubauen '
            'oder Runtime-Code zu verändern.',
 'changes': ('check_repository_baseline.py lädt core.release nicht länger über ein anonymes '
             'spec_from_file_location-Modul, sondern package-aware über importlib.import_module.',
             'Vor dem Import werden eventuell zwischengespeicherte '
             'core.release/core.releases-Module entfernt, damit der Test den aktuellen '
             'Repository-Stand prüft.',
             'Der Repository-Root wird vor dem Import explizit in sys.path gehalten; relative '
             'Importe aus core.release funktionieren dadurch wie im normalen Growstar-Prozess.',
             'core/releases/current.py erhält den neuen Release-Node 3.11.4 / CORE.R2; 3.11.3 / '
             'CORE.R1 bleibt direkter Vorgänger.',
             'Keine Runtime-, Hardware-, Sensor-, Shelly-, MQTT-, Netzwerk- oder '
             'Spider-Farmer-Datei wird geändert.'),
 'tests': ('check_repository_baseline.py muss nach dem Patch ohne ImportError vollständig '
           'durchlaufen.',
           'check_release_split.py muss weiterhin die getrennte Release-Historie und die '
           'öffentliche core.release-Schnittstelle bestätigen.',
           'check_spiderfarmer_growstar_adapter.py muss weiterhin vollständig grün bleiben.',
           'Ein Syntax-/AST-Check bestätigt beide geänderten Python-Dateien vor dem Schreiben.')}
