"""Spider Farmer PS5/PS10 outlet command compiler.

This module is deliberately separate from the existing GGS controller compiler.
It implements only the reverse-engineered, reference-confirmed Power Strip
manual outlet toggle:

    keyPath: ["outlet", "O1".."O10"]
    block:   {"modeType": 0, "mOnOff": 0|1}

The DOWN topic is not guessed. The command-capable proxy supplies the exact
currently subscribed PS topic for the active controller session.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from .state_model import parse_topic


class SpiderFarmerPowerStripCommandError(RuntimeError):
    pass


def normalize_outlet(value):
    text = str(value or "").strip().upper()
    if not text.startswith("O") or not text[1:].isdigit():
        raise SpiderFarmerPowerStripCommandError("Ungültiger Power-Strip-Kanal")
    number = int(text[1:])
    if not 1 <= number <= 10:
        raise SpiderFarmerPowerStripCommandError(
            "Power-Strip-Kanal muss zwischen O1 und O10 liegen"
        )
    return f"O{number}"


def normalize_power(value):
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int) and value in (0, 1):
        return value

    text = str(value or "").strip().lower()
    if text in {"1", "on", "true", "ein"}:
        return 1
    if text in {"0", "off", "false", "aus"}:
        return 0

    raise SpiderFarmerPowerStripCommandError(
        "Power muss boolesch bzw. EIN/AUS sein"
    )


def _capture_candidates(capture_path):
    capture_path = Path(capture_path)
    candidates = [capture_path]
    rotated = Path(str(capture_path) + ".1")
    if rotated.exists():
        candidates.append(rotated)
    return candidates


def find_latest_uid(capture_path, *, pid):
    """Recover the SF account uid from already observed traffic.

    PS outlet commands in the reference bridge carry uid in their normal
    setConfigField envelope. Growstar never invents an account uid; it reuses
    the most recently observed uid for exactly the requested PID.
    """

    wanted_pid = str(pid or "").strip().upper()
    if not wanted_pid:
        raise SpiderFarmerPowerStripCommandError("Power-Strip-PID fehlt")

    for candidate in _capture_candidates(capture_path):
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue

        for line in reversed(lines):
            try:
                row = json.loads(line)
            except (TypeError, ValueError):
                continue

            if not isinstance(row, dict):
                continue

            topic_info = parse_topic(row.get("topic"))
            if not topic_info or topic_info.get("pid") != wanted_pid:
                continue

            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue

            uid = str(payload.get("uid") or "").strip()
            if uid:
                return uid

    raise SpiderFarmerPowerStripCommandError(
        "Für diesen Power Strip wurde noch keine Spider-Farmer-UID beobachtet"
    )


def compile_outlet_power_command(
    capture_path,
    *,
    pid,
    outlet,
    power,
    topic,
):
    pid = str(pid or "").strip().upper()
    if not pid:
        raise SpiderFarmerPowerStripCommandError("Power-Strip-PID fehlt")

    outlet = normalize_outlet(outlet)
    power = normalize_power(power)

    topic_info = parse_topic(topic)
    if (
        not topic_info
        or topic_info.get("direction") != "down"
        or topic_info.get("pid") != pid
        or str(topic_info.get("prefix") or "").upper() != "PS"
    ):
        raise SpiderFarmerPowerStripCommandError(
            "Kein gültiges aktives Spider-Farmer-PS-DOWN-Topic"
        )

    uid = find_latest_uid(capture_path, pid=pid)

    payload = {
        "method": "setConfigField",
        "pid": pid,
        "params": {
            "keyPath": ["outlet", outlet],
            outlet: {
                "modeType": 0,
                "mOnOff": power,
            },
        },
        "msgId": str(int(time.time() * 1000)),
        "uid": uid,
    }

    return {
        "topic": str(topic),
        "payload": payload,
        "module": "outlet",
        "outlet": outlet,
        "power": power,
        "changed_fields": {
            "modeType": 0,
            "mOnOff": power,
        },
        "diagnostic": "ps_outlet_manual",
    }
