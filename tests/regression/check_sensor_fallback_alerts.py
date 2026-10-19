#!/usr/bin/env python3
"""Watchdog/Telegram transitions for a station's primary and fallback sensors."""

import time
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import sensor_sources, watchdog_health
from services import alerts, notifications


def require(condition, label):
    assert condition, label
    print("✅", label)


def runtime():
    return SimpleNamespace(
        tent_id="tent_2", name="Zelt 2", enabled=True,
        control_enabled=True, shadow_enabled=False,
        config={"SENSOR_ASSIGNMENTS": {
            "temperature": {"source_id": "mqtt:primary", "field": "temperature", "label": "Hauptfühler",
                            "fallback": {"source_id": "mqtt:secondary", "field": "temperature", "label": "Ersatzfühler"}},
            "humidity": {"source_id": "mqtt:humidity", "field": "humidity", "label": "Feuchtefühler"},
        }},
        state=SimpleNamespace(live_state={}, last_ds_time=0, last_dht_time=0,
                              temp_stale=True, hum_stale=True),
        state_lock=RLock(),
    )


def main():
    rt = runtime()
    now = time.time()
    sources = {
        "mqtt:primary": {"temperature": 24.0, "last_seen": now},
        "mqtt:secondary": {"temperature": 23.8, "last_seen": now},
        "mqtt:humidity": {"humidity": 57.0, "last_seen": now},
    }
    sent = []
    settings = {"telegram": {"enabled": True, "bot_token": "test", "chat_id": "test"},
                "rules": {"sensor_fallback": True, "sensor_stale": True},
                "repeat_minutes": 60, "send_recovery": True}
    def snapshot():
        with patch.object(watchdog_health, "_loop_health", return_value={"state": "ok", "stale": False}), \
             patch.object(watchdog_health, "_config_health", return_value={"ok": True, "state": "ok"}), \
             patch.object(watchdog_health, "_hardware_health", return_value={"state": "ok", "endpoints": []}), \
             patch.object(watchdog_health, "_safety_health", return_value={"state": "ok", "active": False}):
            return {"stations": [watchdog_health.station_health(rt)],
                    "controller": {"threads": {}, "mqtt": {"stale": False}}}

    with patch.object(sensor_sources, "resolve_runtime", side_effect=lambda runtime: runtime), \
         patch.object(sensor_sources, "get_sensor_source", side_effect=lambda key: sources.get(key)), \
         patch.object(alerts, "_ensure_loaded", return_value=None), \
         patch.object(alerts, "_atomic_save", return_value=None), \
         patch.object(alerts, "_timeline_alarm", return_value=None), \
         patch.object(alerts, "load_notification_settings", return_value=settings), \
         patch.object(alerts, "enqueue_notification", side_effect=lambda message, **kwargs: sent.append((message,kwargs)) or True), \
         patch.object(alerts, "_station_alarm_config", return_value={}):
        alerts._ACTIVE.clear()
        alerts._HISTORY.clear()
        alerts._ENGINE_STARTED_AT = None

        sensor_sources.apply_sensor_assignments(rt)
        require(snapshot()["stations"][0]["temperature"]["state"] == "ok",
                "Primärsensor ist im Watchdog normal")
        alerts.process_watchdog_snapshot(snapshot(), now=now)
        require(not sent, "Ohne Umschaltung keine Telegram-Nachricht")

        sources["mqtt:primary"]["last_seen"] = now - sensor_sources.SENSOR_TIMEOUT - 2
        sensor_sources.apply_sensor_assignments(rt)
        station = snapshot()["stations"][0]
        failover_at = station["sensor_fallbacks"]["temperature"]["since"]
        require(station["temperature"]["state"] == "warn" and
                not station["temperature"]["stale"] and
                station["sensor_fallbacks"]["temperature"]["active"] and failover_at,
                "Watchdog meldet Ersatzsensor als Warnung, nicht als Totalausfall")
        alerts.process_watchdog_snapshot(snapshot(), now=now+5)
        require(len(sent) == 1 and sent[0][1]["kind"] == "alarm" and
                "Hauptfühler" in sent[0][0] and "Ersatzfühler" in sent[0][0] and
                "Umschaltung:" in sent[0][0],
                "Telegram erhält einmalig Station, Sensoren und Umschaltzeit")
        sensor_sources.apply_sensor_assignments(rt)
        require(snapshot()["stations"][0]["sensor_fallbacks"]["temperature"]["since"] == failover_at,
                "Umschaltzeit bleibt bei weiteren Abfragen stabil")
        alerts.process_watchdog_snapshot(snapshot(), now=now+10)
        require(len(sent) == 1, "Kein Alarm bei jedem Regelzyklus erneut")

        sources["mqtt:secondary"]["last_seen"] = now - sensor_sources.SENSOR_TIMEOUT - 2
        sensor_sources.apply_sensor_assignments(rt)
        station = snapshot()["stations"][0]
        require(station["temperature"]["stale"] and not station["sensor_fallbacks"]["temperature"]["active"],
                "Wenn beide ausfallen, meldet Watchdog den Sensorausfall")
        alerts.process_watchdog_snapshot(snapshot(), now=now+15)
        require(any("beide keinen gültigen Wert" in message for message,_ in sent) and
                not any(kwargs["kind"] == "recovery" for _,kwargs in sent),
                "Telegram meldet beide Sensoren ohne Daten und sendet keine falsche Entwarnung")

        sources["mqtt:secondary"]["last_seen"] = time.time()
        sensor_sources.apply_sensor_assignments(rt)
        alerts.process_watchdog_snapshot(snapshot(), now=now+20)
        require(any(kwargs["kind"] == "alarm" and "Fallback-Sensor aktiv" in message
                    for message,kwargs in sent[2:]),
                "Wieder aktiver Ersatzsensor wird nach Totalausfall erneut gemeldet")

        sources["mqtt:primary"]["last_seen"] = time.time()
        sensor_sources.apply_sensor_assignments(rt)
        alerts.process_watchdog_snapshot(snapshot(), now=now+25)
        require(any(kwargs["kind"] == "recovery" and "Primärsensor liefert wieder" in message
                    for message,kwargs in sent),
                "Rückkehr zur Hauptquelle erzeugt eine passende Entwarnung")

        station = snapshot()["stations"][0]
        station["sensor_fallbacks"]["water_temperature"] = {
            "configured": True, "active": True, "unavailable": False,
            "primary_label": "Tank A", "fallback_label": "Tank B", "since": now,
        }
        optional = alerts.extract_alarm_candidates({"stations": [station],
                                                     "controller": {"threads": {}, "mqtt": {"stale": False}}})
        require("station:tent_2:sensor:water_temperature:fallback" in optional,
                "Auch optionale Messgrößen lösen einen Fallback-Alarm aus")
        station["sensor_fallbacks"]["water_temperature"].update(active=False, unavailable=True)
        optional = alerts.extract_alarm_candidates({"stations": [station],
                                                     "controller": {"threads": {}, "mqtt": {"stale": False}}})
        require("station:tent_2:sensor:water_temperature:fallback_unavailable" in optional,
                "Bei zwei ausgefallenen Tankfühlern folgt ein eigener Sensorausfall-Alarm")
        require(not alerts._notifications_available({**settings, "rules": {"sensor_fallback": False}}, "sensor_fallback"),
                "Die Fallback-Telegramregel lässt sich unabhängig deaktivieren")

        with patch.object(notifications, "telegram_credentials", return_value=settings["telegram"]), \
             patch.object(notifications, "send_message") as telegram:
            outcome = notifications._deliver({"text": sent[0][0]})
            require(outcome == "sent" and telegram.call_args.args[2] == sent[0][0],
                    "Notification-Worker übergibt denselben Text an Telegram")

    print("✅ SENSOR.FALLBACK.ALERTS.1 erfolgreich")


if __name__ == "__main__":
    main()
