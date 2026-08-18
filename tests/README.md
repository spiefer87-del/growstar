# Growstar Tests

Seit Growstar 3.8 werden aktuelle Regressionstests unter `tests/` organisiert.

Die früheren phasenbezogenen `check_*.py`-Dateien im Repository-Root wurden
bewusst nicht in eine neue Archivstruktur kopiert. Git ist bereits das Archiv:
der vollständige 3.7.10-Teststand bleibt unter Commit
`0e44d73639c0060eb7f520ccb7ef692081ce5ec6` verfügbar.

Aktueller Baseline-Test:

```bash
python3 tests/regression/check_repository_baseline.py
```

Neue Featuretests sollen künftig nach Subsystem gegliedert werden, statt für
jeden Minipatch eine weitere Root-Datei anzulegen.
