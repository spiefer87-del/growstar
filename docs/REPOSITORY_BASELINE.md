# Growstar 3.8 Repository Baseline

Growstar 3.8.0 beendet die lange 3.7-Patchserie und definiert eine neue,
bereinigte Entwicklungsbasis.

## Was bewusst erhalten bleibt

Folgende Bereiche sind Teil des aktuellen Laufzeit- oder Installationspfads und
wurden beim Cleanup ausdrücklich **nicht** entfernt:

- `app.py`
- `core/`, `services/`, `routes/`, `threads/`
- `auth/`
- `plant_management/`
- `profiles.json`, `core/profile.py`, `routes/profile.py`
- `config.json`
- `install/growstar.service.in`
- `install/install_growstar_service.sh`
- NetworkManager-/Growstar-Netzwerk-Helper
- `install/activate_phase4t_without_old_shutdown.sh`
- `tools/prepare_phase4t_restart.py`
- aktuelle Templates unter `templates/`
- die beiden Pico-Firmwarepakete

Die Phase-4T-Migration bleibt absichtlich im Repository, damit ein älterer
Growstar-Stand weiterhin einen dokumentierten sicheren Upgradepfad besitzt.

## Was aus dem aktiven Tree entfernt wird

- 53 historische `check_*.py`-Patchtests aus dem Repository-Root
- `app_backup.py`
- der alte Root-Pico-Prototyp `main.py`
- `presets.py`
- die ungenutzte Root-`style.css`
- leere Entwicklungsreste
- nicht mehr geroutete Legacy-Templates
- getrackte Pico-`config.py` mit realen Zugangsdaten

Der letzte vollständige 3.7.10-Stand vor dem Cleanup ist weiterhin über Git
unter Commit

`0e44d73639c0060eb7f520ccb7ef692081ce5ec6`

nachvollziehbar.

## Teststrategie ab 3.8

Neue Tests werden thematisch unter `tests/` organisiert. Patchnummern erzeugen
nicht mehr automatisch eine neue `check_phase...py` im Root.

Der zentrale Einstieg für die Repository-Baseline ist:

```bash
python3 tests/regression/check_repository_baseline.py
```

Der Test berührt keine Relais und verändert keine Netzwerkkonfiguration.
