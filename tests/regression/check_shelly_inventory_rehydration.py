#!/usr/bin/env python3
"""Regression für den aktiven Refresh persistierter Shelly-Gateways."""

import json
from pathlib import Path
import sys
import tempfile
import types


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Der reine Inventartest benötigt kein Netzwerk. Auf schlanken Entwicklungs-
# systemen darf die optionale requests-Abhängigkeit deshalb fehlen.
try:
    import requests  # noqa: F401
except ImportError:
    sys.modules["requests"] = types.ModuleType("requests")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    from core.hardware.manager import HardwareManager
    from core.hardware.shelly.gateway import ShellyGateway

    with tempfile.TemporaryDirectory(prefix="growstar-shelly-rehydrate-") as temp_dir:
        inventory = Path(temp_dir) / "hardware_inventory.json"
        inventory.write_text(
            json.dumps({
                "version": 1,
                "gateways": {
                    "192.168.178.84": {
                        "id": "192.168.178.84",
                        "ip": "192.168.178.84",
                        "name": "Shelly Power Strip",
                        "manufacturer": "Shelly",
                        "model": "S4PL-00416EU",
                        "type": "gateway",
                        "online": True,
                        "properties": {"last_seen": 1_700_000_000.0},
                        "methods": ["Shelly.GetStatus"],
                        "capabilities": {"switch": True},
                    }
                },
                "devices": {},
            }),
            encoding="utf-8",
        )

        manager = HardwareManager(inventory)
        gateway = manager.gateway("192.168.178.84")
        require(
            isinstance(gateway, ShellyGateway)
            and callable(getattr(gateway, "refresh", None))
            and gateway.api.ip == "192.168.178.84",
            "Persistierter Shelly wird mit aktivem RPC-Refresh rehydriert",
        )
        require(
            gateway.online is False
            and gateway.uptime is None
            and gateway.properties["last_seen"] == 1_700_000_000.0,
            "Gespeicherte Metadaten bleiben erhalten, Online wird erst live bestätigt",
        )

    service_source = (ROOT / "services/hardware.py").read_text(encoding="utf-8")
    require(
        'refresh = getattr(gateway, "refresh", None)' in service_source
        and "live_gateway = ShellyGateway(ip)" in service_source
        and "manager.add_gateway(live_gateway)" in service_source,
        "Hardware-Service repariert auch alte abstrakte Shelly-Laufzeitobjekte",
    )

    print("✅ Shelly-Inventar-Rehydrierung vollständig geprüft")


if __name__ == "__main__":
    main()
