import os

import requests

import core.context as ctx


RPC_DEBUG_ENV = "GROWSTAR_SHELLY_RPC_DEBUG"

_TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
}


def _env_flag(name, default=False):

    raw = os.getenv(
        name
    )

    if raw is None:
        return bool(
            default
        )

    return (
        str(
            raw
        )
        .strip()
        .lower()
        in _TRUE_VALUES
    )


class ShellyAPI:

    def __init__(
        self,
        ip,
        debug=None
    ):

        self.ip = str(
            ip
        )

        self.base = (
            f"http://{self.ip}/rpc"
        )

        self.debug = (
            _env_flag(
                RPC_DEBUG_ENV
            )
            if debug is None
            else bool(
                debug
            )
        )


    def _debug_response(
        self,
        method,
        response
    ):

        if not self.debug:
            return

        print(
            "🔎 Shelly RPC:",
            self.ip,
            method,
            "HTTP",
            response.status_code
        )

        print(
            "Antwort:",
            response.text
        )


    def _log_http_error(
        self,
        method,
        response,
        exc
    ):

        print(
            "❌ Shelly RPC Fehler:",
            self.ip,
            method,
            "HTTP",
            response.status_code,
            "-",
            exc
        )

        # Fehlerantworten bleiben absichtlich vollständig sichtbar.
        # Nur erfolgreiche Antworten werden standardmäßig unterdrückt.
        if not self.debug:
            print(
                "Antwort:",
                response.text
            )


    def _log_transport_error(
        self,
        method,
        exc
    ):

        print(
            "❌ Shelly RPC Netzwerkfehler:",
            self.ip,
            method,
            "-",
            exc
        )


    def _log_json_error(
        self,
        method,
        response,
        exc
    ):

        print(
            "❌ Shelly RPC JSON-Fehler:",
            self.ip,
            method,
            "HTTP",
            response.status_code,
            "-",
            exc
        )

        # Bei ungültigem JSON ist der Body für die Diagnose relevant.
        if not self.debug:
            print(
                "Antwort:",
                response.text
            )


    def call(
        self,
        method,
        params=None
    ):

        response = None

        try:

            # Phase 4V.4:
            # Inventar-, BLE- und sonstige Shelly-RPCs dürfen nicht mehr
            # gleichzeitig mit Aktor-Health, Relay-Schaltungen oder dem
            # bestehenden Energy/Failsafe-Zyklus auf die Shellys feuern.
            with ctx.shelly_lock:
                response = requests.post(
                    f"{self.base}/{method}",
                    json=params or {},
                    timeout=5
                )

            # Phase 4J.2:
            # Erfolgreiche RPC-Antworten bleiben im Normalbetrieb ruhig.
            # Vollständige Request-Ergebnisse können bei Bedarf über
            # GROWSTAR_SHELLY_RPC_DEBUG=1 wieder sichtbar gemacht werden.
            self._debug_response(
                method,
                response
            )

            try:

                response.raise_for_status()

            except requests.HTTPError as exc:

                self._log_http_error(
                    method,
                    response,
                    exc
                )

                return None

            try:

                return response.json()

            except ValueError as exc:

                self._log_json_error(
                    method,
                    response,
                    exc
                )

                return None

        except requests.RequestException as exc:

            self._log_transport_error(
                method,
                exc
            )

            return None

        except Exception as exc:

            # Rückwärtskompatibel fail-soft bleiben: Die alte Implementierung
            # gab bei jedem unerwarteten RPC-Fehler ebenfalls None zurück.
            print(
                "❌ Shelly RPC unerwarteter Fehler:",
                self.ip,
                method,
                "-",
                exc
            )

            if (
                response is not None
                and not self.debug
            ):
                print(
                    "Antwort:",
                    getattr(
                        response,
                        "text",
                        ""
                    )
                )

            return None


    def list_methods(
        self
    ):

        return self.call(
            "Shelly.ListMethods"
        )
