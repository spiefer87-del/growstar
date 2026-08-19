"""Nicht blockierender Versandkanal für Growstar-Alarme."""

from __future__ import annotations

import itertools
import queue
import threading
import time

from core.release import GROWSTAR_VERSION
from services.notification_settings import telegram_credentials
from services.telegram import TelegramError, send_message


_QUEUE = queue.PriorityQueue(maxsize=500)
_SEQUENCE = itertools.count()
_STATUS_LOCK = threading.RLock()

_STATUS = {
    "worker_started_at": None,
    "last_success_at": None,
    "last_error_at": None,
    "last_error": None,
    "sent_count": 0,
    "failed_count": 0,
    "dropped_count": 0,
}

_RETRY_DELAYS = (5, 30, 120)
_STOP = threading.Event()


def _thread_alive():
    return any(
        thread.name == "growstar-notifications" and thread.is_alive()
        for thread in threading.enumerate()
    )


def notification_runtime_status():
    with _STATUS_LOCK:
        status = dict(_STATUS)

    status.update({
        "thread_alive": _thread_alive(),
        "queue_depth": _QUEUE.qsize(),
    })
    return status


def _record_success():
    with _STATUS_LOCK:
        _STATUS["last_success_at"] = time.time()
        _STATUS["last_error"] = None
        _STATUS["sent_count"] += 1


def _record_error(message, *, final=False):
    with _STATUS_LOCK:
        _STATUS["last_error_at"] = time.time()
        _STATUS["last_error"] = str(message)
        if final:
            _STATUS["failed_count"] += 1


def enqueue_notification(text, *, event_key=None, kind="alarm"):
    job = {
        "text": str(text or ""),
        "event_key": event_key,
        "kind": kind,
        "attempt": 0,
    }

    try:
        _QUEUE.put_nowait((time.time(), next(_SEQUENCE), job))
        return True
    except queue.Full:
        with _STATUS_LOCK:
            _STATUS["dropped_count"] += 1
            _STATUS["last_error_at"] = time.time()
            _STATUS["last_error"] = "Benachrichtigungswarteschlange ist voll"
        return False


def _deliver(job):
    credentials = telegram_credentials()

    if not credentials["enabled"]:
        return "skipped"

    if not credentials["bot_token"] or not credentials["chat_id"]:
        raise TelegramError("Telegram ist aktiviert, aber nicht vollständig eingerichtet")

    send_message(
        credentials["bot_token"],
        credentials["chat_id"],
        job["text"],
    )
    return "sent"


def notification_worker_loop():
    with _STATUS_LOCK:
        _STATUS["worker_started_at"] = time.time()

    while not _STOP.is_set():
        try:
            due_at, sequence, job = _QUEUE.get(timeout=1)
        except queue.Empty:
            continue

        now = time.time()
        if due_at > now:
            _QUEUE.put((due_at, sequence, job))
            time.sleep(min(1.0, max(0.05, due_at - now)))
            continue

        try:
            outcome = _deliver(job)
            if outcome == "sent":
                _record_success()
        except Exception as exc:
            attempt = int(job.get("attempt") or 0)

            if attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[attempt]
                retry = dict(job)
                retry["attempt"] = attempt + 1
                _record_error(
                    f"Telegram-Versand fehlgeschlagen; neuer Versuch in {delay}s: {exc}"
                )
                _QUEUE.put(
                    (time.time() + delay, next(_SEQUENCE), retry)
                )
            else:
                _record_error(
                    f"Telegram-Versand endgültig fehlgeschlagen: {exc}",
                    final=True,
                )
        finally:
            _QUEUE.task_done()


def send_test_notification():
    credentials = telegram_credentials()

    if not credentials["bot_token"]:
        raise ValueError("Telegram Bot ist noch nicht verbunden")
    if not credentials["chat_id"]:
        raise ValueError("Telegram Chat ist noch nicht verbunden")

    result = send_message(
        credentials["bot_token"],
        credentials["chat_id"],
        (
            "✅ Growstar Testnachricht\n\n"
            f"Growstar v{GROWSTAR_VERSION}\n"
            "Telegram-Benachrichtigungen funktionieren."
        ),
    )
    _record_success()
    return result
