#!/usr/bin/env python3
"""Growstar 3.11.1 / Phase SF.1N Shelly-WLAN-Kompatibilitätsregression.

Keine echte BLE- oder WLAN-Mutation.
"""

from __future__ import annotations

from pathlib import Path
import ast
import asyncio
import importlib.util
import json
import struct
import sys
import tempfile
import types


ROOT = Path(
    __file__
).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


def ok(message):
    print(
        "✅",
        message,
    )


def require(
    condition,
    message,
):
    if not condition:
        raise AssertionError(
            message
        )

    ok(
        message
    )


def read(rel):
    return (
        ROOT
        / rel
    ).read_text(
        encoding="utf-8"
    )


def load(
    rel,
    name,
):
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / rel,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


class DummyBleakClient:
    pass


class DummyBleakScanner:
    pass


fake_bleak = types.ModuleType(
    "bleak"
)

fake_bleak.BleakClient = (
    DummyBleakClient
)

fake_bleak.BleakScanner = (
    DummyBleakScanner
)

sys.modules[
    "bleak"
] = fake_bleak


class FakeRpcClient:

    def __init__(
        self,
        *,
        mac="A1B2C3D4E5F6",
        provision="pending",
        include_provision=True,
        delayed_rx=False,
        unrelated_frame_once=False,
        mtu_size=23,
    ):
        self.mac = mac
        self.provision = provision
        self.include_provision = include_provision
        self.rx_zero_once = delayed_rx
        self.unrelated_frame_once = unrelated_frame_once
        self.mtu_size = mtu_size

        self.expected_len = None
        self.request_bytes = b""
        self.response_bytes = b""
        self.response_queue = []

        self.requests = []
        self.data_write_chunks = []

    async def write_gatt_char(
        self,
        uuid,
        data,
        response=True,
    ):
        helper = sys.modules[
            "growstar_ble_rpc_4w5_test"
        ]

        if (
            uuid
            == helper.RPC_TX_CTL_UUID
        ):
            self.expected_len = struct.unpack(
                ">I",
                bytes(data),
            )[0]

            self.request_bytes = b""
            self.data_write_chunks = []

            return

        if (
            uuid
            == helper.RPC_DATA_UUID
        ):
            chunk = bytes(
                data
            )

            self.data_write_chunks.append(
                chunk
            )

            self.request_bytes += chunk

            if (
                len(self.request_bytes)
                < self.expected_len
            ):
                return

            request = json.loads(
                self.request_bytes[
                    :self.expected_len
                ]
            )

            self.requests.append(
                request
            )

            if (
                request["method"]
                == "Shelly.GetDeviceInfo"
            ):
                result = {
                    "id": "shelly-test-a1b2c3d4e5f6",
                    "mac": self.mac,
                    "model": "S4PL-00416EU",
                    "ver": "1.6.99-test",
                }

                if self.include_provision:
                    result["provision"] = (
                        self.provision
                    )

            elif (
                request["method"]
                == "Wifi.SetConfig"
            ):
                result = {
                    "restart_required": False
                }

            else:
                raise AssertionError(
                    "Unerwartete RPC-Methode"
                )

            self.response_bytes = json.dumps(
                {
                    "id": request["id"],
                    "src": "shelly-test",
                    "dst": "growstar",
                    "result": result,
                },
                separators=(",", ":"),
            ).encode(
                "utf-8"
            )

            if self.unrelated_frame_once:
                self.unrelated_frame_once = False

                self.response_queue.append(
                    self.response_bytes
                )

                self.response_bytes = json.dumps(
                    {
                        "src": "shelly-test",
                        "dst": "growstar",
                        "method": "NotifyEvent",
                        "params": {
                            "events": []
                        },
                    },
                    separators=(",", ":"),
                ).encode(
                    "utf-8"
                )

            return

        raise AssertionError(
            "Unerwartete Write-Characteristic"
        )

    async def read_gatt_char(
        self,
        uuid,
    ):
        helper = sys.modules[
            "growstar_ble_rpc_4w5_test"
        ]

        if (
            uuid
            == helper.RPC_RX_CTL_UUID
        ):
            if self.rx_zero_once:
                self.rx_zero_once = False

                return struct.pack(
                    ">I",
                    0,
                )

            if (
                not self.response_bytes
                and self.response_queue
            ):
                self.response_bytes = (
                    self.response_queue.pop(0)
                )

            return struct.pack(
                ">I",
                len(
                    self.response_bytes
                ),
            )

        if (
            uuid
            == helper.RPC_DATA_UUID
        ):
            chunk = self.response_bytes[
                :20
            ]

            self.response_bytes = (
                self.response_bytes[
                    20:
                ]
            )

            return chunk

        raise AssertionError(
            "Unerwartete Read-Characteristic"
        )


