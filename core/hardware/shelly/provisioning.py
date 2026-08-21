"""Read-only Discovery für fabrikneue Shelly-Geräte.

Phase 4W ergänzt bewusst KEIN zweites Gateway- oder BTHome-System:

- Bereits eingerichtete Shellys im LAN bleiben Aufgabe von ShellyDiscovery.
- BLU/BTHome-Sensoren bleiben Aufgabe eines bereits erreichbaren ShellyGateway.
- Dieses Modul erkennt ausschließlich Shelly-Kandidaten über den lokalen
  Bluetooth-Adapter des Raspberry Pi.

Der Discovery-Lauf:
- verändert keine WLAN-Konfiguration,
- führt kein Bluetooth-Pairing/Trust/Connect aus,
- schaltet keine Shelly-Ausgänge,
- schreibt nichts in den HardwareManager,
- überträgt keinerlei WLAN-Passwort.

Die gefundenen Kandidaten sind daher absichtlich nur flüchtige UI-Daten.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading


BLUEZ_BACKEND = "bluez-bluetoothctl"
DEFAULT_SCAN_SECONDS = 8
MIN_SCAN_SECONDS = 3
MAX_SCAN_SECONDS = 20

SHELLY_MANUFACTURER_KEY = "0x0ba9"

_MAC_RE = re.compile(
    r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b"
)
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROLLER_RE = re.compile(
    r"^\s*Controller\s+([0-9A-Fa-f:]{17})(?:\s+(.+?))?(?:\s+\[default\])?\s*$",
    re.MULTILINE,
)
_MFDATA_KEY_RE = re.compile(
    r"ManufacturerData\s+Key:\s*(0x[0-9A-Fa-f]+)",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(
    r"^\s*(Name|Alias|RSSI|Paired|Connected|Trusted):\s*(.*?)\s*$",
    re.MULTILINE,
)
_RSSI_RE = re.compile(
    r"\bRSSI:\s*(-?\d+)\b",
    re.IGNORECASE,
)
_SHELLY_ADVERTISED_ID_RE = re.compile(
    r"^Shelly[A-Za-z0-9_-]*[-_]([0-9A-Fa-f]{12})$",
    re.IGNORECASE,
)


class BluetoothDiscoveryError(RuntimeError):
    """Kontrollierter Fehler des lokalen Bluetooth-Discovery-Pfads."""


class ShellyProvisioningDiscovery:
    """Erkennt flüchtige Shelly-Provisioning-Kandidaten über BlueZ."""

    def __init__(
        self,
        *,
        runner=subprocess.run,
        which=shutil.which,
        scan_seconds=DEFAULT_SCAN_SECONDS,
    ):
        self._runner = runner
        self._which = which
        self.scan_seconds = self._normalize_scan_seconds(scan_seconds)
        self._scan_lock = threading.Lock()

    @staticmethod
    def _normalize_scan_seconds(value):
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            seconds = DEFAULT_SCAN_SECONDS

        return max(
            MIN_SCAN_SECONDS,
            min(MAX_SCAN_SECONDS, seconds),
        )

    @staticmethod
    def _clean_output(value):
        return _ANSI_RE.sub(
            "",
            str(value or ""),
        ).replace("\r", "")

    def _executable(self):
        path = self._which("bluetoothctl")
        return str(path) if path else None

    def _run(self, *args, timeout=6):
        executable = self._executable()
        if not executable:
            raise BluetoothDiscoveryError(
                "BlueZ/bluetoothctl ist auf diesem Raspberry nicht verfügbar."
            )

        env = os.environ.copy()
        env["LC_ALL"] = "C"

        try:
            completed = self._runner(
                [executable, *[str(arg) for arg in args]],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise BluetoothDiscoveryError(
                "Bluetooth-Abfrage hat das Zeitlimit überschritten."
            ) from exc
        except OSError as exc:
            raise BluetoothDiscoveryError(
                f"Bluetooth-Abfrage konnte nicht gestartet werden: {exc}"
            ) from exc

        stdout = self._clean_output(
            getattr(completed, "stdout", "")
        )
        stderr = self._clean_output(
            getattr(completed, "stderr", "")
        )

        if int(getattr(completed, "returncode", 1) or 0) != 0:
            message = (
                stderr.strip()
                or stdout.strip()
                or "bluetoothctl wurde mit einem Fehler beendet."
            )
            raise BluetoothDiscoveryError(message)

        return stdout

    @staticmethod
    def _yes(value):
        return str(value or "").strip().lower() in {
            "yes",
            "true",
            "1",
            "on",
        }

    @staticmethod
    def _normalize_mac(value):
        """Normalisiert eine echte Geräte-MAC ohne BLE-Adressen umzudeuten."""

        raw = str(value or "").strip()

        if re.fullmatch(
            r"[0-9A-Fa-f]{12}",
            raw,
        ):
            compact = raw.upper()

        elif re.fullmatch(
            r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}",
            raw,
        ):
            compact = re.sub(
                r"[:-]",
                "",
                raw,
            ).upper()

        else:
            return None

        return ":".join(
            compact[index:index + 2]
            for index in range(0, 12, 2)
        )

    @classmethod
    def _advertised_device_mac(cls, candidate):
        """Liest die Shelly-Gerätekennung nur aus einem Shelly Advertised Name.

        Wichtig: Die Bluetooth-Adresse ``candidate["address"]`` wird bewusst
        NICHT als Geräte-/WLAN-MAC verwendet. Reale Shellys können für BLE und
        WLAN unterschiedliche Adressen besitzen.
        """

        for key in ("name", "alias"):
            value = str(
                (candidate or {}).get(key)
                or ""
            ).strip()

            match = _SHELLY_ADVERTISED_ID_RE.fullmatch(
                value
            )

            if not match:
                continue

            normalized = cls._normalize_mac(
                match.group(1)
            )

            if normalized:
                return normalized

        return None

    @staticmethod
    def _rssi_from_observed_lines(observed_lines):
        """Nimmt den letzten plausiblen RSSI-Wert aus dem aktiven Scan."""

        result = None

        for line in observed_lines or []:
            for match in _RSSI_RE.finditer(
                str(line or "")
            ):
                try:
                    value = int(
                        match.group(1)
                    )
                except (TypeError, ValueError):
                    continue

                if -127 <= value <= 20:
                    result = value

        return result

    @classmethod
    def classify_candidates(
        cls,
        candidates,
        known_gateways,
    ):
        """Ordnet BLE-Kandidaten read-only dem bekannten Growstar-Bestand zu.

        Die einzige stabile Identität für den Bestandsabgleich ist die aus dem
        Shelly Advertised Name abgeleitete Geräte-MAC. Die BLE-Adresse wird
        ausschließlich als Bluetooth-Adresse angezeigt und niemals als
        Ersatz-MAC verwendet.

        ``known_gateways`` ist absichtlich nur ein bereits erzeugter Snapshot.
        Dieses Modul importiert weiterhin keinen HardwareManager und schreibt
        keinerlei Inventardaten.
        """

        gateways_by_mac = {}

        for gateway in known_gateways or []:
            if not isinstance(gateway, dict):
                continue

            mac = cls._normalize_mac(
                gateway.get("mac")
            )

            if not mac:
                continue

            gateways_by_mac.setdefault(
                mac,
                [],
            ).append(gateway)

        classified = []
        known_count = 0
        new_count = 0
        unknown_count = 0

        for raw_candidate in candidates or []:
            if not isinstance(raw_candidate, dict):
                continue

            candidate = dict(
                raw_candidate
            )

            identity_mac = cls._advertised_device_mac(
                candidate
            )

            candidate["identity_mac"] = identity_mac
            candidate["identity_source"] = (
                "shelly-advertised-name"
                if identity_mac
                else None
            )
            candidate["known_gateway"] = None
            candidate["known_gateway_count"] = 0

            matches = list(
                gateways_by_mac.get(
                    identity_mac,
                    [],
                )
            ) if identity_mac else []

            if matches:
                # Bei historischen doppelten IP-Einträgen bleibt die Identität
                # trotzdem "bekannt". Für die Anzeige bevorzugen wir einen
                # aktuell online gemeldeten Datensatz.
                matches.sort(
                    key=lambda gateway: (
                        not bool(gateway.get("online")),
                        not bool(str(gateway.get("ip") or "").strip()),
                        str(gateway.get("ip") or ""),
                    )
                )

                gateway = matches[0]

                candidate["inventory_state"] = "known"
                candidate["provisioned"] = True
                candidate["known_gateway_count"] = len(matches)
                candidate["known_gateway"] = {
                    "id": gateway.get("id"),
                    "name": gateway.get("name"),
                    "model": gateway.get("model"),
                    "manufacturer": gateway.get("manufacturer"),
                    "ip": gateway.get("ip"),
                    "mac": cls._normalize_mac(
                        gateway.get("mac")
                    ),
                    "online": bool(
                        gateway.get("online")
                    ),
                }
                known_count += 1

            elif identity_mac:
                candidate["inventory_state"] = "new"
                candidate["provisioned"] = False
                new_count += 1

            else:
                candidate["inventory_state"] = "unknown"
                candidate["provisioned"] = None
                unknown_count += 1

            classified.append(
                candidate
            )

        return {
            "candidates": classified,
            "known_count": known_count,
            "new_count": new_count,
            "unknown_count": unknown_count,
        }

    def status(self):
        """Liefert ausschließlich den lokalen Adapterstatus."""

        result = {
            "success": True,
            "backend": BLUEZ_BACKEND,
            "available": False,
            "adapter": None,
            "adapter_name": None,
            "powered": False,
            "scan_seconds": self.scan_seconds,
            "error": None,
        }

        if not self._executable():
            result["success"] = False
            result["error"] = (
                "BlueZ/bluetoothctl ist nicht installiert. "
                "Der bestehende LAN-Gateway-Scan bleibt davon unberührt."
            )
            return result

        result["available"] = True

        try:
            output = self._run("show", timeout=6)
        except BluetoothDiscoveryError as exc:
            result["success"] = False
            result["error"] = str(exc)
            return result

        controller = _CONTROLLER_RE.search(output)
        if controller:
            result["adapter"] = controller.group(1).upper()
            name = (controller.group(2) or "").strip()
            if name.endswith("[default]"):
                name = name[:-9].strip()
            result["adapter_name"] = name or None

        powered_match = re.search(
            r"^\s*Powered:\s*(yes|no)\s*$",
            output,
            re.MULTILINE | re.IGNORECASE,
        )
        result["powered"] = bool(
            powered_match
            and self._yes(powered_match.group(1))
        )

        if not result["adapter"]:
            result["success"] = False
            result["error"] = "Kein lokaler Bluetooth-Adapter wurde gefunden."
        elif not result["powered"]:
            result["success"] = False
            result["error"] = (
                "Der Bluetooth-Adapter des Raspberry ist momentan ausgeschaltet. "
                "Phase 4W verändert den Adapterzustand noch nicht automatisch."
            )

        return result

    @staticmethod
    def _observed_addresses(scan_output):
        addresses = []
        seen = set()

        for match in _MAC_RE.finditer(
            str(scan_output or "")
        ):
            address = match.group(1).upper()
            if address in seen:
                continue
            seen.add(address)
            addresses.append(address)

        return addresses

    @staticmethod
    def _scan_lines_for_address(scan_output, address):
        wanted = str(address or "").upper()
        return [
            line.strip()
            for line in str(scan_output or "").splitlines()
            if wanted and wanted in line.upper()
        ]

    @staticmethod
    def _parse_info(address, info_output):
        fields = {
            key.lower(): value.strip()
            for key, value in _FIELD_RE.findall(
                str(info_output or "")
            )
        }

        manufacturer_keys = sorted(
            {
                key.lower()
                for key in _MFDATA_KEY_RE.findall(
                    str(info_output or "")
                )
            }
        )

        rssi = None
        try:
            if fields.get("rssi") not in {None, ""}:
                rssi = int(fields["rssi"])
        except (TypeError, ValueError):
            rssi = None

        return {
            "address": str(address or "").upper(),
            "name": fields.get("name") or None,
            "alias": fields.get("alias") or None,
            "rssi": rssi,
            "paired": ShellyProvisioningDiscovery._yes(
                fields.get("paired")
            ),
            "connected": ShellyProvisioningDiscovery._yes(
                fields.get("connected")
            ),
            "trusted": ShellyProvisioningDiscovery._yes(
                fields.get("trusted")
            ),
            "manufacturer_keys": manufacturer_keys,
        }

    @staticmethod
    def _looks_like_shelly(candidate, observed_lines=None):
        text = " ".join(
            [
                str(candidate.get("name") or ""),
                str(candidate.get("alias") or ""),
                " ".join(observed_lines or []),
            ]
        ).lower()

        if "shelly" in text:
            return True

        return SHELLY_MANUFACTURER_KEY in {
            str(item).lower()
            for item in candidate.get("manufacturer_keys") or []
        }

    @staticmethod
    def _model_hint(candidate):
        text = " ".join(
            [
                str(candidate.get("name") or ""),
                str(candidate.get("alias") or ""),
            ]
        ).lower()

        # Nur ein Hinweis aus dem Advertised Name. Die endgültige
        # Modellidentität kommt nach der WLAN-Provisionierung weiterhin über
        # Shelly.GetDeviceInfo und das bestehende MODEL_NAMES-Mapping.
        if "pstripg4" in text or "power strip 4" in text:
            return {
                "model": "S4PL-00416EU",
                "name": "Shelly Power Strip 4 Gen4",
            }

        return None

    def _candidate(self, address, scan_output):
        if not _MAC_RE.fullmatch(
            str(address or "")
        ):
            return None

        observed_lines = self._scan_lines_for_address(
            scan_output,
            address,
        )

        info_output = ""
        info_error = None

        try:
            info_output = self._run(
                "info",
                address,
                timeout=6,
            )
        except BluetoothDiscoveryError as exc:
            # Der Scan selbst kann einen Shelly bereits eindeutig über den
            # lokalen Namen zeigen. Ein fehlgeschlagener Detail-Read soll ihn
            # deshalb nicht zwingend aus der Liste entfernen.
            info_error = str(exc)

        candidate = self._parse_info(
            address,
            info_output,
        )

        if not self._looks_like_shelly(
            candidate,
            observed_lines,
        ):
            return None

        # ``bluetoothctl info`` liefert bei realen, nicht gepairten Shellys
        # nicht immer einen RSSI. Der aktive Scan hat den Wert aber bereits
        # gesehen; deshalb verwenden wir ihn ausschließlich als read-only
        # Fallback für die Anzeige.
        if candidate.get("rssi") is None:
            candidate["rssi"] = self._rssi_from_observed_lines(
                observed_lines
            )

        # Wenn bluetoothctl info keinen Namen liefert, verwenden wir nur dann
        # einen aus der Scan-Zeile, wenn dort tatsächlich "Shelly" vorkommt.
        if not candidate.get("name"):
            for line in observed_lines:
                if "shelly" not in line.lower():
                    continue
                tail = line.upper().split(
                    str(address).upper(),
                    1,
                )[-1].strip()
                if tail:
                    candidate["name"] = tail
                    break

        model_hint = self._model_hint(candidate)

        candidate.update(
            {
                "manufacturer": "Shelly",
                "discovery": "raspberry-bluetooth",
                "read_only": True,
                "provisioned": None,
                "model_hint": (
                    model_hint.get("model")
                    if model_hint
                    else None
                ),
                "model_name_hint": (
                    model_hint.get("name")
                    if model_hint
                    else None
                ),
                "detail_error": info_error,
            }
        )

        return candidate

    def scan(self, *, seconds=None):
        """Führt einen einmaligen lokalen Bluetooth-Discovery-Lauf aus."""

        duration = self._normalize_scan_seconds(
            self.scan_seconds
            if seconds is None
            else seconds
        )

        if not self._scan_lock.acquire(blocking=False):
            return {
                "success": False,
                "backend": BLUEZ_BACKEND,
                "busy": True,
                "duration": duration,
                "count": 0,
                "candidates": [],
                "error": "Ein Bluetooth-Scan läuft bereits.",
            }

        try:
            adapter = self.status()

            if not adapter.get("success"):
                return {
                    "success": False,
                    "backend": BLUEZ_BACKEND,
                    "busy": False,
                    "duration": duration,
                    "count": 0,
                    "candidates": [],
                    "adapter": adapter,
                    "error": adapter.get("error"),
                }

            scan_output = ""

            try:
                scan_output = self._run(
                    "--timeout",
                    str(duration),
                    "scan",
                    "on",
                    timeout=duration + 5,
                )
            finally:
                # Discovery-Zustand best-effort aufräumen. Das verändert weder
                # ein gefundenes Gerät noch dessen Pairing/WLAN-Konfiguration.
                try:
                    self._run(
                        "scan",
                        "off",
                        timeout=4,
                    )
                except BluetoothDiscoveryError:
                    pass

            candidates = []

            for address in self._observed_addresses(
                scan_output
            ):
                candidate = self._candidate(
                    address,
                    scan_output,
                )
                if candidate is not None:
                    candidates.append(candidate)

            candidates.sort(
                key=lambda item: (
                    -(
                        item.get("rssi")
                        if isinstance(item.get("rssi"), int)
                        else -999
                    ),
                    str(
                        item.get("name")
                        or item.get("address")
                        or ""
                    ).lower(),
                )
            )

            return {
                "success": True,
                "backend": BLUEZ_BACKEND,
                "busy": False,
                "duration": duration,
                "count": len(candidates),
                "candidates": candidates,
                "adapter": adapter,
                "error": None,
            }

        except BluetoothDiscoveryError as exc:
            return {
                "success": False,
                "backend": BLUEZ_BACKEND,
                "busy": False,
                "duration": duration,
                "count": 0,
                "candidates": [],
                "error": str(exc),
            }

        finally:
            self._scan_lock.release()


provisioning_discovery = ShellyProvisioningDiscovery()
