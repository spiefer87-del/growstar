#!/usr/bin/env python3
"""Growstar Phase 4W.8 – Shelly-Provisionierungsstate kompatibel behandeln.

Dieser Prozess kann ausschließlich:
1. Shelly.GetDeviceInfo lesen,
2. Geräte-MAC und Secure-Provisioning-State prüfen,
3. Wifi.SetConfig für das serverseitig gewählte WLAN senden.

Es gibt bewusst keinen generischen RPC-Endpunkt.
Das WLAN-Secret kommt nur über stdin und erscheint nicht in argv/ps.
"""

from __future__ import annotations

import asyncio
import json
import re
import struct
import sys
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    BleakClient = None
    BleakScanner = None


RPC_DATA_UUID = "5f6d4f53-5f52-5043-5f64-6174615f5f5f"
RPC_TX_CTL_UUID = "5f6d4f53-5f52-5043-5f74-785f63746c5f"
RPC_RX_CTL_UUID = "5f6d4f53-5f52-5043-5f72-785f63746c5f"

RPC_SOURCE = "growstar"
MAX_INPUT_BYTES = 16 * 1024
MAX_RPC_FRAME_BYTES = 64 * 1024
RPC_TIMEOUT_SECONDS = 12.0
CONNECT_TIMEOUT_SECONDS = 15.0
DEVICE_SCAN_TIMEOUT_SECONDS = 5.0
TX_CTL_SETTLE_SECONDS = 0.25
PROVISIONING_STATES_ALLOWED = {"pending", "confirmed"}
PROVISIONING_STATE_NOT_REPORTED = "not-reported"


class ProvisioningError(RuntimeError):
    pass


def _normalize_mac(value):
    compact = re.sub(
        r"[^0-9A-Fa-f]",
        "",
        str(value or ""),
    )

    if (
        len(compact) != 12
        or not re.fullmatch(
            r"[0-9A-Fa-f]{12}",
            compact,
        )
    ):
        raise ProvisioningError(
            "Ungültige Shelly-Geräte-MAC"
        )

    compact = compact.upper()

    return ":".join(
        compact[index:index + 2]
        for index in range(0, 12, 2)
    )


def _validate_request(payload):
    if not isinstance(payload, dict):
        raise ProvisioningError(
            "Ungültige Provisionierungsanfrage"
        )

    address = str(
        payload.get("address")
        or ""
    ).strip().upper()

    if not re.fullmatch(
        r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}",
        address,
    ):
        raise ProvisioningError(
            "Ungültige Bluetooth-Adresse"
        )

    expected_mac = _normalize_mac(
        payload.get("expected_mac")
    )

    ssid = str(
        payload.get("ssid")
        or ""
    ).strip()

    if not ssid:
        raise ProvisioningError(
            "WLAN-Name fehlt"
        )

    if any(
        char in ssid
        for char in ("\x00", "\n", "\r")
    ):
        raise ProvisioningError(
            "Ungültiger WLAN-Name"
        )

    if len(ssid.encode("utf-8")) > 32:
        raise ProvisioningError(
            "WLAN-Name ist länger als 32 Byte"
        )

    password = payload.get("password")

    if password is None:
        password = ""

    password = str(password)

    if any(
        char in password
        for char in ("\x00", "\n", "\r")
    ):
        raise ProvisioningError(
            "WLAN-Passwort enthält ungültige Steuerzeichen"
        )

    if len(password) > 128:
        raise ProvisioningError(
            "WLAN-Passwort ist zu lang"
        )

    return {
        "address": address,
        "expected_mac": expected_mac,
        "ssid": ssid,
        "password": password,
    }


def _data_chunk_size(client):
    """Konservativer Write-Chunk <= ATT-MTU minus Header."""

    try:
        mtu = int(
            getattr(client, "mtu_size", 23)
            or 23
        )
    except (TypeError, ValueError):
        mtu = 23

    return max(
        20,
        min(244, mtu - 3),
    )