async def test_ble_helper():

    helper = load(
        "core/hardware/shelly/ble_rpc_helper.py",
        "growstar_ble_rpc_4w5_test",
    )

    # Testzeit verkürzen, Semantik bleibt unverändert.
    helper.TX_CTL_SETTLE_SECONDS = 0

    request = {
        "address": "D8:85:AC:E2:43:A2",
        "expected_mac": "A1:B2:C3:D4:E5:F6",
        "ssid": "Growstar-Test",
        "password": "nur-test-secret",
    }

    client = FakeRpcClient(
        delayed_rx=True,
        unrelated_frame_once=True,
        mtu_size=23,
    )

    result = await helper._provision_with_client(
        client,
        dict(request),
    )

    require(
        result.get(
            "success"
        )
        is True,
        "BLE-RPC-Provisionierungsworkflow simuliert erfolgreich",
    )

    require(
        [
            item["method"]
            for item
            in client.requests
        ]
        == [
            "Shelly.GetDeviceInfo",
            "Wifi.SetConfig",
        ],
        "Shelly.GetDeviceInfo läuft zwingend vor Wifi.SetConfig",
    )

    require(
        all(
            item.get("src")
            == "growstar"
            for item
            in client.requests
        ),
        "BLE-RPC-Requests besitzen die feste Growstar-Source-ID",
    )

    wifi = (
        client.requests[
            1
        ]["params"][
            "config"
        ]["sta"]
    )

    require(
        wifi.get(
            "ssid"
        )
        == "Growstar-Test"
        and wifi.get(
            "pass"
        )
        == "nur-test-secret"
        and wifi.get(
            "enable"
        )
        is True
        and wifi.get(
            "ipv4mode"
        )
        == "dhcp",
        "Wifi.SetConfig erhält SSID, Secret, enable und DHCP korrekt",
    )

    require(
        len(
            client.data_write_chunks
        )
        > 1,
        "RPC-Daten werden bei kleinem ATT-MTU in mehrere Write-Chunks geteilt",
    )

    ok(
        "RX-Control 0 wird abgewartet statt als leere Antwort gewertet"
    )

    ok(
        "Asynchrones NotifyEvent wird ignoriert und die passende RPC-ID weiter abgewartet"
    )

    mismatch = FakeRpcClient(
        mac="FFFFFFFFFFFF"
    )

    try:
        await helper._provision_with_client(
            mismatch,
            dict(request),
        )
    except helper.ProvisioningError:
        pass
    else:
        raise AssertionError(
            "MAC-Mismatch wurde nicht blockiert"
        )

    require(
        [
            item["method"]
            for item
            in mismatch.requests
        ]
        == [
            "Shelly.GetDeviceInfo"
        ],
        "MAC-Mismatch blockiert Wifi.SetConfig vor dem Schreibzugriff",
    )

    locked = FakeRpcClient(
        provision="locked"
    )

    try:
        await helper._provision_with_client(
            locked,
            dict(request),
        )
    except helper.ProvisioningError:
        pass
    else:
        raise AssertionError(
            "Secure-Provisioning locked wurde nicht blockiert"
        )

    require(
        [
            item["method"]
            for item
            in locked.requests
        ]
        == [
            "Shelly.GetDeviceInfo"
        ],
        "Secure-Provisioning locked blockiert Wifi.SetConfig",
    )

    no_provision_field = FakeRpcClient(
        include_provision=False
    )

    no_provision_result = (
        await helper._provision_with_client(
            no_provision_field,
            dict(request),
        )
    )

    require(
        no_provision_result.get("success")
        is True
        and no_provision_result.get(
            "provision_before"
        )
        == helper.PROVISIONING_STATE_NOT_REPORTED,
        "Fehlendes provision-Feld wird als nicht gemeldet behandelt statt fälschlich blockiert",
    )

    require(
        [
            item["method"]
            for item
            in no_provision_field.requests
        ]
        == [
            "Shelly.GetDeviceInfo",
            "Wifi.SetConfig",
        ],
        "Fehlendes provision-Feld lässt den bestehenden Wifi.SetConfig-Pfad zu",
    )


