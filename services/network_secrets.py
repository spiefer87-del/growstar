"""Lokaler Growstar-Secret-Store für WLAN-Geräteprovisionierung.

Die Datei liegt ausschließlich unter ``instance/secrets`` und ist damit kein
Repository-Inhalt. Sie enthält WLAN-Passphrasen, die Growstar nach einer
erfolgreich verifizierten Netzwerkaktion oder einer expliziten Verifikation
speichern durfte.

Seit Growstar 3.11.0 speichert dieselbe Datei zusätzlich das festgelegte
Geräte-Provisionierungs-WLAN. Dadurch bleibt z. B. die Shelly-Erstinbetriebnahme
auf dem Heimnetz, auch wenn der Raspberry sein WLAN-Interface später als
separaten Spider-Farmer-Access-Point verwendet.

Es gibt bewusst keine API, die ein gespeichertes Secret wieder an den Browser
zurückgibt.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import tempfile
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRET_PATH = (
    PROJECT_ROOT
    / "instance"
    / "secrets"
    / "network_credentials.json"
)

STORE_VERSION = 2


class NetworkSecretError(RuntimeError):
    pass


def _validate_ssid(value):
    ssid = str(value or "").strip()

    if not ssid:
        raise ValueError("WLAN-Name fehlt")

    if any(char in ssid for char in ("\x00", "\n", "\r")):
        raise ValueError("Ungültiger WLAN-Name")

    if len(ssid.encode("utf-8")) > 32:
        raise ValueError("Der WLAN-Name ist länger als 32 Byte")

    return ssid


def _validate_passphrase(value):
    secret = "" if value is None else str(value)

    if not secret:
        raise ValueError("Bitte die WLAN-Passphrase eingeben")

    if any(char in secret for char in ("\x00", "\n", "\r")):
        raise ValueError(
            "Das WLAN-Passwort enthält ungültige Steuerzeichen"
        )

    if len(secret) > 128:
        raise ValueError("Das WLAN-Passwort ist zu lang")

    return secret


def _normalize_security(value):
    security = str(value or "--").strip().upper() or "--"

    if any(char in security for char in ("\x00", "\n", "\r")):
        raise ValueError("Ungültige WLAN-Sicherheitsangabe")

    return security[:128]


class NetworkCredentialStore:
    """Atomarer Cross-Worker-Store für Secrets und Provisionierungsziel."""

    def __init__(self, path=DEFAULT_SECRET_PATH):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(
            self.path.suffix + ".lock"
        )

    def _empty_data(self):
        return {
            "version": STORE_VERSION,
            "provisioning_target": None,
            "networks": {},
        }

    def _ensure_parent(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

    def _locked(self):
        self._ensure_parent()

        handle = open(
            self.lock_path,
            "a+",
            encoding="utf-8",
        )

        try:
            os.chmod(self.lock_path, 0o600)
        except OSError:
            pass

        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX,
        )

        return handle

    def _normalize_target(self, value):
        if not isinstance(value, dict):
            return None

        try:
            ssid = _validate_ssid(value.get("ssid"))
        except (TypeError, ValueError):
            return None

        security = _normalize_security(
            value.get("security")
        )

        return {
            "ssid": ssid,
            "security": security,
            "open_network": bool(
                value.get("open_network")
            ),
            "source": (
                str(
                    value.get("source")
                    or "stored"
                ).strip()
                or "stored"
            )[:128],
            "updated_at": value.get("updated_at"),
        }

    def _read_unlocked(self):
        if not self.path.exists():
            return self._empty_data()

        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

        try:
            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            raise NetworkSecretError(
                "Growstar-WLAN-Secret-Datei ist nicht lesbar"
            ) from exc

        if not isinstance(data, dict):
            raise NetworkSecretError(
                "Growstar-WLAN-Secret-Datei hat ein ungültiges Format"
            )

        networks = data.get("networks")

        if not isinstance(networks, dict):
            raise NetworkSecretError(
                "Growstar-WLAN-Secret-Datei enthält keine gültige Netzwerkliste"
            )

        # Version 1 besaß nur ``networks``. Das Lesen bleibt vollständig
        # kompatibel; erst der nächste legitime Schreibvorgang persistiert v2.
        return {
            "version": STORE_VERSION,
            "provisioning_target": self._normalize_target(
                data.get("provisioning_target")
            ),
            "networks": networks,
        }

    def _write_unlocked(self, data):
        self._ensure_parent()

        payload = {
            "version": STORE_VERSION,
            "provisioning_target": self._normalize_target(
                data.get("provisioning_target")
            ),
            "networks": data.get("networks") or {},
        }

        fd, temp_path = tempfile.mkstemp(
            prefix=".network-credentials-",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )

        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    payload,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temp_path,
                self.path,
            )

            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def save(self, ssid, passphrase, *, source):
        ssid = _validate_ssid(ssid)
        secret = _validate_passphrase(passphrase)
        source = str(source or "verified").strip() or "verified"

        lock = self._locked()

        try:
            data = self._read_unlocked()

            data["networks"][ssid] = {
                "passphrase": secret,
                "source": source,
                "updated_at": time.time(),
            }

            self._write_unlocked(data)

        finally:
            secret = ""
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

        return self.status(ssid)

    def get(self, ssid):
        ssid = _validate_ssid(ssid)
        lock = self._locked()

        try:
            data = self._read_unlocked()
            entry = data["networks"].get(ssid)

            if not isinstance(entry, dict):
                return None

            secret = entry.get("passphrase")

            if not isinstance(secret, str) or not secret:
                return None

            return secret

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

    def remove(self, ssid):
        ssid = _validate_ssid(ssid)
        lock = self._locked()

        try:
            data = self._read_unlocked()
            existed = (
                data["networks"].pop(
                    ssid,
                    None,
                )
                is not None
            )

            if existed:
                self._write_unlocked(data)

            return existed

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

    def provisioning_target(self):
        lock = self._locked()

        try:
            data = self._read_unlocked()
            target = data.get("provisioning_target")

            if not isinstance(target, dict):
                return None

            return dict(target)

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

    def set_provisioning_target(
        self,
        ssid,
        *,
        security,
        open_network,
        source,
    ):
        ssid = _validate_ssid(ssid)
        security = _normalize_security(security)
        source = str(source or "verified").strip() or "verified"

        lock = self._locked()

        try:
            data = self._read_unlocked()

            target = {
                "ssid": ssid,
                "security": security,
                "open_network": bool(open_network),
                "source": source[:128],
                "updated_at": time.time(),
            }

            data["provisioning_target"] = target
            self._write_unlocked(data)

            return dict(target)

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

    def ensure_provisioning_target(
        self,
        ssid,
        *,
        security,
        open_network,
        source,
    ):
        """Legt das Ziel nur an, wenn noch keines festgelegt wurde."""

        ssid = _validate_ssid(ssid)
        security = _normalize_security(security)
        source = str(source or "migration").strip() or "migration"

        lock = self._locked()

        try:
            data = self._read_unlocked()
            existing = data.get("provisioning_target")

            if isinstance(existing, dict):
                return dict(existing)

            target = {
                "ssid": ssid,
                "security": security,
                "open_network": bool(open_network),
                "source": source[:128],
                "updated_at": time.time(),
            }

            data["provisioning_target"] = target
            self._write_unlocked(data)

            return dict(target)

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()

    def status(self, ssid=None):
        active_ssid = (
            _validate_ssid(ssid)
            if ssid
            else None
        )

        lock = self._locked()

        try:
            data = self._read_unlocked()
            networks = data["networks"]
            entry = (
                networks.get(active_ssid)
                if active_ssid
                else None
            )
            target = data.get("provisioning_target")
            target_ssid = (
                target.get("ssid")
                if isinstance(target, dict)
                else None
            )
            target_entry = (
                networks.get(target_ssid)
                if target_ssid
                else None
            )

            return {
                "success": True,
                "active_ssid": active_ssid,
                "stored_for_active": bool(
                    isinstance(entry, dict)
                    and isinstance(
                        entry.get("passphrase"),
                        str,
                    )
                    and bool(entry.get("passphrase"))
                ),
                "stored_count": len(networks),
                "source": (
                    entry.get("source")
                    if isinstance(entry, dict)
                    else None
                ),
                "updated_at": (
                    entry.get("updated_at")
                    if isinstance(entry, dict)
                    else None
                ),
                "provisioning_target_set": bool(target_ssid),
                "provisioning_ssid": target_ssid,
                "provisioning_security": (
                    target.get("security")
                    if isinstance(target, dict)
                    else None
                ),
                "provisioning_open_network": (
                    bool(target.get("open_network"))
                    if isinstance(target, dict)
                    else False
                ),
                "provisioning_source": (
                    target.get("source")
                    if isinstance(target, dict)
                    else None
                ),
                "provisioning_updated_at": (
                    target.get("updated_at")
                    if isinstance(target, dict)
                    else None
                ),
                "stored_for_provisioning": bool(
                    isinstance(target, dict)
                    and (
                        bool(target.get("open_network"))
                        or (
                            isinstance(target_entry, dict)
                            and isinstance(
                                target_entry.get("passphrase"),
                                str,
                            )
                            and bool(target_entry.get("passphrase"))
                        )
                    )
                ),
                "secret_path": "instance/secrets/network_credentials.json",
            }

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()


network_secret_store = NetworkCredentialStore()
