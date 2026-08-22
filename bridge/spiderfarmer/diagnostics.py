"""Local, private diagnostics for the Spider Farmer read-only bridge."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time


_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
MAX_CAPTURE_PAYLOAD_BYTES = 256 * 1024


def _utc_timestamp() -> str:
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def normalize_session_id(client_id: str | None) -> str:
    raw = str(client_id or "").strip()
    compact_hex = re.sub(r"[^0-9A-Fa-f]", "", raw)

    if len(compact_hex) == 12:
        return compact_hex.lower()

    safe = _SAFE_ID.sub("_", raw).strip("._-")
    return (safe[:96] or "unknown").lower()


class BridgeDiagnostics:
    """Maintains a small state file plus a rotating raw JSONL capture.

    The state file only contains summary metadata. The JSONL capture can contain
    device MACs, UIDs and configuration values and is therefore created mode
    0600 below Growstar's local instance directory.
    """

    def __init__(
        self,
        state_dir,
        *,
        capture_payloads=True,
        max_capture_bytes=5 * 1024 * 1024,
    ):
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.state_path = self.state_dir / "bridge_state.json"
        self.capture_path = self.state_dir / "raw_frames.jsonl"
        self.capture_payloads = bool(capture_payloads)
        self.max_capture_bytes = max(256 * 1024, int(max_capture_bytes))

        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.state_dir, 0o700)
        except OSError:
            pass

        self.state = {
            "schema": 1,
            "phase": "SF.1",
            "read_only": True,
            "started_at": _utc_timestamp(),
            "listener": {},
            "upstream": {},
            "totals": {
                "connections": 0,
                "publishes_up": 0,
                "publishes_down": 0,
                "parse_errors": 0,
                "transport_errors": 0,
            },
            "sessions": {},
            "last_error": None,
        }
        self._last_flush_monotonic = 0.0
        self.flush(force=True)

    def configure(self, *, listen_host, listen_port, upstream_host, upstream_port):
        self.state["listener"] = {
            "host": str(listen_host),
            "port": int(listen_port),
        }
        self.state["upstream"] = {
            "host": str(upstream_host),
            "port": int(upstream_port),
        }
        self.flush(force=True)

    def connection_opened(self, peer):
        self.state["totals"]["connections"] += 1
        self.state["last_connection_at"] = _utc_timestamp()
        self.state["last_peer"] = _peer_text(peer)
        self.flush()

    def session_bound(self, client_id, peer):
        session_id = normalize_session_id(client_id)
        now = _utc_timestamp()
        session = self.state["sessions"].setdefault(session_id, {})
        session.update(
            {
                "session_id": session_id,
                "client_id": str(client_id or ""),
                "peer": _peer_text(peer),
                "connected": True,
                "connected_at": session.get("connected_at") or now,
                "last_seen": now,
                "publishes_up": int(session.get("publishes_up") or 0),
                "publishes_down": int(session.get("publishes_down") or 0),
            }
        )
        self.flush(force=True)
        return session_id

    def subscriptions(self, session_id, topics):
        if not session_id:
            return
        session = self.state["sessions"].setdefault(session_id, {})
        session["subscriptions"] = [str(topic) for topic in topics][-20:]
        session["last_seen"] = _utc_timestamp()
        self.flush()

    def publish(self, session_id, *, direction, topic, message, qos=0, retain=False):
        direction = "down" if direction == "down" else "up"
        total_key = f"publishes_{direction}"
        self.state["totals"][total_key] += 1

        if not session_id:
            session_id = "unknown"

        now = _utc_timestamp()
        session = self.state["sessions"].setdefault(
            session_id,
            {
                "session_id": session_id,
                "client_id": "",
                "connected": True,
                "publishes_up": 0,
                "publishes_down": 0,
            },
        )
        session[total_key] = int(session.get(total_key) or 0) + 1
        session["last_seen"] = now
        session["last_direction"] = direction
        session["last_topic"] = str(topic or "")
        session["last_payload_bytes"] = len(message or b"")

        decoded, payload_text = _decode_payload(message)
        if isinstance(decoded, dict):
            session["last_method"] = decoded.get("method")
            data = decoded.get("data")
            session["last_data_keys"] = (
                sorted(str(key) for key in data.keys())
                if isinstance(data, dict)
                else []
            )
            if decoded.get("pid") is not None:
                session["last_pid"] = str(decoded.get("pid"))
            if decoded.get("uid") not in (None, ""):
                session["uid_seen"] = True
        else:
            session["last_method"] = None
            session["last_data_keys"] = []

        if self.capture_payloads:
            record = {
                "ts": now,
                "phase": "SF.1",
                "direction": direction,
                "session_id": session_id,
                "topic": str(topic or ""),
                "qos": int(qos or 0),
                "retain": bool(retain),
                "payload_bytes": len(message or b""),
            }
            if decoded is not None:
                record["payload"] = decoded
            else:
                record["payload_text"] = payload_text
            self._append_capture(record)

        self.flush()

    def parse_error(self, detail):
        self.state["totals"]["parse_errors"] += 1
        self.state["last_error"] = {
            "at": _utc_timestamp(),
            "stage": "mqtt-parse",
            "detail": str(detail)[:500],
        }
        self.flush()

    def transport_error(self, peer, stage, detail):
        self.state["totals"]["transport_errors"] += 1
        self.state["last_error"] = {
            "at": _utc_timestamp(),
            "stage": str(stage),
            "peer": _peer_text(peer),
            "detail": str(detail)[:500],
        }
        self.flush(force=True)

    def disconnected(self, session_id):
        if not session_id:
            return
        session = self.state["sessions"].get(session_id)
        if not isinstance(session, dict):
            return
        session["connected"] = False
        session["disconnected_at"] = _utc_timestamp()
        self.flush(force=True)

    def flush(self, *, force=False):
        now = time.monotonic()
        if not force and (now - self._last_flush_monotonic) < 1.0:
            return
        self._atomic_json(self.state_path, self.state)
        self._last_flush_monotonic = now

    def _append_capture(self, record):
        self._rotate_capture_if_needed()

        line = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        with self.capture_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

        try:
            os.chmod(self.capture_path, 0o600)
        except OSError:
            pass

    def _rotate_capture_if_needed(self):
        try:
            size = self.capture_path.stat().st_size
        except FileNotFoundError:
            return

        if size < self.max_capture_bytes:
            return

        backup = self.capture_path.with_suffix(".jsonl.1")
        try:
            backup.unlink()
        except FileNotFoundError:
            pass
        self.capture_path.replace(backup)
        try:
            os.chmod(backup, 0o600)
        except OSError:
            pass

    @staticmethod
    def _atomic_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=".spiderfarmer-state-",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def _peer_text(peer):
    if isinstance(peer, (tuple, list)):
        return ":".join(str(value) for value in peer[:2])
    return str(peer or "")


def _decode_payload(message):
    raw = bytes(message or b"")
    if len(raw) > MAX_CAPTURE_PAYLOAD_BYTES:
        raw = raw[:MAX_CAPTURE_PAYLOAD_BYTES]

    text = raw.decode("utf-8", errors="replace")

    try:
        return json.loads(text), text
    except (ValueError, TypeError):
        return None, text
