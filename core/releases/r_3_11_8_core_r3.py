"""Growstar release node 3.11.8 / CORE.R3."""

RELEASE = {'version': '3.11.8',
 'date': '2026-08-23',
 'phase': 'CORE.R3',
 'title': 'Release-Nodes dauerhaft in Einzeldateien aufgeteilt',
 'summary': 'Growstar beendet das Anwachsen einer zentralen current.py. Ab diesem Patch besitzt '
            'jeder neue Release genau eine eigene kleine Python-Datei unter core/releases. Ein '
            'dynamischer Loader findet diese Release-Nodes automatisch, validiert sie und sortiert '
            'sie numerisch nach Version. Dadurch muss für zukünftige Patches keine bestehende '
            'Release-Datei mehr erweitert werden. Gleichzeitig wird die Release-Regression '
            'vollständig versions- und datumsdynamisch, sodass neue Kalendertage keinen falschen '
            'Fehler mehr auslösen.',
 'changes': ('Jeder Release ab 3.11.3 liegt in einer eigenen Datei r_<version>_<phase>.py und '
             'exportiert genau einen RELEASE-Datensatz.',
             'core/releases/loader.py entdeckt alle r_*.py-Module automatisch; zukünftige Releases '
             'benötigen keine Änderung an einem zentralen Manifest.',
             'Der Loader validiert Version, Datum, Phase, Titel sowie changes/tests und lehnt '
             'doppelte Versionsnummern ab.',
             'PATCH_RELEASES wird numerisch nach Major/Minor/Patch absteigend sortiert und '
             'anschließend unverändert vor die Legacy-Historie gesetzt.',
             'core/releases/current.py bleibt nur als kleine Kompatibilitätsdatei erhalten und '
             'wächst künftig nicht mehr.',
             'core/releases/__init__.py setzt die automatisch geladenen Patch-Releases und die '
             'unveränderte Legacy-Historie zur öffentlichen RELEASES-Historie zusammen.',
             'check_release_split.py berechnet das deutsche Datumslabel aus dem tatsächlichen '
             'Release-Datum statt den 22.08.2026 hart zu codieren.',
             'Die Regression verlangt für jeden Patch-Release genau eine eigene Release-Datei und '
             'begrenzt Loader, current.py und einzelne Release-Nodes auf kleine Dateigrößen.',
             'check_repository_baseline.py lädt core.release package-aware; dadurch funktionieren '
             'relative Imports auf einem frischen Git-Checkout ohne lokale Sonderdatei.',
             'Runtime-, Hardware-, Sensor-, Netzwerk-, Shelly-, MQTT- und Spider-Farmer-Verhalten '
             'werden nicht verändert.'),
 'tests': ('check_release_split.py prüft automatische Discovery, numerische Sortierung, '
           'Einzeldateien, Duplikatfreiheit und dynamische Versions-/Datumsanzeige.',
           'Die aktuelle Version 3.11.8 / CORE.R3 muss allein aus dem höchsten entdeckten '
           'Release-Node entstehen.',
           'Die Legacy-Historie beginnt weiterhin unverändert bei 3.11.2 / SF.2A und bleibt '
           'vollständig erhalten.',
           'current.py darf nur noch ein kleiner Kompatibilitäts-Wrapper sein und keine '
           'Release-Dictionaries mehr enthalten.',
           'Der Repository-Baseline-Test lädt die Release-API als reguläres core-Paket.',
           'Bestehende Spider-Farmer-Regressionen bleiben unverändert zusätzlich auszuführen.')}
