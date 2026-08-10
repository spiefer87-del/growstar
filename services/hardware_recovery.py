from __future__ import annotations

import threading
import time

from core.hardware.manager import manager
from core.hardware.recovery import HardwareRecoveryCoordinator
from core.runtime import list_runtimes
from services.hardware import hardware


_thread_lock = threading.Lock()
_thread_started = False
_thread = None


def _expected_ble_device_ids():
    """Leitet erwartete BLE-Geräte aus allen lokalen Stationszuweisungen ab."""
    result = set()

    try:
        runtimes = list_runtimes()
    except Exception:
        runtimes = []

    for runtime in runtimes:
        assignments = runtime.config.get("SENSOR_ASSIGNMENTS") or {}
        if not isinstance(assignments, dict):
            continue

        for assignment in assignments.values():
            if not isinstance(assignment, dict):
                continue
            source_id = str(assignment.get("source_id") or "").strip()
            if not source_id.startswith("hardware:blu_"):
                continue
            result.add(source_id.split("hardware:", 1)[1])

    return sorted(result)


coordinator = HardwareRecoveryCoordinator(
    hardware=hardware,
    manager=manager,
    expected_device_ids_provider=_expected_ble_device_ids,
)


def get_hardware_recovery_status():
    status = coordinator.snapshot()
    status["inventory"] = manager.inventory_status()
    return status


def recover_hardware_once():
    return coordinator.recover_once()


def hardware_recovery_loop():
    print("♻️ Hardware Auto-Recovery gestartet")

    # Schnelle Wiederholungen direkt nach Boot/Netzwerkstart, danach ruhiger.
    retry_delays = (2, 5, 10, 30, 60)
    retry_index = 0

    while True:
        status = recover_hardware_once()

        if status.get("healthy"):
            retry_index = 0
            print(
                "✅ Hardware Recovery bereit: "
                f"{status.get('online_gateways', 0)}/{status.get('known_gateways', 0)} Gateways, "
                f"{status.get('online_ble_devices', 0)}/{status.get('expected_ble_devices', 0)} BLE"
            )
            # Im gesunden Zustand reichen gelegentliche Selbstheilungschecks.
            time.sleep(120)
            continue

        missing = status.get("missing_ble_devices") or []
        if status.get("last_error"):
            print("⚠️ Hardware Recovery Fehler:", status["last_error"])
        else:
            print(
                "⚠️ Hardware Recovery noch unvollständig: "
                f"Gateways {status.get('online_gateways', 0)}/{status.get('known_gateways', 0)}, "
                f"BLE fehlt: {', '.join(missing) if missing else 'keins'}"
            )

        delay = retry_delays[min(retry_index, len(retry_delays) - 1)]
        retry_index = min(retry_index + 1, len(retry_delays) - 1)
        time.sleep(delay)


def start_hardware_recovery_thread():
    global _thread_started, _thread

    with _thread_lock:
        if _thread_started and _thread is not None and _thread.is_alive():
            return _thread

        _thread_started = True
        _thread = threading.Thread(
            name="growstar-hw-recovery",
            target=hardware_recovery_loop,
            daemon=True,
        )
        _thread.start()
        return _thread
