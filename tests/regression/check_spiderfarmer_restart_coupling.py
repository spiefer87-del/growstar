#!/usr/bin/env python3
"""Offline regression for Spider-Farmer bridge restart coupling.

The bridge must restart together with growstar.service so stale controller
writers/subscriptions cannot survive an application restart. The root-owned
Spider-Farmer network boundary must stay independent and is deliberately not
restarted.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def main():
    bridge = read("install/growstar-spiderfarmer.service.in")
    network = read("install/growstar-spiderfarmer-network.service.in")
    installer = read("install/install_spiderfarmer_bridge.sh")

    require(
        "PartOf=growstar.service" in bridge,
        "Spider-Farmer-Bridge folgt Restart/Stop von growstar.service",
    )
    require(
        "Requires=growstar-spiderfarmer-network.service" in bridge,
        "Bridge behaelt die bestehende Network-Service-Abhaengigkeit",
    )
    require(
        "PartOf=growstar.service" not in network,
        "Root-Network-Service wird nicht an Growstar-Restarts gekoppelt",
    )
    require(
        "ExecStart=/usr/bin/python3 -m bridge.spiderfarmer.main" in bridge,
        "Bridge-Startpfad bleibt unveraendert",
    )
    require(
        "Restart=on-failure" in bridge,
        "Bestehende Bridge-Fehler-Recovery bleibt aktiv",
    )
    require(
        'TEMPLATE="${SCRIPT_DIR}/growstar-spiderfarmer.service.in"' in installer,
        "Bestehender Installer installiert weiterhin exakt diese Service-Vorlage",
    )
    require(
        'systemctl daemon-reload' in installer,
        "Installer laedt die geaenderte systemd-Unit neu",
    )

    print("✅ SF.4D.13 Restart-Kopplung vollständig geprüft")


if __name__ == "__main__":
    main()
