"""Kleiner Telegram-Bot-API-Client für Growstar.

Der Bot-Token wird ausschließlich als HTTPS-URL-Bestandteil innerhalb dieses
Prozesses benutzt. Er wird weder geloggt noch als Prozessargument verwendet.
"""

from __future__ import annotations

import json
import re
from urllib import error, parse, request


TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10
_TOKEN_RE = re.compile(r"^[0-9]{5,}:[A-Za-z0-9_-]{20,}$")


class TelegramError(RuntimeError):
    pass


def validate_token_format(token):
    token = str(token or "").strip()

    if not token:
        raise ValueError("Telegram Bot-Token fehlt")
    if any(char in token for char in ("\x00", "\n", "\r", " ", "\t")):
        raise ValueError("Telegram Bot-Token enthält ungültige Zeichen")
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError("Telegram Bot-Token hat kein gültiges Format")

    return token


def _telegram_request(token, method, payload=None, *, timeout=DEFAULT_TIMEOUT):
    token = validate_token_format(token)
    method = str(method or "").strip()

    if not method or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", method):
        raise ValueError("Ungültige Telegram-Methode")

    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    body = None

    if payload:
        body = parse.urlencode(payload).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Growstar/3.9",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        description = "Telegram API hat die Anfrage abgelehnt"
        try:
            data = json.loads(exc.read().decode("utf-8", errors="replace"))
            description = str(data.get("description") or description)
        except Exception:
            pass
        raise TelegramError(description) from exc
    except error.URLError as exc:
        raise TelegramError("Telegram ist über das Internet momentan nicht erreichbar") from exc
    except TimeoutError as exc:
        raise TelegramError("Telegram-Anfrage hat das Zeitlimit überschritten") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TelegramError("Telegram hat keine gültige JSON-Antwort geliefert") from exc

    if not data.get("ok"):
        raise TelegramError(str(data.get("description") or "Telegram API Fehler"))

    return data.get("result")


def get_me(token):
    result = _telegram_request(token, "getMe")

    if not isinstance(result, dict) or not result.get("id"):
        raise TelegramError("Telegram konnte den Bot nicht bestätigen")

    return {
        "id": result.get("id"),
        "username": result.get("username"),
        "first_name": result.get("first_name"),
    }


def discover_private_chat(token):
    """Findet den zuletzt angeschriebenen privaten Bot-Chat.

    Der Benutzer muss dem Bot vorher mindestens eine Nachricht (z. B. /start)
    geschickt haben. Growstar benötigt dafür keinen dauerhaften Long-Polling-Bot.
    """

    updates = _telegram_request(
        token,
        "getUpdates",
        {
            "limit": 100,
            "timeout": 0,
            "allowed_updates": json.dumps(["message"]),
        },
    )

    if not isinstance(updates, list):
        updates = []

    for update in reversed(updates):
        if not isinstance(update, dict):
            continue

        message = update.get("message")
        if not isinstance(message, dict):
            continue

        chat = message.get("chat")
        if not isinstance(chat, dict) or chat.get("type") != "private":
            continue

        chat_id = chat.get("id")
        if chat_id is None:
            continue

        label_parts = [
            str(chat.get("first_name") or "").strip(),
            str(chat.get("last_name") or "").strip(),
        ]
        label = " ".join(part for part in label_parts if part).strip()
        username = str(chat.get("username") or "").strip()

        if not label:
            label = f"@{username}" if username else str(chat_id)

        return {
            "chat_id": str(chat_id),
            "chat_label": label,
            "chat_username": username or None,
        }

    raise TelegramError(
        "Kein privater Telegram-Chat gefunden. Öffne den Bot in Telegram, "
        "sende /start und drücke danach erneut auf „Chat finden“."
    )


def send_message(token, chat_id, text):
    token = validate_token_format(token)
    chat_id = str(chat_id or "").strip()
    text = str(text or "").strip()

    if not chat_id:
        raise ValueError("Telegram Chat-ID fehlt")
    if any(char in chat_id for char in ("\x00", "\n", "\r")):
        raise ValueError("Ungültige Telegram Chat-ID")
    if not text:
        raise ValueError("Telegram Nachricht ist leer")

    if len(text) > 4096:
        text = text[:4080] + "\n…"

    result = _telegram_request(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )

    if not isinstance(result, dict):
        raise TelegramError("Telegram hat keine Nachrichtenbestätigung geliefert")

    return {
        "message_id": result.get("message_id"),
        "date": result.get("date"),
        "chat_id": str((result.get("chat") or {}).get("id") or chat_id),
    }