def load_service_with_stubs():

    fake_manager_module = types.ModuleType(
        "core.hardware.manager"
    )

    class FakeManager:
        def add_gateway(
            self,
            gateway,
        ):
            return None

        def save_inventory(
            self,
            merge=True,
        ):
            return {}

    fake_manager_module.manager = (
        FakeManager()
    )

    sys.modules[
        "core.hardware.manager"
    ] = fake_manager_module

    fake_discovery_module = types.ModuleType(
        "core.hardware.shelly.discovery"
    )

    class FakeDiscovery:
        def scan(
            self
        ):
            return []

    fake_discovery_module.ShellyDiscovery = (
        FakeDiscovery
    )

    sys.modules[
        "core.hardware.shelly.discovery"
    ] = fake_discovery_module

    fake_provisioning_module = types.ModuleType(
        "core.hardware.shelly.provisioning"
    )

    fake_provisioning_module.provisioning_discovery = (
        object()
    )

    sys.modules[
        "core.hardware.shelly.provisioning"
    ] = fake_provisioning_module

    fake_hardware_module = types.ModuleType(
        "services.hardware"
    )

    class FakeHardware:
        def gateways(
            self
        ):
            return []

    fake_hardware_module.hardware = (
        FakeHardware()
    )

    sys.modules[
        "services.hardware"
    ] = fake_hardware_module

    fake_network_module = types.ModuleType(
        "services.network"
    )

    class FakeNetworkError(
        RuntimeError
    ):
        pass

    fake_network_module.NetworkChangeError = (
        FakeNetworkError
    )

    fake_network_module.current_wifi_provisioning_credentials = (
        lambda: {
            "success": True,
            "ssid": "Growstar-Test",
            "credential_type": "passphrase",
            "credential_source": "growstar_secret_store",
            "password_required": False,
            "password": "test-passphrase",
        }
    )

    sys.modules[
        "services.network"
    ] = fake_network_module

    return load(
        "services/shelly_provisioning.py",
        "growstar_shelly_service_4w6_test",
    )


def test_state_and_credentials():

    service = load_service_with_stubs()

    with tempfile.TemporaryDirectory() as temp:

        store = (
            service.ProvisioningStateStore(
                Path(temp)
                / "state.json"
            )
        )

        (
            token1,
            _entry1,
            created1,
        ) = store.claim(
            mac="A1:B2:C3:D4:E5:F6",
            address="D8:85:AC:E2:43:A2",
            ssid="Growstar-Test",
        )

        (
            token2,
            _entry2,
            created2,
        ) = store.claim(
            mac="A1:B2:C3:D4:E5:F6",
            address="D8:85:AC:E2:43:A2",
            ssid="Growstar-Test",
        )

        require(
            created1 is True
            and created2 is False
            and token1 == token2,
            "Cross-worker State-Guard verhindert einen zweiten Write-Claim",
        )

        raw = (
            Path(temp)
            / "state.json"
        ).read_text(
            encoding="utf-8"
        )

        require(
            "password"
            not in raw.lower()
            and "passphrase"
            not in raw.lower(),
            "Persistenter Provisionierungsstatus enthält kein WLAN-Secret",
        )

        store.update(
            token1,
            state="verify_pending",
            write_status="unknown",
        )

        require(
            store.get(
                token1
            )["state"]
            == "verify_pending",
            "Unsicherer Write wechselt ausschließlich in den LAN-Verifikationszustand",
        )


