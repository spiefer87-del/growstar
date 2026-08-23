#!/usr/bin/env python3
"""SF.4D.7: controlled end-to-end test through Growstar's production HTTP path.

This tool deliberately does NOT talk to the Spider Farmer command socket and
does NOT build MQTT packets. It calls the existing Growstar device API, exactly
the layer used by the normal device detail UI:

    HTTP device API
      -> routes.device._save_device()
      -> services.spiderfarmer_commands.send_controller_setpoints()
      -> existing private bridge command socket
      -> existing controller MQTT session

The test is dry-run by default. A real write requires --yes.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib import error, parse, request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class ProductionPathError(RuntimeError):
    """Raised when the existing Growstar production path is not ready."""


def build_device_url(base_url, tent_id, device):
    base = str(base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    tent = parse.quote(str(tent_id or "").strip(), safe="")
    dev = parse.quote(str(device or "").strip(), safe="")

    if not tent:
        raise ProductionPathError("tent_id fehlt")
    if not dev:
        raise ProductionPathError("device fehlt")

    return f"{base}/api/tents/{tent}/devices/{dev}"


def request_json(url, *, method="GET", payload=None, timeout=5.0):
    body = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(
        url,
        data=body,
        headers=headers,
        method=str(method).upper(),
    )

    try:
        with request.urlopen(req, timeout=float(timeout)) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProductionPathError(
            f"Growstar HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except error.URLError as exc:
        raise ProductionPathError(
            f"Growstar API nicht erreichbar: {exc.reason}"
        ) from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionPathError(
            "Growstar API lieferte keine gültige JSON-Antwort"
        ) from exc

    if not isinstance(data, dict):
        raise ProductionPathError(
            "Growstar API lieferte kein JSON-Objekt"
        )

    return data


def validate_preflight(data, *, requested_level=None, requested_oscillation=None):
    if not isinstance(data, dict) or not data.get("success"):
        raise ProductionPathError(
            "Geräte-GET war nicht erfolgreich"
        )

    controller = data.get("controller")
    if not isinstance(controller, dict):
        raise ProductionPathError(
            "Geräte-Payload enthält keinen Controller-Kontext"
        )

    if not controller.get("assigned"):
        raise ProductionPathError(
            "Dem Growstar-Gerät ist kein Controller zugeordnet"
        )

    if controller.get("provider") != "spiderfarmer":
        raise ProductionPathError(
            "Der zugeordnete Controller ist kein Spider-Farmer-Controller"
        )

    if controller.get("family") != "fan":
        raise ProductionPathError(
            f"Erwartete Controller-Familie 'fan', erhalten: "
            f"{controller.get('family')!r}"
        )

    schema = controller.get("schema")
    if not isinstance(schema, dict):
        raise ProductionPathError(
            "Controller-Schema fehlt"
        )

    if "level" not in schema:
        raise ProductionPathError(
            "Controller unterstützt keinen Growstar-Level-Sollwert"
        )

    if requested_level is not None:
        validate_schema_value(
            "level",
            requested_level,
            schema.get("level") or {},
        )

    if requested_oscillation is not None:
        if "oscillation" not in schema:
            raise ProductionPathError(
                "Controller unterstützt keinen Oszillations-Sollwert"
            )
        validate_schema_value(
            "oscillation",
            requested_oscillation,
            schema.get("oscillation") or {},
        )

    return controller


def validate_schema_value(name, value, spec):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ProductionPathError(
            f"{name} muss eine ganze Zahl sein"
        ) from exc

    minimum = spec.get("min")
    maximum = spec.get("max")

    if minimum is not None and number < int(minimum):
        raise ProductionPathError(
            f"{name}={number} liegt unter Minimum {minimum}"
        )

    if maximum is not None and number > int(maximum):
        raise ProductionPathError(
            f"{name}={number} liegt über Maximum {maximum}"
        )

    return number


def build_payload(*, level, oscillation=None):
    setpoints = {
        "level": int(level),
    }

    if oscillation is not None:
        setpoints["oscillation"] = int(oscillation)

    return {
        "controller_setpoints": setpoints,
    }


def summarize_preflight(data, controller):
    return {
        "tent_id": data.get("tent_id"),
        "device": data.get("device"),
        "controller_target": controller.get("target_id"),
        "provider": controller.get("provider"),
        "family": controller.get("family"),
        "online": controller.get("online"),
        "capabilities": controller.get("capabilities") or [],
        "current_setpoints": controller.get("setpoints") or {},
        "schema": controller.get("schema") or {},
    }


def evaluate_apply_response(data):
    if not isinstance(data, dict) or not data.get("success"):
        raise ProductionPathError(
            "Growstar-Geräte-POST war nicht erfolgreich"
        )

    apply = data.get("controller_apply")
    if not isinstance(apply, dict):
        raise ProductionPathError(
            "Growstar-Antwort enthält keinen controller_apply-Status"
        )

    if not apply.get("success"):
        raise ProductionPathError(
            "Controller-Schreibpfad meldet Fehler: "
            + str(
                apply.get("message")
                or apply.get("status")
                or apply
            )
        )

    return apply


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Testet einen Spider-Farmer-Ventilator ausschließlich über den "
            "normalen Growstar-Geräte-API-/Produktionspfad."
        )
    )
    parser.add_argument(
        "--tent",
        default="tent_1",
        help="Growstar-Tent-ID (Standard: tent_1)",
    )
    parser.add_argument(
        "--device",
        default="vent",
        help="Logisches Growstar-Gerät (Standard: vent)",
    )
    parser.add_argument(
        "--level",
        type=int,
        required=True,
        help="Ventilatorstufe auf der Growstar/GGS-Skala L1 bis L10",
    )
    parser.add_argument(
        "--oscillation",
        type=int,
        default=None,
        help="Optionale Oszillationsstufe L1 bis L10",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=(
            "Lokale Growstar-HTTP-Basis "
            f"(Standard: {DEFAULT_BASE_URL})"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP-Timeout in Sekunden (Standard: 5)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Erst mit diesem Flag wird der reale POST ausgeführt",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    try:
        url = build_device_url(
            args.base_url,
            args.tent,
            args.device,
        )

        current = request_json(
            url,
            timeout=args.timeout,
        )

        controller = validate_preflight(
            current,
            requested_level=args.level,
            requested_oscillation=args.oscillation,
        )

        payload = build_payload(
            level=args.level,
            oscillation=args.oscillation,
        )

        print("=== SF.4D.7 PRODUKTIONS-PREFLIGHT ===")
        print(
            json.dumps(
                summarize_preflight(current, controller),
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print("=== GEPLANTER GROWSTAR-POST ===")
        print("URL:", url)
        print(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )
        )

        if not args.yes:
            print()
            print(
                "DRY-RUN: Es wurde NICHT geschrieben. "
                "Für den echten Produktionspfad denselben Befehl mit --yes "
                "wiederholen."
            )
            return 0

        result = request_json(
            url,
            method="POST",
            payload=payload,
            timeout=args.timeout,
        )

        apply = evaluate_apply_response(result)

        print()
        print("=== CONTROLLER_APPLY ===")
        print(
            json.dumps(
                apply,
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print(
            "OK: Growstar hat den Sollwert über den normalen "
            "Geräte-/Produktionspfad an die Spider-Farmer-Bridge übergeben."
        )

        if apply.get("verified") is False:
            print(
                "HINWEIS: verified=false bedeutet nur, dass dieser "
                "Schreibpfad keine separate Rücklesebestätigung liefert. "
                "Die reale Controller-Anzeige bitte zusätzlich prüfen."
            )

        return 0

    except ProductionPathError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
