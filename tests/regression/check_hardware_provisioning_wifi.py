#!/usr/bin/env python3
"""Growstar 3.10.5 / Phase 4W.5 Regression.

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


fake_bleak = types.ModuleType(
    "bleak"
)

fake_bleak.BleakClient = (
    DummyBleakClient
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
        delayed_rx=False,
        mtu_size=23,
    ):
        self.mac = mac
        self.provision = provision
        self.rx_zero_once = delayed_rx
        self.mtu_size = mtu_size

        self.expected_len = None
        self.request_bytes = b""
        self.response_bytes = b""

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
                    "provision": self.provision,
                }

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

    fake_network_module._active_wifi_snapshot = (
        lambda: {
            "ssid": "Growstar-Test"
        }
    )

    fake_network_module.get_current_wifi_password = (
        lambda _ssid: {
            "success": True,
            "ssid": "Growstar-Test",
            "credential_type": "passphrase",
            "revealable": True,
            "password": "test-passphrase",
        }
    )

    fake_network_module.wifi_scan = (
        lambda force=False: {
            "success": True,
            "networks": [
                {
                    "ssid": "Growstar-Test",
                    "security": "WPA2",
                    "hidden": False,
                }
            ],
        }
    )

    sys.modules[
        "services.network"
    ] = fake_network_module

    return load(
        "services/shelly_provisioning.py",
        "growstar_shelly_service_4w5_test",
    )


def test_state_and_credentials():

    service = load_service_with_stubs()

    wifi = (
        service.current_wifi_credentials()
    )

    require(
        wifi.get("ssid")
        == "Growstar-Test"
        and wifi.get("password")
        == "test-passphrase"
        and not wifi.get(
            "password_required"
        ),
        "Aktuelles Growstar-WLAN wird serverseitig inklusive rücklesbarer Passphrase aufgelöst",
    )

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
        "Hardware-UI besitzt den kontrollierten Phase-4W.5-Setupfluss",
    )

    release = load(
        "core/release.py",
        "growstar_release_4w5_test",
    )

    require(
        release.GROWSTAR_VERSION
        == "3.10.5"
        and release.GROWSTAR_INTERNAL_PHASE
        == "4W.5",
        "Growstar meldet Version 3.10.5 / Phase 4W.5",
    )

    require(
        release.RELEASES[
            1
        ]["version"]
        == "3.10.4"
        and release.RELEASES[
            1
        ]["phase"]
        == "4W.4",
        "Phase 4W.4 bleibt direkt in der Patch-Historie erhalten",
    )

    asyncio.run(
        test_ble_helper()
    )

    test_state_and_credentials()

    print(
        "✅ Phase 4W.5 sichere Shelly-WLAN-Erstinbetriebnahme vollständig"
    )


if __name__ == "__main__":
    main()
