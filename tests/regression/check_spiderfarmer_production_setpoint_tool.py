#!/usr/bin/env python3
"""Offline regression for the SF.4D.7 production-path test helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/test_spiderfarmer_production_setpoint.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "sf4d7_production_tool",
        TOOL,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def controller_payload():
    return {
        "success": True,
        "tent_id": "tent_1",
        "device": "vent",
        "controller": {
            "assigned": True,
            "target_id": "spiderfarmer:744dbd59d734:fan",
            "provider": "spiderfarmer",
            "family": "fan",
            "online": True,
            "capabilities": ["level", "oscillation"],
            "schema": {
                "level": {
                    "min": 1,
                    "max": 10,
                    "step": 1,
                },
                "oscillation": {
                    "min": 1,
                    "max": 10,
                    "step": 1,
                },
            },
            "setpoints": {
                "level": 7,
            },
        },
    }


def expect_error(tool, callback, text):
    try:
        callback()
    except tool.ProductionPathError:
        print("✅", text)
    else:
        raise AssertionError(text)


def main():
    tool = load_tool()

    url = tool.build_device_url(
        "http://127.0.0.1:8000/",
        "tent_1",
        "vent",
    )

    require(
        url == "http://127.0.0.1:8000/api/tents/tent_1/devices/vent",
        "Tool nutzt exakt die bestehende Growstar-Tent-Geräte-API",
    )

    current = controller_payload()
    controller = tool.validate_preflight(
        current,
        requested_level=4,
        requested_oscillation=5,
    )

    require(
        controller["provider"] == "spiderfarmer"
        and controller["family"] == "fan",
        "Preflight akzeptiert nur die bestehende Spider-Farmer-Fan-Zuordnung",
    )

    payload = tool.build_payload(
        level=4,
        oscillation=5,
    )

    require(
        payload == {
            "controller_setpoints": {
                "level": 4,
                "oscillation": 5,
            },
        },
        "Produktions-Testpayload enthält ausschließlich generische controller_setpoints",
    )

    payload_without_oscillation = tool.build_payload(
        level=7,
    )
    require(
        payload_without_oscillation == {
            "controller_setpoints": {
                "level": 7,
            },
        },
        "Level-Test verändert keine Oszillation, wenn sie nicht ausdrücklich angefordert wurde",
    )

    for invalid in (0, 11, 60):
        expect_error(
            tool,
            lambda invalid=invalid: tool.validate_preflight(
                current,
                requested_level=invalid,
            ),
            f"Preflight blockiert ungültiges Fan-Level {invalid}",
        )

    no_assignment = controller_payload()
    no_assignment["controller"]["assigned"] = False
    expect_error(
        tool,
        lambda: tool.validate_preflight(
            no_assignment,
            requested_level=4,
        ),
        "Tool verweigert Schreibtest ohne Controller-Zuordnung",
    )

    wrong_provider = controller_payload()
    wrong_provider["controller"]["provider"] = "other"
    expect_error(
        tool,
        lambda: tool.validate_preflight(
            wrong_provider,
            requested_level=4,
        ),
        "Tool verweigert Schreibtest über einen fremden Provider",
    )

    wrong_family = controller_payload()
    wrong_family["controller"]["family"] = "blower"
    expect_error(
        tool,
        lambda: tool.validate_preflight(
            wrong_family,
            requested_level=4,
        ),
        "Tool verweigert Fan-Schreibtest gegen eine andere Controller-Familie",
    )

    apply = tool.evaluate_apply_response({
        "success": True,
        "controller_apply": {
            "success": True,
            "status": "sent",
            "verified": False,
        },
    })

    require(
        apply["status"] == "sent",
        "Tool wertet den bestehenden controller_apply-Rückkanal aus",
    )

    expect_error(
        tool,
        lambda: tool.evaluate_apply_response({
            "success": True,
            "controller_apply": {
                "success": False,
                "status": "bridge_error",
                "message": "test",
            },
        }),
        "Bridge-Fehler werden nicht als erfolgreicher Produktions-Test ausgegeben",
    )

    source = TOOL.read_text(encoding="utf-8")

    forbidden = (
        "command.sock",
        "setConfigField",
        "build_publish",
        "compile_controller_command",
        "AF_UNIX",
        "mqtt",
    )

    for token in forbidden:
        require(
            token not in source,
            f"Produktions-Testtool besitzt keinen parallelen Low-Level-Pfad: {token}",
        )

    route_text = (
        ROOT / "routes/device.py"
    ).read_text(encoding="utf-8")

    require(
        '@app.route("/api/tents/<tent_id>/devices/<device>", methods=["GET", "POST"])'
        in route_text,
        "Bestehende Tent-Geräte-API ist weiterhin der getestete Einstiegspunkt",
    )

    require(
        "send_controller_setpoints(" in route_text
        and 'setpoints=requested_setpoints' in route_text,
        "Bestehende Route reicht controller_setpoints an den Provider-Adapter weiter",
    )

    adapter_text = (
        ROOT / "services/spiderfarmer_commands.py"
    ).read_text(encoding="utf-8")

    require(
        '"action": "set_controller"' in adapter_text
        and '"setpoints": dict(setpoints or {})' in adapter_text,
        "Bestehender Spider-Farmer-Adapter bleibt der einzige Produktions-Command-Adapter",
    )

    print(
        "✅ Spider Farmer SF.4D.7 Produktionspfad-Testtool Regression vollständig erfolgreich"
    )


if __name__ == "__main__":
    main()
