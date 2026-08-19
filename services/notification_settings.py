"""Lokale, nicht versionierte Einstellungen für Growstar-Benachrichtigungen."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import threading


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_DIR = PROJECT_ROOT / "instance"
SETTINGS_FILE = INSTANCE_DIR / "notifications.json"

_LOCK = threading.RLock()

RULE_KEYS = (
    "sensor_stale",
    "sensor_limits",
    "hardware",
    "safety",
    "control_loop",
    "configuration",
    "controller",
)

DEFAULT_SETTINGS = {
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "bot_id": None,
        "bot_username": None,
        "bot_name": None,
        "chat_id": "",
        "chat_label": None,
        "chat_username": None,
    },
    "rules": {
        key: True
        for key in RULE_KEYS
    },
    "send_recovery": True,
    "repeat_minutes": 60,
}


def _atomic_write(data):
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".tmp")

    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())

    os.chmod(temp, 0o600)
    os.replace(temp, SETTINGS_FILE)
    os.chmod(SETTINGS_FILE, 0o600)


def _normalize(raw):
    result = deepcopy(DEFAULT_SETTINGS)

    if not isinstance(raw, dict):
        return result

    telegram = raw.get("telegram")
    if isinstance(telegram, dict):
        for key in result["telegram"]:
            if key in telegram:
                result["telegram"][key] = telegram[key]

    rules = raw.get("rules")
    if isinstance(rules, dict):
        for key in RULE_KEYS:
            if key in rules:
                result["rules"][key] = bool(rules[key])

    if "send_recovery" in raw:
        result["send_recovery"] = bool(raw["send_recovery"])

    try:
        repeat = int(raw.get("repeat_minutes", result["repeat_minutes"]))
    except (TypeError, ValueError):
        repeat = result["repeat_minutes"]

    if repeat not in {0, 15, 30, 60, 120, 240}:
        repeat = 60

    result["repeat_minutes"] = repeat
    result["telegram"]["enabled"] = bool(result["telegram"].get("enabled"))
    result["telegram"]["bot_token"] = str(
        result["telegram"].get("bot_token") or ""
    ).strip()
    result["telegram"]["chat_id"] = str(
        result["telegram"].get("chat_id") or ""
    ).strip()

    return result


def load_notification_settings():
    with _LOCK:
        if not SETTINGS_FILE.exists():
            return deepcopy(DEFAULT_SETTINGS)

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
                return _normalize(json.load(handle))
        except Exception:
            # Beschädigte lokale Notification-Config schaltet Telegram fail-safe
            # ab, statt den Growstar-Start zu blockieren.
            return deepcopy(DEFAULT_SETTINGS)


def _save(settings):
    normalized = _normalize(settings)
    _atomic_write(normalized)
    return normalized


def public_notification_settings():
    settings = load_notification_settings()
    telegram = settings["telegram"]

    return {
        "telegram": {
            "enabled": bool(telegram["enabled"]),
            "token_configured": bool(telegram["bot_token"]),
            "bot_id": telegram.get("bot_id"),
            "bot_username": telegram.get("bot_username"),
            "bot_name": telegram.get("bot_name"),
            "chat_configured": bool(telegram["chat_id"]),
            "chat_label": telegram.get("chat_label"),
            "chat_username": telegram.get("chat_username"),
        },
        "rules": dict(settings["rules"]),
        "send_recovery": bool(settings["send_recovery"]),
        "repeat_minutes": int(settings["repeat_minutes"]),
    }


def save_bot_connection(token, identity):
    token = str(token or "").strip()
    if not token:
        raise ValueError("Telegram Bot-Token fehlt")

    with _LOCK:
        settings = load_notification_settings()
        telegram = settings["telegram"]

        telegram["bot_token"] = token
        telegram["bot_id"] = identity.get("id")
        telegram["bot_username"] = identity.get("username")
        telegram["bot_name"] = identity.get("first_name")

        # Ein neuer Token kann zu einem anderen Bot gehören. Die bisherige
        # Chat-Zuordnung wird deshalb bewusst zurückgesetzt.
        telegram["chat_id"] = ""
        telegram["chat_label"] = None
        telegram["chat_username"] = None
        telegram["enabled"] = False

        _save(settings)

    return public_notification_settings()


def save_discovered_chat(chat):
    with _LOCK:
        settings = load_notification_settings()
        if not settings["telegram"]["bot_token"]:
            raise ValueError("Telegram Bot ist noch nicht verbunden")

        settings["telegram"]["chat_id"] = str(chat.get("chat_id") or "").strip()
        settings["telegram"]["chat_label"] = chat.get("chat_label")
        settings["telegram"]["chat_username"] = chat.get("chat_username")
        _save(settings)

    return public_notification_settings()


def update_notification_preferences(payload):
    if not isinstance(payload, dict):
        raise TypeError("Benachrichtigungseinstellungen müssen ein Objekt sein")

    with _LOCK:
        settings = load_notification_settings()

        if "rules" in payload:
            rules = payload["rules"]
            if not isinstance(rules, dict):
                raise ValueError("rules muss ein Objekt sein")
            for key in RULE_KEYS:
                if key in rules:
                    settings["rules"][key] = bool(rules[key])

        if "send_recovery" in payload:
            settings["send_recovery"] = bool(payload["send_recovery"])

        if "repeat_minutes" in payload:
            try:
                repeat = int(payload["repeat_minutes"])
            except (TypeError, ValueError) as exc:
                raise ValueError("Ungültiges Wiederholungsintervall") from exc
            if repeat not in {0, 15, 30, 60, 120, 240}:
                raise ValueError("Ungültiges Wiederholungsintervall")
            settings["repeat_minutes"] = repeat

        if "telegram_enabled" in payload:
            enabled = bool(payload["telegram_enabled"])
            telegram = settings["telegram"]
            if enabled and not (
                telegram.get("bot_token")
                and telegram.get("chat_id")
            ):
                raise ValueError(
                    "Telegram kann erst aktiviert werden, wenn Bot und Chat verbunden sind"
                )
            telegram["enabled"] = enabled

        _save(settings)

    return public_notification_settings()


def clear_telegram_connection():
    with _LOCK:
        settings = load_notification_settings()
        settings["telegram"] = deepcopy(DEFAULT_SETTINGS["telegram"])
        _save(settings)

    return public_notification_settings()


def telegram_credentials():
    settings = load_notification_settings()
    telegram = settings["telegram"]

    return {
        "enabled": bool(telegram.get("enabled")),
        "bot_token": str(telegram.get("bot_token") or ""),
        "chat_id": str(telegram.get("chat_id") or ""),
        "chat_label": telegram.get("chat_label"),
        "bot_username": telegram.get("bot_username"),
    }


def notification_rule_enabled(rule):
    settings = load_notification_settings()
    return bool(settings.get("rules", {}).get(rule, False))
