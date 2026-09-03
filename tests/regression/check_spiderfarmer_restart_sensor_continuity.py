#!/usr/bin/env python3
"""Regression for timestamp-safe D734 sensor continuity across restarts."""

from copy import deepcopy
import datetime
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import core.context as context
import core.state as controller_state
from bridge.spiderfarmer.diagnostics import BridgeDiagnostics
from core.config import DEFAULT_CONFIG
from core.constants import SENSOR_TIMEOUT
from core.runtime import TentRuntime
from core.sensor_sources import (
    _source_is_fresh,
    apply_sensor_assignments,
    update_sensor_source,
)
from core.state import create_runtime_state
from services import spiderfarmer


SESSION = "744dbd59d734"
SOURCE_ID = "spiderfarmer:744dbd59d734:environment"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def iso_timestamp(epoch):
    return (
        datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def persisted_state(last_seen):
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {
            SESSION: {
                "id": SESSION,
                "pid": "744DBD59D734",
                "prefix": "CB",
                "last_seen": last_seen,
                "live": {
                    "sensor": {
                        "temperature_c": 23.9,
                        "humidity_percent": 70.5,
                        "vpd_kpa": 0.87,
                    },
                    "fan": {"on": 1, "level": 6},
                },
                "config": {
                    "fan": {
                        "on": 1,
                        "level": 6,
                        "run_level": 5,
                        "standby_level": 3,
                    }
                },
            }
        },
    }


def runtime_for_d734():
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["SENSOR_ASSIGNMENTS"] = {
        "temperature": {
            "source_id": SOURCE_ID,
            "field": "temperature",
            "label": "Spider Farmer GGS D734",
        },
        "humidity": {
            "source_id": SOURCE_ID,
            "field": "humidity",
            "label": "Spider Farmer GGS D734",
        },
    }
    return TentRuntime(
        tent_id="tent_restart_test",
        name="Restart Test",
        state=create_runtime_state(),
        config=cfg,
        state_lock=context.state_lock,
        control_enabled=False,
    )


def main():
    now = time.time()
    sample_epoch = int(now - 70)
    last_seen = iso_timestamp(sample_epoch)

    with tempfile.TemporaryDirectory() as td:
        state_path = Path(td) / "spiderfarmer_state.json"
        state_path.write_text(
            json.dumps(persisted_state(last_seen)),
            encoding="utf-8",
        )

        restarted = BridgeDiagnostics(td)
        restored = restarted.growstar_state["controllers"][SESSION]

        require(
            restored["last_seen"] == last_seen
            and restored["live"]["sensor"]["temperature_c"] == 23.9,
            "Bridge-Neustart erhält D734-Liveprobe mit unverändertem Zeitstempel",
        )

        spiderfarmer.reset_sync_cache()
        captured = []

        def capture_source(source_id, **kwargs):
            captured.append((source_id, kwargs))
            return {
                "id": source_id,
                "temperature": kwargs["temperature"],
                "humidity": kwargs["humidity"],
            }

        with mock.patch.object(
            spiderfarmer,
            "update_sensor_source",
            side_effect=capture_source,
        ):
            result = spiderfarmer.sync_sensor_sources(
                state_path,
                now=now,
            )

        require(
            len(result["published"]) == 1
            and captured[0][0] == SOURCE_ID
            and captured[0][1]["observed_at"] == float(sample_epoch),
            "Adapter reicht das tatsächliche Alter weiter statt den Neustartzeitpunkt",
        )

    with context.state_lock:
        previous_sources = deepcopy(
            controller_state.live_state.get("sensor_sources", {})
        )
        controller_state.live_state["sensor_sources"] = {}

    try:
        with mock.patch("core.sensor_sources.time.time", return_value=now):
            source = update_sensor_source(
                SOURCE_ID,
                label="Spider Farmer GGS D734",
                source_type="spiderfarmer",
                temperature=23.9,
                humidity=70.5,
                observed_at=sample_epoch,
            )

        require(
            source["last_seen"] == float(sample_epoch)
            and _source_is_fresh(source, now=now),
            "70 Sekunden alte Probe bleibt innerhalb des normalen Sensorfensters frisch",
        )

        runtime = runtime_for_d734()
        with mock.patch("core.sensor_sources.time.time", return_value=now):
            changed = apply_sensor_assignments(runtime=runtime)

        require(
            changed
            and runtime.state.live_state["temp"] == 23.9
            and runtime.state.live_state["hum"] == 70.5,
            "Gespeicherte D734-Zuweisung funktioniert nach Neustart ohne Pico-Umschaltung",
        )

        require(
            not _source_is_fresh(
                source,
                now=sample_epoch + SENSOR_TIMEOUT + 0.1,
            ),
            "Nach exakt demselben 120-Sekunden-Limit bleibt der Failsafe erhalten",
        )

        future_source = dict(source, last_seen=now + 30)
        require(
            not _source_is_fresh(future_source, now=now),
            "Zeitstempel aus der Zukunft werden nicht als frisch akzeptiert",
        )

        with mock.patch("core.sensor_sources.time.time", return_value=now):
            newer = update_sensor_source(
                SOURCE_ID,
                temperature=24.2,
                humidity=69.0,
                observed_at=now - 5,
            )
            protected = update_sensor_source(
                SOURCE_ID,
                temperature=10.0,
                humidity=10.0,
                observed_at=sample_epoch,
            )

        require(
            protected["last_seen"] == newer["last_seen"]
            and protected["temperature"] == 24.2
            and protected["humidity"] == 69.0,
            "Verzögerter Persistenzstand kann keine neuere Liveprobe überschreiben",
        )
    finally:
        with context.state_lock:
            controller_state.live_state["sensor_sources"] = previous_sources

    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    seed_pos = app_text.index("sync_spiderfarmer_sensor_sources_once()")
    safety_pos = app_text.index('"growstar-safety"')
    require(
        seed_pos < safety_pos
        and '"growstar-spiderfarmer-sensors"' in app_text,
        "Start-Sync läuft vor Safety und der schnelle Folge-Thread ist registriert",
    )

    thread_text = (ROOT / "threads/spiderfarmer.py").read_text(
        encoding="utf-8"
    )
    require(
        "SPIDERFARMER_SYNC_INTERVAL = 2.0" in thread_text,
        "Neue D734-Proben werden spätestens im kurzen Zwei-Sekunden-Takt erkannt",
    )

    service_text = (
        ROOT / "install/growstar-spiderfarmer.service.in"
    ).read_text(encoding="utf-8")
    require(
        "PartOf=growstar.service" in service_text,
        "Bestehender Bridge-/Writer-Neustartschutz bleibt unverändert erhalten",
    )

    print("✅ Growstar 3.16.5 / SF.RESTART.1 vollständig geprüft")


if __name__ == "__main__":
    main()
