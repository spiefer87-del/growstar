#!/usr/bin/env python3
"""Regression for Spider Farmer SF.3C native read-only UI integration."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import routes.dashboard as dashboard
import services.spiderfarmer as spiderfarmer


SESSION = "744dbd59d734"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def sample_state():
    return {
        "schema": 1,
        "phase": "SF.2",
        "read_only": True,
        "controllers": {
            SESSION: {
                "id": SESSION,
                "pid": "744DBD59D734",
                "prefix": "CB",
                "last_seen": "2026-08-23T00:10:00Z",
                "live": {
                    "sensor": {
                        "temperature_c": 21.7,
                        "humidity_percent": 66.4,
                        "vpd_kpa": 0.87,
                    },
                    "light": {
                        "on": 0,
                        "level": 0,
                    },
                    "fan": {
                        "on": 1,
                        "level": 3,
                        "mode_type": 2,
                    },
                    "blower": {
                        "on": 1,
                        "level": 50,
                        "mode_type": 8,
                    },
                },
                "config": {
                    "fan": {
                        "standby_level": 3,
                        "run_level": 7,
                        "oscillation_level": 4,
                        "natural_wind": 1,
                        "cycle": {
                            "weekmask": 127,
                            "start_time_s": 20100,
                            "run_duration_s": 90,
                            "off_duration_s": 270,
                            "executions": 52,
                        },
                    }
                },
            }
        },
    }


def main():
    dashboard_path = ROOT / "routes/dashboard.py"
    template_path = ROOT / "templates/spiderfarmer.html"
    system_path = ROOT / "templates/system.html"
    release_path = ROOT / "core/releases/r_3_11_9_sf_3c.py"

    for path in (
        dashboard_path,
        template_path,
        system_path,
        release_path,
    ):
        require(
            path.is_file(),
            f"{path.relative_to(ROOT)} vorhanden",
        )

    dashboard_text = dashboard_path.read_text(encoding="utf-8")
    template_text = template_path.read_text(encoding="utf-8")
    system_text = system_path.read_text(encoding="utf-8")

    ast.parse(dashboard_text, filename=str(dashboard_path))

    require(
        '@app.get("/system/spiderfarmer")' in dashboard_text,
        "SF.3C registriert native Spider-Farmer-Systemseite",
    )

    require(
        '@app.get("/api/spiderfarmer/controllers")' in dashboard_text,
        "SF.3C registriert genau den read-only Controller-GET-Pfad",
    )

    require(
        "/system/spiderfarmer" in system_text
        and "Spider Farmer" in system_text,
        "Systemübersicht besitzt sichtbaren Spider-Farmer-Einstieg",
    )

    require(
        "/api/spiderfarmer/controllers" in template_text,
        "Spider-Farmer-UI liest den nativen Controller-GET-Pfad",
    )

    require(
        "effective" in template_text
        and "oscillation_level" in template_text
        and "standby_level" in template_text
        and "run_level" in template_text,
        "UI stellt normalisierte effective-Werte inklusive Ventilator-Config dar",
    )

    require(
        "setInterval(loadControllers, 5000)" in template_text,
        "UI aktualisiert den read-only Controller-State periodisch",
    )

    for method in ("@app.post(", "@app.put(", "@app.patch(", "@app.delete("):
        require(
            not (
                method in dashboard_text
                and "spiderfarmer" in dashboard_text[
                    max(0, dashboard_text.find(method) - 200):
                    dashboard_text.find(method) + 500
                ]
            ),
            f"SF.3C besitzt keinen Spider-Farmer-{method[5:-1].upper()}-Pfad",
        )

    combined = dashboard_text + "\n" + template_text

    for forbidden in (
        "asyncio.open_connection",
        "socket.send",
        "writer.write",
        "build_publish",
        "encode_publish",
        "setConfigField(",
        "paho",
    ):
        require(
            forbidden not in combined,
            f"SF.3C UI besitzt keinen Command-/Transportpfad: {forbidden}",
        )

    with tempfile.TemporaryDirectory() as td:
        state_path = Path(td) / "spiderfarmer_state.json"
        state_path.write_text(
            json.dumps(sample_state()),
            encoding="utf-8",
        )

        controllers = spiderfarmer.list_controllers(
            state_path
        )

        require(
            len(controllers) == 1,
            "Bestehender Spider-Farmer-Service liefert genau einen Testcontroller",
        )

        controller = controllers[0]

        require(
            controller["id"] == SESSION
            and controller["device_count"] >= 4,
            "Controller-Identität und Geräteinventar bleiben kanonisch",
        )

        fan = next(
            item
            for item in controller["devices"]
            if item["id"] == "fan"
        )

        require(
            fan["effective"]["level"] == 3
            and fan["effective"]["run_level"] == 7
            and fan["effective"]["standby_level"] == 3
            and fan["effective"]["oscillation_level"] == 4,
            "SF.3C übernimmt Live-Level und persistierte Ventilator-Konfiguration gemeinsam",
        )

        original = dashboard.list_spiderfarmer_controllers
        try:
            dashboard.list_spiderfarmer_controllers = (
                lambda: controllers
            )
            payload = dashboard._spiderfarmer_controllers_payload()
        finally:
            dashboard.list_spiderfarmer_controllers = original

        require(
            payload["success"] is True
            and payload["phase"] == "SF.3C"
            and payload["read_only"] is True,
            "SF.3C API-Payload kennzeichnet Phase und read-only explizit",
        )

        require(
            payload["controllers"][0]["devices"]
            == controllers[0]["devices"],
            "SF.3C API verwendet das bestehende Geräte-Modell ohne Parallelmodell",
        )

    print("✅ Spider Farmer SF.3C native read-only UI Regression vollständig erfolgreich")


if __name__ == "__main__":
    main()
