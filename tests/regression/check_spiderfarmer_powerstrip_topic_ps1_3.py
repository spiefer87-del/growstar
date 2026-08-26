#!/usr/bin/env python3
"""Growstar 3.13.6 / SF.PS1.3 static topic regression."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    command = (ROOT / "bridge/spiderfarmer/powerstrip_command.py").read_text(encoding="utf-8")
    proxy = (ROOT / "bridge/spiderfarmer/powerstrip_proxy.py").read_text(encoding="utf-8")

    require(
        'POWERSTRIP_PREFIXES = frozenset({"PS", "PS5", "PS10"})' in command,
        "PS/PS5/PS10 sind die einzige zugelassene Power-Strip-Topicfamilie",
    )
    require(
        'if len(subscribed) == 1:' in proxy,
        "Echte DOWN-Subscription hat Vorrang",
    )
    require(
        'if len(subscribed) > 1:' in proxy,
        "Mehrere DOWN-Subscriptions bleiben fail-closed",
    )
    require(
        'info.get("direction") != "up"' in proxy,
        "Fallback akzeptiert ausschließlich beobachtete UP-Topics",
    )
    require(
        'info.get("pid") != wanted_pid' in proxy,
        "Fallback bleibt an dieselbe PID gebunden",
    )
    require(
        'return f"SF/GGS/{prefix}/API/DOWN/{wanted_pid}"' in proxy,
        "DOWN wird nur aus validiertem Prefix und derselben PID konstruiert",
    )
    require(
        '"Power-Strip-Topic-Prefix ist nicht eindeutig"' in proxy,
        "Mehrdeutige Prefixe blockieren",
    )

    print("✅ Growstar 3.13.6 / SF.PS1.3 vollständig geprüft")


if __name__ == "__main__":
    main()
