"""Growstar Phase 4W.5 – sichere Shelly-WLAN-Erstinbetriebnahme.

Der bestehende Hardware-/Netzwerk-Unterbau bleibt unverändert:
- aktuelles WLAN aus services.network,
- LAN-Erkennung aus ShellyDiscovery,
- Persistenz aus dem vorhandenen HardwareManager.

Das WLAN-Secret wird nie persistiert.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

from core.hardware.manager import manager
from core.hardware.shelly.discovery import ShellyDiscovery
from core.hardware.shelly.provisioning import provisioning_discovery
from services.hardware import hardware
from services.network import (
    NetworkChangeError,
    _active_wifi_snapshot,
    get_current_wifi_password,
    wifi_scan,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

DEFAULT_STATE_PATH = (
    PROJECT_ROOT
    / "instance"
    / "shelly_provisioning_state.json"
)

BLE_HELPER_PATH = (
    PROJECT_ROOT
    / "core"
    / "hardware"
    / "shelly"
    / "ble_rpc_helper.py"
)

BLE_HELPER_PYTHON = "/usr/bin/python3"

STATE_MAX_AGE_SECONDS = 15 * 60
LAN_VERIFY_ATTEMPTS = 6
LAN_VERIFY_PAUSE_SECONDS = 2.0
BLE_HELPER_TIMEOUT_SECONDS = 40


class ShellyProvisioningError(
    RuntimeError
):
    pass


def _normalize_mac(value):

    compact = "".join(
        char
        for char in str(
            value
            or ""
        ).upper()
        if char
        in "0123456789ABCDEF"
    )

    if len(compact) != 12:
        raise ShellyProvisioningError(
            "Ungültige Shelly-Geräte-MAC"
        )

    return ":".join(
        compact[index:index + 2]
        for index in range(
            0,
            12,
            2,
        )
    )


def _validate_password(value):

    secret = (
        ""
        if value is None
        else str(value)
    )

    if any(
        char in secret
        for char in (
            "\x00",
            "\n",
            "\r",
        )
    ):
        raise ValueError(
            "Das WLAN-Passwort enthält ungültige Steuerzeichen"
        )

    if len(secret) > 128:
        raise ValueError(
            "Das WLAN-Passwort ist zu lang"
        )

    return secret


def _current_wifi_security(
    ssid,
):
    """Best-effort Security-Info aus dem vorhandenen NM-Scan."""

    scan = wifi_scan(
        force=False
    )

    if not scan.get(
        "success"
    ):
        return None

    for item in (
        scan.get("networks")
        or []
    ):
        if (
            item.get("ssid")
            == ssid
            and not item.get(
                "hidden"
            )
        ):
            return str(
                item.get("security")
                or "--"
            ).strip().upper()

    return None


def _security_is_open(
    security,
):
    return str(
        security
        or ""
    ).strip().upper() in {
        "",
        "--",
        "NONE",
        "OPEN",
    }


def current_wifi_credentials(
    password_override=None,
):
    """Ermittelt Ziel-SSID und Secret ausschließlich serverseitig."""

    snapshot = _active_wifi_snapshot()

    if (
        not snapshot
        or not snapshot.get(
            "ssid"
        )
    ):
        raise NetworkChangeError(
            "Growstar ist aktuell mit keinem verwalteten WLAN verbunden"
        )

    ssid = str(
        snapshot.get("ssid")
        or ""
    ).strip()

    if not ssid:
        raise NetworkChangeError(
            "Aktuelle WLAN-SSID konnte nicht ermittelt werden"
        )

    security = _current_wifi_security(
        ssid
    )

    if _security_is_open(
        security
    ):
        return {
            "success": True,
            "ssid": ssid,
            "password": "",
            "password_required": False,
            "credential_type": "open",
        }

    stored = get_current_wifi_password(
        ssid
    )

    if stored.get(
        "revealable"
    ):

        secret = stored.get(
            "password"
        )

        if (
            not isinstance(
                secret,
                str,
            )
            or not secret
        ):
            raise NetworkChangeError(
                "NetworkManager meldet eine Passphrase, liefert sie aber nicht"
            )

        return {
            "success": True,
            "ssid": ssid,
            "password": secret,
            "password_required": False,
            "credential_type": "passphrase",
        }

    override = _validate_password(
        password_override
    )

    if override:
        return {
            "success": True,
            "ssid": ssid,
            "password": override,
            "password_required": False,
            "credential_type": "user_passphrase",
        }

    return {
        "success": True,
        "ssid": ssid,
        "password": None,
        "password_required": True,
        "credential_type": (
            stored.get(
                "credential_type"
            )
            or "unknown"
        ),
    }


class ProvisioningStateStore:
    """Cross-worker Idempotenzstatus ohne WLAN-Secret."""

    def __init__(
        self,
        path=DEFAULT_STATE_PATH,
    ):
        self.path = Path(
            path
        )

        self.lock_path = (
            self.path.with_suffix(
                self.path.suffix
                + ".lock"
            )
        )

    def _read_unlocked(
        self
    ):
        if not self.path.exists():
            return {
                "version": 1,
                "entries": {},
            }

        try:
            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return {
                "version": 1,
                "entries": {},
            }

        if not isinstance(
            data,
            dict,
        ):
            return {
                "version": 1,
                "entries": {},
            }

        entries = data.get(
            "entries"
        )

        if not isinstance(
            entries,
            dict,
        ):
            entries = {}

        return {
            "version": 1,
            "entries": entries,
        }

    def _write_unlocked(
        self,
        data,
    ):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temp_path = tempfile.mkstemp(
            prefix=".shelly-provisioning-",
            suffix=".tmp",
            dir=str(
                self.path.parent
            ),
            text=True,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:

                json.dump(
                    data,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

                handle.flush()

                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temp_path,
                self.path,
            )

            try:
                os.chmod(
                    self.path,
                    0o600,
                )
            except OSError:
                pass

        except Exception:
            try:
                os.unlink(
                    temp_path
                )
            except OSError:
                pass
            raise

    def _locked(
        self
    ):
        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        handle = open(
            self.lock_path,
            "a+",
            encoding="utf-8",
        )

        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX,
        )

        return handle

    @staticmethod
    def _prune(
        data
    ):
        now = time.time()

        entries = (
            data.get(
                "entries"
            )
            or {}
        )

        keep = {}

        for token, entry in entries.items():

            try:
                stamp = float(
                    entry.get(
                        "updated_at"
                    )
                    or entry.get(
                        "created_at"
                    )
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                now - stamp
                <= STATE_MAX_AGE_SECONDS
            ):
                keep[token] = entry

        data[
            "entries"
        ] = keep

        return data

    def active_for_mac(
        self,
        mac,
    ):
        wanted = _normalize_mac(
            mac
        )

        lock = self._locked()

        try:
            data = self._prune(
                self._read_unlocked()
            )

            self._write_unlocked(
                data
            )

            for token, entry in (
                data["entries"].items()
            ):
                if (
                    entry.get("mac")
                    == wanted
                ):
                    return (
                        token,
                        dict(entry),
                    )

            return (
                None,
                None,
            )

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )

            lock.close()

    def claim(
        self,
        *,
        mac,
        address,
        ssid,
    ):
        wanted = _normalize_mac(
            mac
        )

        lock = self._locked()

        try:
            data = self._prune(
                self._read_unlocked()
            )

            for token, entry in (
                data["entries"].items()
            ):
                if (
                    entry.get("mac")
                    == wanted
                ):
                    return (
                        token,
                        dict(entry),
                        False,
                    )

            token = secrets.token_urlsafe(
                24
            )

            now = time.time()

            entry = {
                "mac": wanted,
                "address": str(
                    address
                    or ""
                ).upper(),
                "ssid": str(
                    ssid
                    or ""
                ),
                "state": "writing",
                "created_at": now,
                "updated_at": now,
            }

            data["entries"][
                token
            ] = entry

            self._write_unlocked(
                data
            )

            return (
                token,
                dict(entry),
                True,
            )

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )

            lock.close()

    def update(
        self,
        token,
        **changes,
    ):
        lock = self._locked()

        try:
            data = self._prune(
                self._read_unlocked()
            )

            entry = data[
                "entries"
            ].get(
                str(token)
            )

            if not entry:
                return None

            entry.update(
                changes
            )

            entry[
                "updated_at"
            ] = time.time()

            data["entries"][
                str(token)
            ] = entry

            self._write_unlocked(
                data
            )

            return dict(
                entry
            )

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )

            lock.close()

    def get(
        self,
        token,
    ):
        lock = self._locked()

        try:
            data = self._prune(
                self._read_unlocked()
            )

            self._write_unlocked(
                data
            )

            entry = data[
                "entries"
            ].get(
                str(token)
            )

            return (
                dict(entry)
                if entry
                else None
            )

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )

            lock.close()

    def remove(
        self,
        token,
    ):
        lock = self._locked()

        try:
            data = self._prune(
                self._read_unlocked()
            )

            existed = (
                data["entries"].pop(
                    str(token),
                    None,
                )
                is not None
            )

            self._write_unlocked(
                data
            )

            return existed

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )

            lock.close()


def _run_ble_helper(
    payload
):
    if not BLE_HELPER_PATH.is_file():
        raise ShellyProvisioningError(
            "Shelly-BLE-RPC-Helper fehlt"
        )

    if not os.path.isfile(
        BLE_HELPER_PYTHON
    ):
        raise ShellyProvisioningError(
            "/usr/bin/python3 ist für den BLE-Helper nicht verfügbar"
        )

    try:
        completed = subprocess.run(
            [
                BLE_HELPER_PYTHON,
                str(
                    BLE_HELPER_PATH
                ),
            ],
            input=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            timeout=BLE_HELPER_TIMEOUT_SECONDS,
            check=False,
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
            },
        )

    except subprocess.TimeoutExpired:
        # Konservativ: der Helper könnte bereits bei Wifi.SetConfig gewesen sein.
        return {
            "success": False,
            "write_started": True,
            "write_status": "unknown",
            "error": (
                "BLE-Helper hat das Zeitlimit überschritten; "
                "nur LAN-Verifikation erlaubt."
            ),
        }

    finally:
        payload[
            "password"
        ] = ""

    lines = (
        completed.stdout
        or ""
    ).strip().splitlines()

    if not lines:
        return {
            "success": False,
            "write_started": (
                completed.returncode
                not in {
                    1,
                    2,
                }
            ),
            "write_status": "unknown",
            "error": (
                completed.stderr
                or "BLE-Helper lieferte keine Antwort"
            ).strip(),
        }

    try:
        result = json.loads(
            lines[-1]
        )
    except json.JSONDecodeError:
        return {
            "success": False,
            "write_started": (
                completed.returncode
                not in {
                    1,
                    2,
                }
            ),
            "write_status": "unknown",
            "error": (
                "BLE-Helper lieferte keine gültige JSON-Antwort"
            ),
        }

    return result


class ShellyWifiProvisioningService:

    def __init__(
        self,
        *,
        state_store=None,
        hardware_service=hardware,
        discovery_factory=ShellyDiscovery,
        ble_runner=_run_ble_helper,
        credential_resolver=current_wifi_credentials,
        sleeper=time.sleep,
    ):
        self.state = (
            state_store
            or ProvisioningStateStore()
        )

        self.hardware = hardware_service
        self.discovery_factory = (
            discovery_factory
        )
        self.ble_runner = ble_runner
        self.credential_resolver = (
            credential_resolver
        )
        self.sleeper = sleeper

    def _fresh_candidate(
        self,
        address,
    ):
        address = str(
            address
            or ""
        ).strip().upper()

        result = (
            provisioning_discovery.scan(
                seconds=3
            )
        )

        if not result.get(
            "success"
        ):
            raise ShellyProvisioningError(
                result.get(
                    "error"
                )
                or (
                    "Bluetooth-Scan vor der "
                    "WLAN-Erstinbetriebnahme fehlgeschlagen"
                )
            )

        gateways = [
            gateway.to_dict()
            for gateway
            in self.hardware.gateways()
        ]

        classification = (
            provisioning_discovery.classify_candidates(
                result.get(
                    "candidates"
                )
                or [],
                gateways,
            )
        )

        candidate = next(
            (
                item
                for item
                in classification[
                    "candidates"
                ]
                if str(
                    item.get(
                        "address"
                    )
                    or ""
                ).upper()
                == address
            ),
            None,
        )

        if candidate is None:
            raise ShellyProvisioningError(
                "Das gewählte Shelly ist im frischen Bluetooth-Scan nicht sichtbar"
            )

        if (
            candidate.get(
                "inventory_state"
            )
            == "known"
        ):
            raise ShellyProvisioningError(
                "Dieses Shelly ist bereits im Growstar-Hardwarebestand"
            )

        if (
            candidate.get(
                "inventory_state"
            )
            != "new"
        ):
            raise ShellyProvisioningError(
                "Die Shelly-Geräteidentität ist nicht eindeutig; Schreiben blockiert"
            )

        candidate[
            "identity_mac"
        ] = _normalize_mac(
            candidate.get(
                "identity_mac"
            )
        )

        return candidate

    def _existing_gateway_by_mac(
        self,
        expected_mac,
    ):
        wanted = _normalize_mac(
            expected_mac
        )

        for gateway in (
            self.hardware.gateways()
        ):

            try:
                current = _normalize_mac(
                    getattr(
                        gateway,
                        "mac",
                        None,
                    )
                )
            except ShellyProvisioningError:
                continue

            if current == wanted:
                return gateway

        return None

    def _adopt_gateway(
        self,
        gateway,
    ):
        """Persistiert erst das bereits per LAN-RPC/MAC verifizierte Gateway."""

        if gateway is None:
            raise ShellyProvisioningError(
                "Verifiziertes Gateway fehlt"
            )

        wanted = _normalize_mac(
            getattr(
                gateway,
                "mac",
                None,
            )
        )

        existing = (
            self._existing_gateway_by_mac(
                wanted
            )
        )

        if existing is not None:
            return existing

        gateway_id = str(
            getattr(
                gateway,
                "id",
                "",
            )
            or ""
        ).strip()

        if not gateway_id:
            raise ShellyProvisioningError(
                "Verifiziertes Gateway besitzt keine ID/IP"
            )

        manager.add_gateway(
            gateway
        )

        manager.save_inventory(
            merge=True
        )

        return gateway

    def _verify_lan_once(
        self,
        expected_mac,
    ):
        existing = (
            self._existing_gateway_by_mac(
                expected_mac
            )
        )

        if existing is not None:
            return existing

        wanted = _normalize_mac(
            expected_mac
        )

        discovered = (
            self.discovery_factory().scan()
        )

        for gateway in discovered:

            try:
                current = _normalize_mac(
                    getattr(
                        gateway,
                        "mac",
                        None,
                    )
                )
            except ShellyProvisioningError:
                continue

            if current != wanted:
                continue

            return self._adopt_gateway(
                gateway
            )

        return None

    def _wait_for_lan(
        self,
        expected_mac,
    ):
        for attempt in range(
            LAN_VERIFY_ATTEMPTS
        ):

            gateway = (
                self._verify_lan_once(
                    expected_mac
                )
            )

            if gateway is not None:
                return gateway

            if (
                attempt + 1
                < LAN_VERIFY_ATTEMPTS
            ):
                self.sleeper(
                    LAN_VERIFY_PAUSE_SECONDS
                )

        return None

    @staticmethod
    def _gateway_result(
        gateway
    ):
        return (
            gateway.to_dict()
            if gateway is not None
            else None
        )

    def start(
        self,
        address,
        password_override=None,
    ):
        candidate = self._fresh_candidate(
            address
        )

        expected_mac = candidate[
            "identity_mac"
        ]

        (
            existing_token,
            _existing_state,
        ) = self.state.active_for_mac(
            expected_mac
        )

        if existing_token:

            gateway = self._wait_for_lan(
                expected_mac
            )

            if gateway is not None:

                self.state.remove(
                    existing_token
                )

                return {
                    "success": True,
                    "adopted": True,
                    "write_repeated": False,
                    "verification_pending": False,
                    "gateway": self._gateway_result(
                        gateway
                    ),
                }

            return {
                "success": False,
                "adopted": False,
                "write_repeated": False,
                "verification_pending": True,
                "verification_token": existing_token,
                "message": (
                    "Für dieses Shelly existiert bereits ein begonnener "
                    "WLAN-Schreibvorgang. Growstar wiederholt Wifi.SetConfig "
                    "nicht und erlaubt nur die LAN-Verifikation."
                ),
            }

        wifi = self.credential_resolver(
            password_override=password_override
        )

        if wifi.get(
            "password_required"
        ):
            return {
                "success": False,
                "password_required": True,
                "ssid": wifi.get(
                    "ssid"
                ),
                "credential_type": wifi.get(
                    "credential_type"
                ),
                "error": (
                    "NetworkManager besitzt nur einen nicht rückrechenbaren "
                    "Schlüssel. Bitte die echte WLAN-Passphrase einmalig eingeben."
                ),
            }

        ssid = str(
            wifi.get(
                "ssid"
            )
            or ""
        )

        secret = str(
            wifi.get(
                "password"
            )
            or ""
        )

        (
            token,
            _state_entry,
            created,
        ) = self.state.claim(
            mac=expected_mac,
            address=candidate[
                "address"
            ],
            ssid=ssid,
        )

        if not created:
            return {
                "success": False,
                "verification_pending": True,
                "verification_token": token,
                "write_repeated": False,
                "message": (
                    "Provisionierung wurde bereits von einem anderen "
                    "Growstar-Worker begonnen."
                ),
            }

        helper_payload = {
            "address": candidate[
                "address"
            ],
            "expected_mac": expected_mac,
            "ssid": ssid,
            "password": secret,
        }

        try:
            helper_result = (
                self.ble_runner(
                    helper_payload
                )
            )
        finally:
            secret = ""
            helper_payload[
                "password"
            ] = ""

        if not helper_result.get(
            "write_started"
        ):
            self.state.remove(
                token
            )

            return {
                "success": False,
                "verification_pending": False,
                "write_repeated": False,
                "error": (
                    helper_result.get(
                        "error"
                    )
                    or "WLAN-Schreibzugriff wurde nicht begonnen"
                ),
            }

        self.state.update(
            token,
            state="verify_pending",
            write_status=(
                helper_result.get(
                    "write_status"
                )
                or "unknown"
            ),
        )

        gateway = self._wait_for_lan(
            expected_mac
        )

        if gateway is not None:

            self.state.remove(
                token
            )

            return {
                "success": True,
                "adopted": True,
                "verification_pending": False,
                "write_repeated": False,
                "ssid": ssid,
                "gateway": self._gateway_result(
                    gateway
                ),
                "ble": {
                    "write_status": helper_result.get(
                        "write_status"
                    ),
                    "provision_before": helper_result.get(
                        "provision_before"
                    ),
                },
            }

        return {
            "success": False,
            "adopted": False,
            "verification_pending": True,
            "verification_token": token,
            "write_repeated": False,
            "ssid": ssid,
            "message": (
                "WLAN-Konfiguration wurde begonnen, das Shelly ist im LAN "
                "noch nicht über seine Geräte-MAC bestätigt. Bitte nur die "
                "LAN-Verifikation wiederholen."
            ),
            "ble": {
                "write_status": helper_result.get(
                    "write_status"
                ),
                "error": helper_result.get(
                    "error"
                ),
            },
        }

    def verify(
        self,
        token,
    ):
        entry = self.state.get(
            token
        )

        if not entry:
            raise ShellyProvisioningError(
                "LAN-Verifikation ist abgelaufen oder unbekannt"
            )

        expected_mac = _normalize_mac(
            entry.get(
                "mac"
            )
        )

        gateway = self._wait_for_lan(
            expected_mac
        )

        if gateway is None:
            return {
                "success": False,
                "adopted": False,
                "verification_pending": True,
                "verification_token": token,
                "write_repeated": False,
                "message": (
                    "Shelly wurde im LAN noch nicht mit der erwarteten "
                    "Geräte-MAC gefunden. Es wurde kein weiterer "
                    "WLAN-Schreibversuch ausgeführt."
                ),
            }

        self.state.remove(
            token
        )

        return {
            "success": True,
            "adopted": True,
            "verification_pending": False,
            "write_repeated": False,
            "gateway": self._gateway_result(
                gateway
            ),
        }


shelly_wifi_provisioning = (
    ShellyWifiProvisioningService()
)
