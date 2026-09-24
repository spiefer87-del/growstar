#!/usr/bin/env python3
"""Regression für Betriebsart-, Sitzungs- und Klimakontext der Gerätezyklen."""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = type("Timeout", (Exception,), {})
    requests_stub.ConnectionError = type("ConnectionError", (Exception,), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from core.actuators import set_heating
from core.runtime import create_isolated_runtime
from services import grow_events
from services.grow_insights import build_device_activity


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def add_transition(device, state, occurred_at, *, mode, strategy, session):
    enabled = state == "EIN"
    return grow_events.record_event(
        station_id="tent_1",
        occurred_at=occurred_at,
        category="device",
        event_type="actuator_power_changed",
        severity="info",
        title=f"{device.title()} {'eingeschaltet' if enabled else 'ausgeschaltet'}",
        summary="Zyklus-Kontexttest",
        source="actuator_control",
        source_id=device,
        dedupe_key=f"cycle-context:{device}:{state}:{occurred_at}",
        metadata={
            "geraet": device,
            "zustand": state,
            "modus": mode,
            "relaisstrategie": strategy,
            "sitzung": session,
        },
    )


def main():
    runtime = create_isolated_runtime(
        "tent_1",
        name="Zelt 1",
        config_data={
            "IP_HEATING": "192.0.2.20",
            "RELAY_HEATING": 0,
            "DEVICE_MODES": {"heating": "INTERVAL"},
            "DEVICE_PARAMS": {
                "heating": {
                    "interval_night_enabled": True,
                    "control_states": {
                        "interval_a": {"power": True},
                        "interval_b": {"power": True},
                        "interval_a_night": {"power": True},
                        "interval_b_night": {"power": True},
                    },
                },
            },
        },
        save_config_callback=lambda cfg: None,
        control_enabled=True,
        live_requested=True,
    )
    with runtime.state_lock:
        runtime.state.current_profile = "TAG"
        runtime.state.live_state.update({
            "profile": "TAG",
            "temp": 25.2,
            "hum": 58.4,
            "vpd": 1.31,
            "temp_target": 25.5,
            "temp_tol": 0.3,
            "hum_target": 58.0,
            "hum_tol": 3.0,
            "vpd_control": {"mode": "OFF"},
        })

    original_db = grow_events.DB_FILE
    now = 1_700_300_000
    with tempfile.TemporaryDirectory(prefix="growstar-cycle-context-") as temp_dir:
        grow_events.DB_FILE = Path(temp_dir) / "events.db"
        try:
            grow_events.init_grow_event_db()
            with patch("core.actuators.switch_shelly", return_value=True):
                set_heating(True, "(Intervall Phase A)", runtime=runtime)
            grow_events.flush_event_queue(limit=100)

            event = grow_events.list_events(
                station_id="tent_1", category="device", since=0
            )["items"][0]
            metadata = event["metadata"]
            require(
                metadata.get("sitzung")
                and metadata.get("relaisstrategie") == "INTERVALL_DAUERSTROM"
                and metadata.get("phase_a_power") == "EIN"
                and metadata.get("phase_b_power") == "EIN",
                "Intervall ohne Relais-Aus wird mit Sitzung und Phasenstrategie protokolliert",
            )
            require(
                metadata.get("profil") == "TAG"
                and metadata.get("temperatur_c") == 25.2
                and metadata.get("temperatur_soll_c") == 25.5
                and metadata.get("temperatur_abweichung_c") == -0.3,
                "Bestätigte Schaltung erhält Profil-, Klima- und Sollwertkontext",
            )

            activity = build_device_activity(
                station_id="tent_1",
                since=0,
                station_names={"tent_1": "Zelt 1"},
                now=now,
            )
            heating = next(item for item in activity["items"] if item["device"] == "heating")
            require(
                heating["continuous_operation"] is True
                and heating["operation_label"] == "Intervall · Shelly bleibt EIN"
                and heating["average_display"] == "nicht nötig"
                and heating["short_cycle_warning"] is False,
                "Dauerstrom-Intervall erscheint nicht als fehlender oder auffälliger Zyklus",
            )
            require(
                "beiden Intervallphasen" in heating["cycle_note"]
                and "25,2 °C" in heating["climate_context"]
                and "Temp.-Soll 25,5 ± 0,3 °C" in heating["climate_context"],
                "Aktivitätskarte erklärt Betriebsart und letzten Klimakontext",
            )

            add_transition(
                "fan", "EIN", now - 300, mode="ENV",
                strategy="BEDARFSGESTEUERT", session="vor-neustart",
            )
            add_transition(
                "fan", "EIN", now - 120, mode="ENV",
                strategy="BEDARFSGESTEUERT", session="nach-neustart",
            )
            add_transition(
                "fan", "AUS", now - 60, mode="ENV",
                strategy="BEDARFSGESTEUERT", session="nach-neustart",
            )
            for index in range(4):
                started = now - 1_000 + index * 100
                add_transition(
                    "vent", "EIN", started, mode="INTERVAL",
                    strategy="INTERVALL_SCHALTEND", session="intervall",
                )
                add_transition(
                    "vent", "AUS", started + 30, mode="INTERVAL",
                    strategy="INTERVALL_SCHALTEND", session="intervall",
                )

            activity = build_device_activity(
                station_id="tent_1",
                since=0,
                station_names={"tent_1": "Zelt 1"},
                now=now,
            )
            fan = next(item for item in activity["items"] if item["device"] == "fan")
            vent = next(item for item in activity["items"] if item["device"] == "vent")
            require(
                fan["cycles"] == 1
                and fan["average_seconds"] == 60
                and fan["restart_interruptions"] == 1
                and "App-Neustart" in fan["cycle_note"],
                "Ein App-Neustart trennt offene Phasen statt falsche Laufzeit zu erzeugen",
            )
            require(
                vent["cycles"] == 4
                and vent["short_cycles"] == 0
                and vent["warning_eligible_cycles"] == 0
                and vent["short_cycle_warning"] is False,
                "Kurze beabsichtigte Intervallphasen lösen keine ENV-Taktungswarnung aus",
            )
        finally:
            grow_events.DB_FILE = original_db

    template = (ROOT / "templates/grow_events.html").read_text(encoding="utf-8")
    require(
        "{{ item.operation_label }}" in template
        and "{{ item.average_display }}" in template
        and "Beim letzten Relaiswechsel:" in template
        and "Ø EIN ist dort nicht nötig" in template,
        "Oberfläche zeigt Betriebsart, passenden Durchschnitt und Schaltkontext",
    )
    print("✅ INTELLIGENCE.CYCLE-CONTEXT.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
