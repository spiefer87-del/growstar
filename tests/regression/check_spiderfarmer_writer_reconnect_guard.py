#!/usr/bin/env python3
"""Growstar 3.13.8 / SF writer reconnect guard regression."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.command_proxy import CommandSpiderFarmerProxy


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


class DummyWriter:
    pass


def fresh_proxy():
    proxy = object.__new__(CommandSpiderFarmerProxy)
    proxy._controller_writers = {}
    proxy._controller_subscriptions = {}
    return proxy


def main():
    controller_id = "744dbd59d734"

    # Normal cleanup: the closing connection owns the active writer.
    proxy = fresh_proxy()
    owned_writer = DummyWriter()
    proxy._controller_writers[controller_id] = owned_writer
    proxy._controller_subscriptions[controller_id] = {
        "SF/GGS/CB/API/DOWN/744DBD59D734"
    }

    removed = proxy._release_controller_session(
        controller_id,
        owned_writer,
    )

    require(removed is True, "Eigener Writer wird beim Disconnect entfernt")
    require(
        controller_id not in proxy._controller_writers,
        "Eigener Writer ist nach Cleanup entfernt",
    )
    require(
        controller_id not in proxy._controller_subscriptions,
        "Eigene Subscription ist nach Cleanup entfernt",
    )

    # Reconnect race:
    # old TLS connection closes after a newer connection already registered.
    proxy = fresh_proxy()
    old_writer = DummyWriter()
    new_writer = DummyWriter()

    proxy._controller_writers[controller_id] = new_writer
    new_subscriptions = {
        "SF/GGS/CB/API/DOWN/744DBD59D734"
    }
    proxy._controller_subscriptions[controller_id] = new_subscriptions

    removed = proxy._release_controller_session(
        controller_id,
        old_writer,
    )

    require(
        removed is False,
        "Stale alte Verbindung darf neuen Writer nicht entfernen",
    )
    require(
        proxy._controller_writers.get(controller_id) is new_writer,
        "Neu registrierter D734-Writer bleibt erhalten",
    )
    require(
        proxy._controller_subscriptions.get(controller_id) is new_subscriptions,
        "Subscriptions der neuen D734-Verbindung bleiben erhalten",
    )

    # Missing session id must be harmless.
    proxy = fresh_proxy()
    require(
        proxy._release_controller_session(None, DummyWriter()) is False,
        "Cleanup ohne Session-ID bleibt wirkungslos",
    )

    source = (
        ROOT / "bridge/spiderfarmer/command_proxy.py"
    ).read_text(encoding="utf-8")

    require(
        "current_writer is not controller_writer" in source,
        "Lifecycle-Guard prüft Writer-Identität",
    )
    require(
        "self._release_controller_session(" in source,
        "TLS-finally verwendet den geschützten Cleanup",
    )
    require(
        "self._controller_writers.pop(session_id, None)" in source,
        "Writer-Cleanup bleibt für die eigene Verbindung erhalten",
    )

    print("✅ Growstar 3.13.8 / SF Writer Reconnect Guard vollständig geprüft")


if __name__ == "__main__":
    main()
