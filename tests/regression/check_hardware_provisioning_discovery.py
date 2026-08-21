#!/usr/bin/env python3
"""Growstar Phase 4W – herstellerfreie Shelly-Discovery Regression.

Read-only:
- kein echter Bluetooth-Scan
- kein Pairing
- keine WLAN-Mutation
- keine Shelly-Schaltung
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message):
    print("✅", message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    ok(message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def syntax(rel):
    ast.parse(read(rel), filename=rel)
    ok(f"Python-Syntax {rel}")


class Completed:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeBluetoothctl:
    def __init__(self, *, manufacturer_only=False):
        self.commands = []
        self.manufacturer_only = manufacturer_only

    def which(self, name):
        if name == "bluetoothctl":
            return "/usr/bin/bluetoothctl"
        return None

    def run(
        self,
        args,
        *,
        capture_output,
        text,
        timeout,
        check,
        env,
    ):
        command = list(args)
        self.commands.append(command)

        tail = command[1:]

        if tail == ["show"]:
            return Completed(
                stdout=(
                    "Controller AA:BB:CC:DD:EE:FF raspberrypi [default]\n"
                    "\tPowered: yes\n"
                    "\tDiscovering: no\n"
                )
            )

        if "scan" in tail and "on" in tail:
            shelly_name = (
                "Generic Device"
                if self.manufacturer_only
                else "ShellyPStripG4-A1B2C3D4E5F6"
            )
            return Completed(
                stdout=(
                    f"[NEW] Device 11:22:33:44:55:66 {shelly_name}\n"
                    "[CHG] Device 11:22:33:44:55:66 RSSI: -48\n"
                    "[NEW] Device 22:33:44:55:66:77 Pixel Phone\n"
                )
            )

        if tail == ["scan", "off"]:
            return Completed(
                stdout="Discovery stopped\n"
            )

        if tail == ["info", "11:22:33:44:55:66"]:
            name = (
                "Generic Device"
                if self.manufacturer_only
                else "ShellyPStripG4-A1B2C3D4E5F6"
            )
            return Completed(
                stdout=(
                    "Device 11:22:33:44:55:66\n"
                    f"\tName: {name}\n"
                    f"\tAlias: {name}\n"
                    "\tPaired: no\n"
                    "\tTrusted: no\n"
                    "\tConnected: no\n"
                    "\tRSSI: -48\n"
                    "\tManufacturerData Key: 0x0ba9 (2985)\n"
                )
            )

        if tail == ["info", "22:33:44:55:66:77"]:
            return Completed(
                stdout=(
                    "Device 22:33:44:55:66:77\n"
                    "\tName: Pixel Phone\n"
                    "\tAlias: Pixel Phone\n"
                    "\tPaired: no\n"
                    "\tTrusted: no\n"
                    "\tConnected: no\n"
                    "\tRSSI: -60\n"
                )
            )

        raise AssertionError(
            "Unerwarteter bluetoothctl-Aufruf: "
            + repr(command)
        )


def load_provisioning():
    spec = importlib.util.spec_from_file_location(
        "growstar_phase4w_provisioning_test",
        ROOT / "core/hardware/shelly/provisioning.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_fake_discovery(module, *, manufacturer_only=False):
    fake = FakeBluetoothctl(
        manufacturer_only=manufacturer_only
    )

    discovery = module.ShellyProvisioningDiscovery(
        runner=fake.run,
        which=fake.which,
        scan_seconds=8,
    )

    status = discovery.status()

    require(
        status["success"]
        and status["available"]
        and status["powered"],
        "Simulierter Raspberry-Bluetooth-Adapter wird als bereit erkannt",
    )

    result = discovery.scan()

    require(
        result["success"]
        and result["count"] == 1,
        "Discovery filtert genau einen Shelly-Kandidaten",
    )

    candidate = result["candidates"][0]

    require(
        candidate["address"] == "11:22:33:44:55:66"
        and candidate["manufacturer"] == "Shelly"
        and candidate["read_only"] is True,
        "Shelly-Kandidat wird read-only mit stabiler Bluetooth-Adresse dargestellt",
    )

    all_tokens = [
        str(token).lower()
        for command in fake.commands
        for token in command[1:]
    ]

    for forbidden in (
        "pair",
        "trust",
        "connect",
        "remove",
        "power",
    ):
        require(
            forbidden not in all_tokens,
            f"Discovery führt keinen bluetoothctl-{forbidden}-Befehl aus",
        )

    return candidate


def main():
    for rel in (
        "core/hardware/shelly/provisioning.py",
        "routes/hardware.py",
        "core/release.py",
        "tests/regression/check_hardware_provisioning_discovery.py",
    ):
        syntax(rel)

    provisioning = load_provisioning()

    candidate = run_fake_discovery(
        provisioning,
        manufacturer_only=False,
    )

    require(
        candidate.get("model_hint") == "S4PL-00416EU"
        and candidate.get("model_name_hint") == "Shelly Power Strip 4 Gen4",
        "Power-Strip-Gen4-Name erzeugt den passenden unverbindlichen Modell-Hinweis",
    )

    manufacturer_candidate = run_fake_discovery(
        provisioning,
        manufacturer_only=True,
    )

    require(
        manufacturer_candidate.get("manufacturer_keys") == ["0x0ba9"],
        "Shelly wird auch ohne eindeutigen Namen über ManufacturerData 0x0BA9 erkannt",
    )

    provisioning_source = read(
        "core/hardware/shelly/provisioning.py"
    )
    provisioning_source_lower = provisioning_source.lower()
    provisioning_tree = ast.parse(
        provisioning_source,
        filename="core/hardware/shelly/provisioning.py",
    )

    # Phase 4W.1:
    # Kommentare und Docstrings dürfen Begriffe wie "HardwareManager" erklären,
    # ohne dass daraus ein produktiver Codepfad entsteht. Deshalb prüfen wir
    # echte Python-Struktur statt eines pauschalen Texttreffers.
    imported_modules = set()
    referenced_names = set()

    for node in ast.walk(provisioning_tree):

        if isinstance(node, ast.Import):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(
                    node.module
                )

        elif isinstance(node, ast.Name):
            referenced_names.add(
                node.id
            )

    require(
        "core.hardware.manager" not in imported_modules
        and "HardwareManager" not in referenced_names,
        "Discovery importiert oder referenziert keinen HardwareManager",
    )

    for forbidden in (
        "wifi.setconfig",
        "nmcli",
        "manager.add",
        "manager.save",
        "shell=true",
    ):
        require(
            forbidden not in provisioning_source_lower,
            f"Discovery enthält keinen produktiven Mutationspfad '{forbidden}'",
        )

    routes = read("routes/hardware.py")

    require(
        '@app.post("/api/hardware/scan")' in routes
        and 'data.get("mode") == "provisioning"' in routes,
        "Bestehender Hardware-Scan bleibt erhalten und trägt den expliziten Provisioning-Modus",
    )

    require(
        '@app.get("/api/hardware/provisioning/status")' in routes,
        "Read-only Provisioning-Status-API ist registriert",
    )

    service = read("services/hardware.py")

    require(
        "scanner.register(" in service
        and "ShellyDiscovery()" in service,
        "Bestehender Shelly-LAN-Gateway-Scanner bleibt registriert",
    )

    require(
        "provisioning_discovery" not in service,
        "Factory-Discovery wird nicht als GatewayScanner oder HardwareManager-Quelle registriert",
    )

    gateway = read(
        "core/hardware/shelly/gateway.py"
    )

    require(
        "BTHome.StartDeviceDiscovery" in gateway,
        "Bestehender Gateway-BTHome-Scan bleibt als eigener Discovery-Pfad erhalten",
    )

    models = read(
        "core/hardware/shelly/models.py"
    )

    require(
        '"S4PL-00416EU"' in models,
        "Bestehender Modellkatalog kennt die Shelly Power Strip 4 Gen4 weiterhin",
    )

    template = read("templates/devices.html")

    require(
        "LAN-Gateway suchen" in template
        and "Neue Shelly ohne Hersteller-App" in template,
        "Hardware-UI trennt LAN-Gateway-Scan und fabrikneue Geräte sichtbar",
    )

    require(
        "noch keine WLAN-Daten" in template
        or "keine WLAN-Daten" in template,
        "Hardware-UI kennzeichnet Phase 4W ausdrücklich als noch nicht provisionierend",
    )

    release_spec = importlib.util.spec_from_file_location(
        "growstar_phase4w_release_test",
        ROOT / "core/release.py",
    )
    release = importlib.util.module_from_spec(release_spec)
    sys.modules[release_spec.name] = release
    release_spec.loader.exec_module(release)

    feature_release = next(
        (
            item
            for item in release.RELEASES
            if item.get("version") == "3.10.0"
            and item.get("phase") == "4W"
        ),
        None,
    )

    require(
        feature_release is not None,
        "Feature-Release 3.10.0 / Phase 4W bleibt in den Patch Notes dokumentiert",
    )

    print("✅ Phase 4W Hardware-Erstinbetriebnahme-Discovery vollständig")


if __name__ == "__main__":
    main()