async def _rpc_call(
    client,
    rpc_id,
    method,
    params=None,
):
    request = {
        "id": int(rpc_id),
        "src": RPC_SOURCE,
        "method": str(method),
        "params": params or {},
    }

    request_bytes = json.dumps(
        request,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    if len(request_bytes) > MAX_RPC_FRAME_BYTES:
        raise ProvisioningError(
            "RPC-Anfrage ist zu groß"
        )

    await client.write_gatt_char(
        RPC_TX_CTL_UUID,
        struct.pack(
            ">I",
            len(request_bytes),
        ),
        response=True,
    )

    # Shelly empfiehlt eine kurze Synchronisationspause nach TX-Control.
    await asyncio.sleep(
        TX_CTL_SETTLE_SECONDS
    )

    chunk_size = _data_chunk_size(
        client
    )

    for offset in range(
        0,
        len(request_bytes),
        chunk_size,
    ):
        await client.write_gatt_char(
            RPC_DATA_UUID,
            request_bytes[
                offset:offset + chunk_size
            ],
            response=True,
        )

    deadline = (
        time.monotonic()
        + RPC_TIMEOUT_SECONDS
    )

    # Auf demselben RPC-Kanal dürfen asynchrone NotifyStatus-/NotifyEvent-
    # Frames auftauchen. Sie besitzen nicht unsere Request-ID und müssen
    # verworfen werden, statt den eigentlichen RPC-Aufruf abzubrechen.
    while time.monotonic() < deadline:

        frame_len = 0

        while time.monotonic() < deadline:

            raw = bytes(
                await client.read_gatt_char(
                    RPC_RX_CTL_UUID
                )
            )

            if len(raw) >= 4:
                frame_len = struct.unpack(
                    ">I",
                    raw[:4],
                )[0]

            # 0 bedeutet: aktuell noch kein Frame abholbereit.
            if frame_len:
                break

            await asyncio.sleep(
                0.1
            )

        if not frame_len:
            break

        if frame_len > MAX_RPC_FRAME_BYTES:
            raise ProvisioningError(
                "BLE-RPC-Antwort ist unerwartet groß"
            )

        frame = bytearray()

        while (
            len(frame) < frame_len
            and time.monotonic() < deadline
        ):

            chunk = bytes(
                await client.read_gatt_char(
                    RPC_DATA_UUID
                )
            )

            if chunk:
                frame.extend(
                    chunk
                )
            else:
                await asyncio.sleep(
                    0.05
                )

        if len(frame) < frame_len:
            raise ProvisioningError(
                f"Unvollständige BLE-RPC-Antwort auf {method}"
            )

        try:
            response = json.loads(
                bytes(
                    frame[:frame_len]
                ).decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ProvisioningError(
                "Ungültige BLE-RPC-JSON-Antwort"
            ) from exc

        # Notifications und verspätete Antworten anderer Requests sind auf
        # dem symmetrischen Shelly-RPC-Kanal zulässig. Nur die eigene ID ist
        # die Antwort auf diesen Aufruf.
        if response.get("id") != request["id"]:
            continue

        if "error" in response:

            error = response.get(
                "error"
            ) or {}

            code = (
                error.get("code")
                if isinstance(error, dict)
                else None
            )

            message = str(
                error.get("message")
                if isinstance(error, dict)
                else error
            ).strip()

            suffix = (
                f" (RPC {code})"
                if code is not None
                else ""
            )

            raise ProvisioningError(
                (
                    message
                    or f"{method} fehlgeschlagen"
                )
                + suffix
            )

        if "result" not in response:
            raise ProvisioningError(
                "BLE-RPC-Antwort enthält kein result-Feld"
            )

        return response["result"]

    raise ProvisioningError(
        f"Keine passende BLE-RPC-Antwort auf {method} innerhalb des Zeitlimits"
    )

async def _provision_with_client(
    client,
    request,
):
    """Fester Workflow: GetDeviceInfo -> Wifi.SetConfig."""

    info = await _rpc_call(
        client,
        1,
        "Shelly.GetDeviceInfo",
        {},
    )

    actual_mac = _normalize_mac(
        info.get("mac")
    )

    if (
        actual_mac
        != request["expected_mac"]
    ):
        raise ProvisioningError(
            "Shelly-Geräte-MAC stimmt nicht mit dem Bluetooth-Kandidaten überein"
        )

    # Das `provision`-Feld gehört zur Shelly-Secure-Provisioning-
    # Zustandsmaschine und existiert erst ab Firmware 1.7.5. Ältere bzw.
    # noch nicht aktualisierte Gen3/Gen4-Firmwares können über den offiziellen
    # BLE-RPC-Service erreichbar sein, ohne dieses Feld zu liefern.
    #
    # Explizite Sperrzustände (z. B. locked/complete) bleiben weiterhin
    # fail-closed. Nur ein tatsächlich NICHT gemeldeter Zustand wird als
    # kompatibler Legacy-/Firmware-Fall behandelt. Der nachfolgende
    # Wifi.SetConfig-Aufruf bleibt die einzige Schreiboperation und sein
    # RPC-Ergebnis wird weiterhin ausgewertet.
    provision_raw = info.get("provision")

    provision_state = str(
        provision_raw
        or ""
    ).strip().lower()

    if provision_state:
        if (
            provision_state
            not in PROVISIONING_STATES_ALLOWED
        ):
            raise ProvisioningError(
                "Shelly Secure-Provisioning erlaubt keinen WLAN-Schreibzugriff "
                f"(Status: {provision_state})"
            )
    else:
        provision_state = (
            PROVISIONING_STATE_NOT_REPORTED
        )

    # pass muss beim Setzen einer SSID mitgeführt werden.
    # Für ein offenes WLAN ist null zulässig.
    wifi_config = {
        "sta": {
            "ssid": request["ssid"],
            "pass": (
                request["password"]
                or None
            ),
            "enable": True,
            "ipv4mode": "dhcp",
        }
    }

    # Ab dem ersten TX-Control für Wifi.SetConfig behandeln wir den Zustand
    # konservativ als "Write begonnen". Ein Fehler wird NICHT automatisch
    # durch einen zweiten Schreibversuch kompensiert.
    try:
        wifi_result = await _rpc_call(
            client,
            2,
            "Wifi.SetConfig",
            {
                "config": wifi_config
            },
        )

        return {
            "success": True,
            "write_started": True,
            "write_status": "accepted",
            "device_mac": actual_mac,
            "model": info.get("model"),
            "device_id": info.get("id"),
            "provision_before": provision_state,
            "restart_required": bool(
                (
                    wifi_result
                    or {}
                ).get(
                    "restart_required"
                )
            ),
        }

    except Exception as exc:

        return {
            "success": False,
            "write_started": True,
            "write_status": "unknown",
            "device_mac": actual_mac,
            "model": info.get("model"),
            "device_id": info.get("id"),
            "provision_before": provision_state,
            "error": (
                "Wifi.SetConfig wurde begonnen, der Abschluss konnte über BLE "
                f"nicht sicher bestätigt werden: {exc}"
            ),
        }


async def _run(payload):
    if (
        BleakClient is None
        or BleakScanner is None
    ):
        raise ProvisioningError(
            "python3-bleak ist nicht installiert"
        )

    request = _validate_request(
        payload
    )

    # Bleak empfiehlt unter BlueZ ein bereits aufgelöstes BLEDevice an den
    # Client zu übergeben. Das vermeidet einen zweiten impliziten Lookup beim
    # Connect und entspricht dem auf dem echten Growstar-Pi verifizierten Pfad.
    device = await BleakScanner.find_device_by_address(
        request["address"],
        timeout=DEVICE_SCAN_TIMEOUT_SECONDS,
    )

    if device is None:
        raise ProvisioningError(
            "Shelly ist beim unmittelbaren BLE-Verbindungsaufbau nicht mehr sichtbar"
        )

    client = BleakClient(
        device,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )

    result = None
    connected = False

    try:
        await client.connect()
        connected = True

        result = await _provision_with_client(
            client,
            request,
        )

    finally:
        request["password"] = ""

        if connected:
            try:
                await client.disconnect()
            except Exception as exc:
                # BlueZ/dbus-fast kann nach einem ansonsten erfolgreichen
                # GATT-Lauf beim Disconnect einen EOFError liefern. Ein
                # Cleanup-Fehler darf weder einen erfolgreichen Write noch
                # den davor entstandenen eigentlichen RPC-Fehler maskieren.
                if (
                    isinstance(result, dict)
                ):
                    detail = str(exc).strip()
                    result[
                        "disconnect_error"
                    ] = (
                        f"{type(exc).__name__}: {detail}"
                        if detail
                        else type(exc).__name__
                    )

    return result


def _emit(
    payload,
    code=0,
):
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
        )
        + "\n"
    )

    sys.stdout.flush()

    raise SystemExit(
        code
    )


def main():

    raw = sys.stdin.buffer.read(
        MAX_INPUT_BYTES + 1
    )

    if len(raw) > MAX_INPUT_BYTES:
        _emit(
            {
                "success": False,
                "write_started": False,
                "write_status": "not-started",
                "error": "Anfrage zu groß",
            },
            2,
        )

    try:
        payload = json.loads(
            raw.decode("utf-8")
            or "{}"
        )

        result = asyncio.run(
            _run(payload)
        )

    except ProvisioningError as exc:
        _emit(
            {
                "success": False,
                "write_started": False,
                "write_status": "not-started",
                "error": str(exc),
            },
            2,
        )

    except Exception as exc:
        _emit(
            {
                "success": False,
                "write_started": False,
                "write_status": "not-started",
                "error": (
                    "BLE-Provisionierung fehlgeschlagen: "
                    + str(exc)
                ),
            },
            2,
        )

    _emit(
        result,
        0
        if result.get("success")
        else 3,
    )


if __name__ == "__main__":
    main()
