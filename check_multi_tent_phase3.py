#!/usr/bin/env python3
"""Isolierter Phase-3-Test ohne echte Shelly-/MQTT-/Bluetooth-Zugriffe."""

import json
import os
from pathlib import Path
import tempfile


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    project_root = Path(__file__).resolve().parent

    with tempfile.TemporaryDirectory(prefix="growstar-phase3-") as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # Imports absichtlich erst nach chdir: config.json/tents.json des
            # echten Systems werden dadurch weder gelesen noch verändert.
            from core.tents import (
                DEFAULT_TENT_ID,
                TentManager,
                init_tents,
                manager,
                validate_tent_id,
            )
            from core.tent_config import (
                ensure_tent_config,
                load_tent_config,
            )
            from core.runtime import (
                get_default_runtime,
                get_runtime,
                init_runtimes,
                list_runtimes,
            )

            init_tents()
            default_meta = manager.get(DEFAULT_TENT_ID)
            require(default_meta is not None, "tent_1 fehlt")
            require(default_meta["enabled"] is True, "tent_1 muss enabled sein")
            require(
                default_meta["control_enabled"] is True,
                "tent_1 muss für Rückwärtskompatibilität Control behalten",
            )

            tent2 = manager.add_tent("tent_2", name="Zelt 2")
            require(tent2["control_enabled"] is False, "tent_2 Control muss AUS sein")
            require(tent2["enabled"] is True, "tent_2 Runtime soll ladbar sein")

            config_path = ensure_tent_config("tent_2")
            require(config_path == "tent_configs/tent_2.json", "falscher Config-Pfad")
            require(Path(config_path).exists(), "tent_2 Config wurde nicht angelegt")

            cfg2 = load_tent_config("tent_2")
            require(cfg2.get("SENSOR_ASSIGNMENTS") == {}, "Sensoren müssen leer starten")
            require(int(cfg2.get("RAMP_ENABLED", 1)) == 0, "Rampe muss AUS starten")
            require(
                all(mode == "OFF" for mode in cfg2.get("DEVICE_MODES", {}).values()),
                "Alle Gerätemodi müssen OFF starten",
            )
            require(
                not any(k.startswith("IP_") or k.startswith("RELAY_") for k in cfg2),
                "Neue Zelt-Config darf keine Hardware-Adressen erben",
            )

            runtimes = init_runtimes()
            runtime_ids = {rt.tent_id for rt in runtimes}
            require(runtime_ids == {"tent_1", "tent_2"}, f"Runtimes falsch: {runtime_ids}")

            rt1 = get_default_runtime()
            rt2 = get_runtime("tent_2")

            require(rt1.state is not rt2.state, "State muss pro Zelt getrennt sein")
            require(rt1.config is not rt2.config, "Config muss pro Zelt getrennt sein")
            require(rt1.state_lock is not rt2.state_lock, "Locks müssen getrennt sein")
            require(rt1.control_enabled is True, "tent_1 Control unerwartet AUS")
            require(rt2.control_enabled is False, "tent_2 Control unerwartet AN")

            old_default_temp = rt1.config.get("DAY_TEMP")
            rt2.config["DAY_TEMP"] = 29.25
            rt2.config["SENSOR_ASSIGNMENTS"] = {
                "temperature": {
                    "source_id": "blu:test-temp",
                    "field": "temperature",
                }
            }
            require(rt2.persist_config() is True, "tent_2 Config wurde nicht persistiert")

            reloaded = load_tent_config("tent_2")
            require(reloaded["DAY_TEMP"] == 29.25, "DAY_TEMP nicht persistent")
            require(
                reloaded["SENSOR_ASSIGNMENTS"]["temperature"]["source_id"]
                == "blu:test-temp",
                "Sensorzuweisung nicht persistent",
            )
            require(
                rt1.config.get("DAY_TEMP") == old_default_temp,
                "tent_2 Änderung hat tent_1 verändert",
            )

            # init_runtimes ist absichtlich idempotent und lädt persistierte
            # Werte bei einem erneuten Initialisieren wieder ein.
            init_runtimes()
            rt2_reloaded = get_runtime("tent_2")
            require(rt2_reloaded.config["DAY_TEMP"] == 29.25, "Runtime-Reload verlor Config")
            require(rt2_reloaded.control_enabled is False, "Reload aktivierte Hardware-Control")

            # tents.json ist auch mit einer neuen Manager-Instanz lesbar.
            second_manager = TentManager("tents.json")
            snapshot = second_manager.load()
            require("tent_2" in snapshot["tents"], "tent_2 fehlt nach Manager-Reload")
            require(
                snapshot["tents"]["tent_2"]["control_enabled"] is False,
                "Manager-Reload aktivierte Control",
            )

            # Unsichere IDs dürfen nie einen Dateipfad erzeugen können.
            rejected = 0
            for bad_id in ("../tent_3", "tent/3", "", "tent 3"):
                try:
                    validate_tent_id(bad_id)
                except ValueError:
                    rejected += 1
            require(rejected == 4, "Unsichere Tent-IDs wurden nicht vollständig blockiert")

            # Legacy tent_1 bleibt weiterhin außerhalb tent_configs.
            require(
                not Path("tent_configs/tent_1.json").exists(),
                "tent_1 darf nicht stillschweigend migriert werden",
            )

            print("✅ Phase 3 Tent-Metadaten persistent")
            print("✅ tent_1 bleibt rückwärtskompatibel auf config.json")
            print("✅ tent_2 besitzt eigene persistente Config")
            print("✅ Neue Zelte starten ohne Sensor-/Hardware-Zuordnung")
            print("✅ State / Config / Locks bleiben pro Zelt isoliert")
            print("✅ tent_2 Hardware-Control bleibt ausdrücklich deaktiviert")
            print("✅ Tent-ID Path-Traversal-Schutz OK")
            print("✅ Phase 3 Tests vollständig erfolgreich")
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    main()
