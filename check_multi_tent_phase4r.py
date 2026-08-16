#!/usr/bin/env python3
"""Phase 4R – bedienungssicherer Auto-Refresh.

Statische UI-/Release-Regression. Keine Netzwerk- oder Hardwarezugriffe.
"""

from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_release():
    spec = importlib.util.spec_from_file_location(
        "phase4r_release",
        ROOT / "core" / "release.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ast.parse(read("core/release.py"), filename="core/release.py")
    print("✅ Python-Syntax core/release.py")

    release = load_release()
    device = read("templates/device_control.html")
    sensors = read("templates/sensoren.html")

    history = release.release_history()
    phase4r_release = next(
        (
            item
            for item in history
            if item.get("version") == "3.6.4"
            and item.get("phase") == "4R"
        ),
        None,
    )

    require(
        phase4r_release is not None,
        "Phase 4R bleibt als Version 3.6.4 in der Release-Historie erhalten",
    )

    # Gerätesteuerung
    require(
        "function applyDeviceForm(data)" in device,
        "Gerätekonfiguration ist von der Runtime-Anzeige getrennt",
    )
    require(
        "async function loadDevice({syncForm = false} = {})" in device,
        "Geräte-Refresh besitzt einen expliziten Form-Sync-Schalter",
    )
    require(
        "if (syncForm && !formDirty)" in device,
        "Ungespeicherte Geräteeingaben werden nicht überschrieben",
    )
    require(
        "() => loadDevice({syncForm: false})" in device
        and "setInterval(loadDevice, 3000)" not in device,
        "3-Sekunden-Auto-Refresh aktualisiert nur Live-/Hardware-/Safety-Daten",
    )
    require(
        "FORM_CONTROL_IDS" in device
        and "markFormDirty()" in device
        and "Ungespeicherte Änderungen · Live-Status läuft weiter" in device,
        "Geräteformular erkennt aktive Benutzereingaben",
    )
    require(
        "refreshInFlight" in device
        and "saveInProgress" in device
        and "refreshEpoch" in device,
        "Geräteseite schützt vor überlappenden Refresh-/Save-Responses",
    )
    require(
        "applyDeviceForm(data);" in device
        and "renderRuntime(data);" in device,
        "Nach erfolgreichem Speichern werden Formular und Runtime bewusst synchronisiert",
    )

    # Sensorseite
    require(
        "async function loadAssignments({syncControls = false} = {})" in sensors,
        "Sensor-Refresh besitzt einen expliziten Controls-Sync-Schalter",
    )
    require(
        "if(syncControls){" in sensors
        and "applyAssignmentControls(data);" in sensors,
        "Dropdowns und Offsets werden nur bei bewusstem Sync übernommen",
    )
    require(
        "syncControls:false" in sensors
        and "setInterval(" in sensors
        and "setInterval(\n    loadAssignments" not in sensors,
        "10-Sekunden-Auto-Refresh überschreibt keine Sensor-Bedienelemente",
    )
    require(
        "OFFSET_DEBOUNCE_MS = 350" in sensors
        and "function queueOffsetSave(key, value)" in sensors,
        "Offset-Eingaben werden mit 350 ms Debounce gebündelt",
    )
    require(
        "inFlight: false" in sensors
        and "pending: null" in sensors
        and "await flushOffsetSave(" in sensors,
        "Offset-Saves werden pro Feld serialisiert und der neueste Wert bleibt erhalten",
    )
    require(
        "input.value =\n        value;" in sensors
        and "queueOffsetSave(" in sensors,
        "Plus/Minus reagiert sofort sichtbar und speichert anschließend gebündelt",
    )
    require(
        "stateLoadInFlight" in sensors
        and "assignmentLoadInFlight" in sensors
        and "assignmentSaveInFlight" in sensors,
        "Sensorseite verhindert überlappende Refresh-/Save-Requests",
    )
    require(
        "await flushAllOffsets();" in sensors
        and "async function manualRefresh()" in sensors,
        "Bewusstes Aktualisieren speichert wartende Offsets vor dem Reload",
    )
    require(
        "loadState,\n    3000" in sensors,
        "RAW- und Korrekturwerte aktualisieren sich weiterhin alle 3 Sekunden",
    )

    # Safety scope
    combined = device + sensors
    require(
        "switch_shelly" not in combined
        and "set_device(" not in combined
        and "core.safety" not in combined,
        "Phase 4R verändert keine Hardware-/Safety-Steuerlogik",
    )

    print("✅ Phase 4R bedienungssicherer Auto-Refresh vollständig")


if __name__ == "__main__":
    main()