def main():

    for rel in (
        "core/hardware/shelly/ble_rpc_helper.py",
        "services/shelly_provisioning.py",
        "routes/hardware.py",
        "core/release.py",
        "tests/regression/check_hardware_provisioning_wifi.py",
    ):
        ast.parse(
            read(rel),
            filename=rel,
        )

        ok(
            "Python-Syntax "
            + rel
        )

    helper_source = read(
        "core/hardware/shelly/ble_rpc_helper.py"
    )

    service_source = read(
        "services/shelly_provisioning.py"
    )

    routes = read(
        "routes/hardware.py"
    )

    template = read(
        "templates/devices.html"
    )

    require(
        "current_wifi_provisioning_credentials"
        in service_source
        and "password_override"
        not in service_source
        and "_active_wifi_snapshot"
        not in service_source,
        "Shelly-Workflow bezieht WLAN-Credentials ausschließlich aus der zentralen Netzwerkquelle",
    )

    require(
        "network_secret_required"
        in service_source
        and 'data.get("password")'
        not in routes,
        "Hardware-API akzeptiert kein separates Shelly-WLAN-Passwort mehr",
    )

    require(
        "provisioning-wifi-password"
        not in template
        and "System → Netzwerk öffnen"
        in template
        and "zentrale"
        in template.lower(),
        "Hardware-UI verweist bei fehlendem Secret auf die zentrale Netzwerkverwaltung",
    )

    require(
        "find_device_by_address"
        in helper_source
        and "elif result is None:\n                    raise"
        not in helper_source,
        "BLE-Helper löst das Gerät frisch auf und lässt Disconnect-EOFError den RPC-Fehler nicht maskieren",
    )

    require(
        "Switch.Set"
        not in helper_source
        and "Shelly.FactoryReset"
        not in helper_source
        and "BLE.StartPairing"
        not in helper_source,
        "BLE-Helper besitzt keinen Relais-, Factory-Reset- oder Pairing-Pfad",
    )

    require(
        "shell=True"
        not in helper_source
        and "shell=True"
        not in service_source,
        "Provisionierung verwendet keine Shell-Ausführung",
    )

    require(
        'BLE_HELPER_PYTHON = "/usr/bin/python3"'
        in service_source
        and "input=json.dumps("
        in service_source,
        "WLAN-Secret wird über stdin statt argv an /usr/bin/python3 übergeben",
    )

    require(
        "active_for_mac"
        in service_source
        and "verification_token"
        in service_source
        and "write_repeated"
        in service_source,
        "Idempotenz-Guard und tokengebundene LAN-Verifikation sind vorhanden",
    )

    require(
        "manager.save_inventory("
        in service_source
        and "_normalize_mac("
        in service_source,
        "Hardware-Inventar wird erst im MAC-verifizierten LAN-Adoptionspfad gespeichert",
    )

    require(
        '@app.post("/api/hardware/provisioning/wifi")'
        in routes
        and '@app.post("/api/hardware/provisioning/verify")'
        in routes,
        "WLAN-Provisionierungs- und reine Verifikations-API sind registriert",
    )

    require(
        "WLAN-Erstinbetriebnahme"
        in template
        and "LAN-Verifikation erneut versuchen"
        in template
        and "/api/hardware/provisioning/wifi"
        in template
        and "/api/hardware/provisioning/verify"
        in template,
        "Hardware-UI besitzt den kontrollierten Phase-4W.6-Setupfluss",
    )

    release = load(
        "core/release.py",
        "growstar_release_4w6_test",
    )

    require(
        release.GROWSTAR_VERSION
        == "3.11.1"
        and release.GROWSTAR_INTERNAL_PHASE
        == "SF.1N",
        "Growstar meldet Version 3.11.1 / Phase SF.1N",
    )

    require(
        release.RELEASES[
            1
        ]["version"]
        == "3.11.0"
        and release.RELEASES[
            1
        ]["phase"]
        == "SF.1",
        "Phase SF.1 bleibt direkt in der Patch-Historie erhalten",
    )

    asyncio.run(
        test_ble_helper()
    )

    test_state_and_credentials()

    print(
        "✅ Growstar 3.11.1 / SF.1N Shelly-Provisionierungs-Kompatibilität vollständig"
    )


if __name__ == "__main__":
    main()
