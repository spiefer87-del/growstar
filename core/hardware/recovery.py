from __future__ import annotations

import threading
import time


class HardwareRecoveryCoordinator:
    """Koordiniert die automatische Wiederherstellung bekannter Hardware.

    Die Klasse kennt keine Flask-Routen und keine konkrete Shelly-Implementierung.
    Sie arbeitet ausschließlich gegen die bereits vorhandene Hardware-Service-
    Oberfläche. Dadurch bleibt sie testbar und löst keine versteckten Pairings
    unbekannter Geräte aus.
    """

    def __init__(
        self,
        *,
        hardware,
        manager,
        expected_device_ids_provider,
        sleep=time.sleep,
        now=time.time,
        ble_scan_settle_sec=4.0,
    ):
        self.hardware = hardware
        self.manager = manager
        self.expected_device_ids_provider = expected_device_ids_provider
        self.sleep = sleep
        self.now = now
        self.ble_scan_settle_sec = float(ble_scan_settle_sec)

        self._status_lock = threading.RLock()
        self._status = {
            "running": False,
            "phase": "idle",
            "attempts": 0,
            "last_attempt_ts": None,
            "last_success_ts": None,
            "last_error": None,
            "known_gateways": 0,
            "online_gateways": 0,
            "expected_ble_devices": 0,
            "online_ble_devices": 0,
            "missing_ble_devices": [],
            "gateway_scan_used": False,
            "ble_scan_used": False,
            "healthy": False,
        }

    def snapshot(self):
        with self._status_lock:
            return dict(self._status)

    def _set_status(self, **values):
        with self._status_lock:
            self._status.update(values)

    @staticmethod
    def _is_bthome_device(device):
        props = getattr(device, "properties", None) or {}
        return (
            getattr(device, "type", None) == "sensor"
            and props.get("protocol") == "bthome"
        )

    @staticmethod
    def _looks_paired(device):
        props = getattr(device, "properties", None) or {}
        return bool(
            props.get("paired")
            or props.get("bthome_device_id")
            or props.get("bthome_device_key")
            or props.get("paired_gateways")
        )

    def expected_ble_device_ids(self):
        expected = set()

        try:
            provided = self.expected_device_ids_provider() or []
            expected.update(str(item) for item in provided if item)
        except Exception:
            pass

        try:
            for device in self.manager.devices_list():
                if self._is_bthome_device(device) and self._looks_paired(device):
                    if getattr(device, "id", None):
                        expected.add(str(device.id))
        except Exception:
            pass

        return sorted(expected)

    def _gateways(self):
        try:
            return list(self.manager.gateways_list())
        except Exception:
            return []

    def _device(self, device_id):
        try:
            if hasattr(self.manager, "device"):
                return self.manager.device(device_id)
            return self.manager.devices.get(device_id)
        except Exception:
            return None

    @staticmethod
    def _gateway_supports_bluetooth(gateway):
        if bool(getattr(gateway, "bluetooth", False)):
            return True
        if bool(getattr(gateway, "bluetooth_enabled", False)):
            return True

        methods = getattr(gateway, "methods", None) or []
        for method in methods:
            text = str(method).lower()
            if "bluetooth" in text or "ble" in text or "bthome" in text:
                return True

        capabilities = getattr(gateway, "capabilities", None) or {}
        if isinstance(capabilities, dict):
            for key, value in capabilities.items():
                text = f"{key} {value}".lower()
                if "bluetooth" in text or "ble" in text or "bthome" in text:
                    return True

        return False

    def _refresh_known_gateways(self):
        gateways = self._gateways()
        online = 0

        for gateway in gateways:
            try:
                refreshed = self.hardware.refresh_gateway(gateway.id)
                if refreshed is not None and bool(getattr(refreshed, "online", False)):
                    online += 1
            except Exception:
                continue

        return gateways, online

    def _scan_gateways_if_needed(self, gateways, online_count):
        used = False
        if gateways and online_count > 0:
            return gateways, online_count, used

        used = True
        try:
            self.hardware.scan_gateways()
        except Exception:
            return self._gateways(), 0, used

        gateways = self._gateways()
        online_count = sum(1 for gateway in gateways if bool(getattr(gateway, "online", False)))
        return gateways, online_count, used

    def _read_expected_devices(self, expected_ids):
        online = 0
        missing = []

        for device_id in expected_ids:
            device = self._device(device_id)
            if device is None:
                missing.append(device_id)
                continue

            try:
                self.hardware.read_ble_sensor_values(device_id, listen=False)
            except TypeError:
                # Rückwärtskompatibilität mit älteren Service-Signaturen.
                try:
                    self.hardware.read_ble_sensor_values(device_id)
                except Exception:
                    pass
            except Exception:
                pass

            device = self._device(device_id)
            if device is not None and bool(getattr(device, "online", False)):
                online += 1
            else:
                missing.append(device_id)

        return online, missing

    def _ble_recovery_scan(self, gateways, missing_ids):
        if not missing_ids:
            return False

        candidates = [
            gateway
            for gateway in gateways
            if self._gateway_supports_bluetooth(gateway)
        ]

        if not candidates:
            return False

        started = []
        for gateway in candidates:
            try:
                # Aktiviert nur Gateways, die laut Capability/gespeichertem
                # Zustand Bluetooth unterstützen. Unbekannte Shellys werden
                # nicht blind verändert.
                if not bool(getattr(gateway, "bluetooth_enabled", False)):
                    try:
                        self.hardware.enable_bluetooth(gateway.id)
                    except Exception:
                        pass

                result = self.hardware.start_ble_scan(gateway.id)
                if result is not None:
                    started.append(gateway)
            except Exception:
                continue

        if not started:
            return False

        if self.ble_scan_settle_sec > 0:
            self.sleep(self.ble_scan_settle_sec)

        for gateway in started:
            try:
                self.hardware.get_ble_scan_result(gateway.id)
            except Exception:
                pass

            # Bestehende Service-Funktionen dürfen die gefundenen Geräte in den
            # Manager übernehmen. Es wird hier ausdrücklich KEIN pair-Aufruf
            # für unbekannte Geräte ausgeführt.
            try:
                self.hardware.add_discovered_ble_devices(gateway.id)
            except Exception:
                pass

            try:
                self.hardware.register_discovered_ble_devices(gateway.id)
            except Exception:
                pass

        return True

    def recover_once(self):
        attempt_ts = float(self.now())
        self._set_status(
            running=True,
            phase="gateway-refresh",
            attempts=int(self.snapshot().get("attempts") or 0) + 1,
            last_attempt_ts=attempt_ts,
            last_error=None,
            gateway_scan_used=False,
            ble_scan_used=False,
        )

        try:
            gateways, online_gateways = self._refresh_known_gateways()
            gateways, online_gateways, gateway_scan_used = self._scan_gateways_if_needed(
                gateways,
                online_gateways,
            )

            expected_ids = self.expected_ble_device_ids()
            self._set_status(
                phase="ble-direct-read",
                known_gateways=len(gateways),
                online_gateways=online_gateways,
                expected_ble_devices=len(expected_ids),
                gateway_scan_used=gateway_scan_used,
            )

            online_ble, missing = self._read_expected_devices(expected_ids)

            ble_scan_used = False
            if missing:
                self._set_status(phase="ble-scan")
                ble_scan_used = self._ble_recovery_scan(gateways, missing)
                if ble_scan_used:
                    online_ble, missing = self._read_expected_devices(expected_ids)

            try:
                self.manager.save_inventory(merge=True)
            except Exception as exc:
                # Persistenzfehler soll Recovery nicht als Netzwerkfehler
                # maskieren, wird aber sichtbar gemeldet.
                self.manager.last_inventory_error = str(exc)

            gateway_required = bool(gateways or expected_ids)
            gateway_ok = (not gateway_required) or bool(gateways and online_gateways > 0)
            ble_ok = not expected_ids or not missing
            healthy = bool(gateway_ok and ble_ok)
            success_ts = float(self.now()) if healthy else self.snapshot().get("last_success_ts")

            self._set_status(
                running=False,
                phase="ready" if healthy else "degraded",
                known_gateways=len(gateways),
                online_gateways=online_gateways,
                expected_ble_devices=len(expected_ids),
                online_ble_devices=online_ble,
                missing_ble_devices=list(missing),
                gateway_scan_used=gateway_scan_used,
                ble_scan_used=ble_scan_used,
                healthy=healthy,
                last_success_ts=success_ts,
            )

        except Exception as exc:
            self._set_status(
                running=False,
                phase="error",
                healthy=False,
                last_error=str(exc),
            )

        return self.snapshot()
