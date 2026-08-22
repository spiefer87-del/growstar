"""Lokaler Growstar-Secret-Store für WLAN-Geräteprovisionierung.

Die Datei liegt ausschließlich unter ``instance/secrets`` und ist damit kein
Repository-Inhalt. Sie enthält nur WLAN-Passphrasen, die Growstar nach einer
erfolgreich verifizierten Netzwerkaktion oder einer expliziten Verifikation
speichern durfte.

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


class NetworkCredentialStore:
    """Kleiner atomarer Secret-Store mit Cross-Worker-Lock."""

    def __init__(self, path=DEFAULT_SECRET_PATH):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(
            self.path.suffix + ".lock"
        )

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

    def _read_unlocked(self):
        if not self.path.exists():
            return {
                "version": 1,
                "networks": {},
            }

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

        return {
            "version": 1,
            "networks": networks,
        }

    def _write_unlocked(self, data):
        self._ensure_parent()

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
                    data,
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
                "secret_path": "instance/secrets/network_credentials.json",
            }

        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )
            lock.close()


network_secret_store = NetworkCredentialStore()
