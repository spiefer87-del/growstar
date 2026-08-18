#!/usr/bin/env python3
"""Bereitet den einmaligen Wechsel von der alten Shutdown-Logik auf Phase 4T vor."""

from core.runtime import init_runtimes, list_runtimes
from core.tents import init_tents
from services.restart_policy import apply_shutdown_restart_policy


def main():
    init_tents()
    init_runtimes()

    failures = []

    for runtime in list_runtimes():
        # Default-Station ist LIVE. Zusätzliche persisted-LIVE-Stationen
        # beginnen in einem separaten Prozess zwar als ARMING, besitzen aber
        # weiterhin eine gültige stationsbezogene Konfiguration.
        if not runtime.control_enabled and not getattr(runtime, "live_requested", False):
            continue

        result = apply_shutdown_restart_policy(runtime, verify=True)

        print(f"🔁 [{runtime.tent_id}] Neustart-Policy:")
        for item in result["devices"].values():
            if not item["configured"]:
                continue

            if item["action"] == "KEEP":
                print(f"  ↔ {item['label']}: Zustand beibehalten")
            elif item["error"]:
                print(f"  ❌ {item['label']}: {item['error']}")
            else:
                print(f"  🛑 {item['label']}: sicher AUS")

        failures.extend(
            f"[{runtime.tent_id}] {entry}"
            for entry in result.get("failures") or []
        )

    if failures:
        print()
        print("❌ Neustart wird nicht automatisch fortgesetzt:")
        for entry in failures:
            print(" -", entry)
        raise SystemExit(2)

    print("✅ Physische Restart-Policy erfolgreich vorbereitet")


if __name__ == "__main__":
    main()
