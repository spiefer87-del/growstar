#!/usr/bin/env python3

"""
Growstar Phase 4J.2 – Shelly RPC Log-Hygiene Regression

WICHTIG:
- keine echten Netzwerkrequests
- keine Shelly-Hardware
- keine Aktorik
- keine Runtime-Imports

Geprüft wird ausschließlich core/hardware/shelly/api.py.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
API_FILE = ROOT / "core" / "hardware" / "shelly" / "api.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "phase4j2_shelly_api",
        API_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        payload=None,
        text=None,
        json_error=None,
    ):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        self.text = (
            text
            if text is not None
            else repr(payload)
        )

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise requests.HTTPError(
                f"{self.status_code} Server Error"
            )

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def capture_call(api, method):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = api.call(method)
    return result, output.getvalue()


def main():
    module = load_module()

    require(
        module.RPC_DEBUG_ENV == "GROWSTAR_SHELLY_RPC_DEBUG",
        "Expliziter RPC-Debug-Schalter vorhanden",
    )

    # ---------------------------------------------------------
    # 1. Erfolg: Normalbetrieb muss ruhig sein
    # ---------------------------------------------------------
    methods_payload = {
        "methods": [
            "Shelly.GetStatus",
            "BLE.GetConfig",
            "BTHome.StartDeviceDiscovery",
        ]
    }

    module.requests.post = lambda *args, **kwargs: FakeResponse(
        status_code=200,
        payload=methods_payload,
        text='{"methods":["Shelly.GetStatus","BLE.GetConfig","BTHome.StartDeviceDiscovery"]}',
    )

    api = module.ShellyAPI(
        "192.0.2.10",
        debug=False,
    )

    result, output = capture_call(
        api,
        "Shelly.ListMethods",
    )

    require(
        result == methods_payload,
        "Erfolgreiche RPC-Antwort bleibt funktional unverändert",
    )
    require(
        output == "",
        "Erfolgreicher RPC ist standardmäßig vollständig ruhig",
    )

    # ---------------------------------------------------------
    # 2. Debug: Erfolg darf vollständig sichtbar werden
    # ---------------------------------------------------------
    debug_api = module.ShellyAPI(
        "192.0.2.10",
        debug=True,
    )

    result, output = capture_call(
        debug_api,
        "BLE.GetConfig",
    )

    require(
        result == methods_payload,
        "Debug-Modus verändert den RPC-Rückgabewert nicht",
    )
    require(
        "BLE.GetConfig" in output
        and "HTTP 200" in output
        and "Antwort:" in output,
        "Debug-Modus zeigt Methode, Status und vollständige Antwort",
    )

    # ---------------------------------------------------------
    # 3. HTTP-Fehler: trotz ruhigem Normalbetrieb vollständig loggen
    # ---------------------------------------------------------
    error_body = '{"code":-103,"message":"unsupported method"}'

    module.requests.post = lambda *args, **kwargs: FakeResponse(
        status_code=500,
        payload=None,
        text=error_body,
    )

    error_api = module.ShellyAPI(
        "192.0.2.11",
        debug=False,
    )

    result, output = capture_call(
        error_api,
        "BTHome.StartDeviceDiscovery",
    )

    require(
        result is None,
        "HTTP-Fehler bleibt fail-soft und liefert None",
    )
    require(
        "BTHome.StartDeviceDiscovery" in output
        and "HTTP 500" in output
        and error_body in output,
        "HTTP-Fehler behält Methode, Status und vollständigen Response-Body",
    )

    # ---------------------------------------------------------
    # 4. Transportfehler: weiterhin sichtbar
    # ---------------------------------------------------------
    def fail_post(*args, **kwargs):
        raise requests.ConnectionError(
            "synthetischer Verbindungstest"
        )

    module.requests.post = fail_post

    transport_api = module.ShellyAPI(
        "192.0.2.12",
        debug=False,
    )

    result, output = capture_call(
        transport_api,
        "Shelly.GetStatus",
    )

    require(
        result is None,
        "Transportfehler bleibt fail-soft",
    )
    require(
        "Netzwerkfehler" in output
        and "Shelly.GetStatus" in output
        and "synthetischer Verbindungstest" in output,
        "Transportfehler bleibt im Journal eindeutig diagnostizierbar",
    )

    # ---------------------------------------------------------
    # 5. Ungültiges Erfolgs-JSON: Body sichtbar, None zurück
    # ---------------------------------------------------------
    module.requests.post = lambda *args, **kwargs: FakeResponse(
        status_code=200,
        payload=None,
        text="<html>kein json</html>",
        json_error=ValueError(
            "synthetischer JSON-Test"
        ),
    )

    json_api = module.ShellyAPI(
        "192.0.2.13",
        debug=False,
    )

    result, output = capture_call(
        json_api,
        "Shelly.GetStatus",
    )

    require(
        result is None,
        "Ungültiges JSON bleibt fail-soft",
    )
    require(
        "JSON-Fehler" in output
        and "<html>kein json</html>" in output,
        "Ungültiges JSON protokolliert den diagnostischen Response-Body",
    )

    # ---------------------------------------------------------
    # 6. Environment-Debug ohne Caller-Änderung
    # ---------------------------------------------------------
    old = os.environ.get(
        module.RPC_DEBUG_ENV
    )

    try:
        os.environ[
            module.RPC_DEBUG_ENV
        ] = "1"

        env_api = module.ShellyAPI(
            "192.0.2.14"
        )

        require(
            env_api.debug is True,
            "Debug kann ohne Codeänderung per Environment aktiviert werden",
        )

    finally:
        if old is None:
            os.environ.pop(
                module.RPC_DEBUG_ENV,
                None,
            )
        else:
            os.environ[
                module.RPC_DEBUG_ENV
            ] = old

    print("✅ Phase 4J.2 Shelly RPC Log-Hygiene vollständig")


if __name__ == "__main__":
    main()
