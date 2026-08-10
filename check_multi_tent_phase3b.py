#!/usr/bin/env python3
"""Phase-3B-Regressionstest ohne echte Hardwarezugriffe."""

import json
import os
from pathlib import Path
import tempfile
import time


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="growstar-phase3b-") as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # core.profile erwartet den gemeinsamen Preset-Katalog bereits beim
            # Import. Für den Test genügt ein leerer, valider Katalog.
            Path("profiles.json").write_text(
                json.dumps({"active": None, "profiles": {}}),
                encoding="utf-8",
            )

            from core.tents import DEFAULT_TENT_ID, init_tents, manager
            from core.tent_config import load_tent_config
            from core.runtime import (
                get_default_runtime,
                get_runtime,
                init_runtimes,
            )
            import core.actuators as actuators
            from core.sensor_sources import update_sensor_source
            from threads.main import run_control_cycle

            init_tents()
            manager.add_tent("tent_2", name="Zelt 2")

            meta = manager.get("tent_2")
            require(meta["shadow_enabled"] is False, "Shadow muss standardmäßig AUS sein")
            require(meta["control_enabled"] is False, "Hardware-Control muss AUS sein")

            # Phase 4H erlaubt einen persistenten LIVE-Zielmodus, aber ein
            # solcher Eintrag darf nach einem Neustart das echte Hardware-Gate
            # niemals blind öffnen. Er muss zunächst als ARMING laden.
            raw = manager.snapshot()
            raw["tents"]["tent_2"]["control_enabled"] = True
            Path("tents.json").write_text(
                json.dumps(raw),
                encoding="utf-8",
            )
            init_tents()
            require(
                manager.get("tent_2")["control_enabled"] is True,
                "persistenter LIVE-Zielmodus wurde nicht erhalten",
            )

            init_runtimes()
            arming_rt = get_runtime("tent_2")
            require(arming_rt.control_enabled is False, "ARMING öffnete Hardware beim Boot")
            require(arming_rt.live_requested is True, "LIVE-Zielmodus fehlt in Runtime")
            require(arming_rt.arming is True, "persistiertes LIVE startet nicht als ARMING")

            # Für die historischen Phase-3B-Shadow-Checks die Station wieder
            # kontrolliert auf einen normalen Shadow-Zielmodus setzen.
            manager.set_control_enabled("tent_2", False)
            manager.set_shadow_enabled("tent_2", True)
            init_runtimes()

            rt1 = get_default_runtime()
            rt2 = get_runtime("tent_2")

            require(rt1.control_enabled is True, "tent_1 verlor Hardware-Control")
            require(rt2.control_enabled is False, "tent_2 bekam Hardware-Control")
            require(rt2.shadow_enabled is True, "tent_2 Shadow wurde nicht geladen")

            # Für den Test absichtlich sogar Hardware-Adressen in die Runtime
            # schreiben. Die Aktor-Barriere muss Netzwerkzugriffe trotzdem
            # vollständig verhindern.
            rt2.config["IP_HEATING"] = "192.0.2.10"
            rt2.config["RELAY_HEATING"] = 0

            network_calls = []

            def forbidden_switch(*args, **kwargs):
                network_calls.append((args, kwargs))
                raise AssertionError("Shadow-Runtime hat switch_shelly aufgerufen")

            actuators.switch_shelly = forbidden_switch

            actuators.set_heating(True, "(Shadow-Test)", runtime=rt2)
            require(not network_calls, "Shadow-Aktor hat Netzwerkzugriff versucht")
            require(rt2.shadow_outputs.get("heating") is True, "Shadow-Soll EIN fehlt")
            require(rt2.state.heating_on is False, "realer Heating-State wurde verändert")

            # Jetzt einen kompletten Regelzyklus mit einer echten Controller-
            # Sensorquelle rechnen lassen.
            rt2.config.update({
                "DAY_TEMP": 24.0,
                "NIGHT_TEMP": 24.0,
                "DAY_TEMP_TOL": 1.0,
                "NIGHT_TEMP_TOL": 1.0,
                "DAY_HUM": 60.0,
                "NIGHT_HUM": 60.0,
                "DAY_HUM_TOL": 5.0,
                "NIGHT_HUM_TOL": 5.0,
                "MIN_TEMP": 12.0,
                "MAX_TEMP": 30.0,
                "RAMP_ENABLED": 0,
                "SENSOR_ASSIGNMENTS": {
                    "temperature": {
                        "source_id": "test:tent2",
                        "field": "temperature",
                    },
                    "humidity": {
                        "source_id": "test:tent2",
                        "field": "humidity",
                    },
                },
                "DEVICE_MODES": {
                    "heating": "ENV",
                    "fan": "OFF",
                    "vent": "OFF",
                    "light": "OFF",
                },
            })

            update_sensor_source(
                "test:tent2",
                label="Phase3B Test Sensor",
                source_type="test",
                temperature=15.0,
                humidity=60.0,
            )

            # DB-Schreibfenster im Test überspringen; Datenbankmigration gehört
            # bereits zu Phase 1 und wird hier nicht erneut getestet.
            rt2.state.last_db_write = time.time()

            result = run_control_cycle(
                runtime=rt2,
                now=time.time(),
                shadow=True,
            )

            require(result["mode"] == "shadow", "Regelzyklus lief nicht als Shadow")
            require(rt2.state.live_state["temp"] == 15.0, "tent_2 Temperatur fehlt")
            require(rt2.shadow_outputs.get("heating") is True, "Heizentscheidung falsch")
            require(rt2.state.heating_on is False, "Shadow schaltete realen State")
            require(not network_calls, "Regelzyklus versuchte Hardwarezugriff")
            require(rt2.loop_mode == "shadow", "Runtime-Status nicht auf shadow")
            require(rt2.last_loop_ts is not None, "last_loop_ts fehlt")

            # Read-only Multi-Tent-API isoliert prüfen, wenn Flask in der
            # Testumgebung installiert ist. Auf dem Raspberry ist das immer der
            # Fall; die Build-Sandbox kann bewusst schlanker sein.
            api_tested = False
            try:
                from flask import Flask
                from routes.tents import register as register_tent_routes
            except ModuleNotFoundError:
                print("ℹ️ Flask in Build-Sandbox nicht installiert – API-Laufzeittest übersprungen")
            else:
                app = Flask("phase3b-test")
                register_tent_routes(app)
                client = app.test_client()

                response = client.get("/api/tents")
                require(response.status_code == 200, "/api/tents fehlgeschlagen")
                payload = response.get_json()
                ids = {item["id"] for item in payload["tents"]}
                require(ids == {"tent_1", "tent_2"}, f"API-Zelte falsch: {ids}")

                response = client.get("/api/tents/tent_2/state")
                require(response.status_code == 200, "tent_2 state API fehlgeschlagen")
                state_payload = response.get_json()
                require(state_payload["runtime_mode"] == "shadow", "API meldet nicht shadow")
                require(
                    state_payload["hardware_actuation_blocked"] is True,
                    "API meldet Hardware nicht als blockiert",
                )
                require(
                    state_payload["shadow_outputs"]["heating"] is True,
                    "API zeigt Shadow-Heizentscheidung nicht",
                )

                response = client.get("/api/tents/tent_2/config")
                require(response.status_code == 200, "tent_2 config API fehlgeschlagen")
                cfg_payload = response.get_json()
                require(cfg_payload["control_enabled"] is False, "API Control unerwartet AN")
                api_tested = True

            # Persistenzschema bleibt aus Phase 3A kompatibel.
            cfg2 = load_tent_config("tent_2")
            require(cfg2.get("SENSOR_ASSIGNMENTS") == {}, "Test veränderte echte Tent-Datei")

            print("✅ Phase 3B Shadow-Metadaten persistent und sicher")
            print("✅ Zusätzliche Zelte öffnen Hardware weiterhin nur über das Runtime-Gate")
            print("✅ Persistiertes LIVE startet nach Reboot sicher als ARMING")
            print("✅ Shadow-Aktorik sendet selbst mit IP/Relay keinen Netzwerkbefehl")
            print("✅ Vollständiger tent_2 Regelzyklus rechnet Sensoren/Sollwerte getrennt")
            print("✅ Reale Gerätezustände bleiben im Shadow-Modus unverändert")
            if api_tested:
                print("✅ Read-only /api/tents/... Endpunkte liefern Runtime/Shadow-Status")
            else:
                print("ℹ️ /api/tents/... Runtime-Test erfolgt beim Raspberry-Deployment")
            print("✅ tent_1 bleibt produktiver Hardware-Regelkreis")
            print("✅ Phase 3B Tests vollständig erfolgreich")
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    main()
