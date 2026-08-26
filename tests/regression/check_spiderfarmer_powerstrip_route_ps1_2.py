#!/usr/bin/env python3
"""Growstar 3.13.7 / SF.PS1.3a route regression."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routes.spiderfarmer_powerstrip import _find_outlet, _is_power_strip


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    require(
        _is_power_strip({"prefix": "PS", "devices": []}),
        "Kanonischer Prefix PS wird als Power Strip erkannt",
    )

    observed = {
        "prefix": None,
        "devices": [{
            "kind": "outlet",
            "channels": [{"channel": "O1"}, {"channel": "O5"}],
        }],
    }
    require(
        _is_power_strip(observed),
        "Normalisiertes Outlet-Inventar dient als sicherer Route-Fallback",
    )

    ggs = {
        "prefix": "CB",
        "devices": [{"kind": "fan", "channels": []}],
    }
    require(
        not _is_power_strip(ggs),
        "Normaler GGS-Controller bleibt ausgeschlossen",
    )

    malformed = {
        "prefix": None,
        "devices": [{
            "kind": "outlet",
            "channels": [{"channel": "relay1"}, {"channel": "O99"}],
        }],
    }
    require(
        not _is_power_strip(malformed),
        "Ungültiges Outlet-Inventar öffnet den Power-Strip-Pfad nicht",
    )

    channel = _find_outlet(
        {
            "devices": [{
                "kind": "outlet",
                "channels": [
                    {"channel": "O1"},
                    {"channel": "O5", "effective": {"on": 1}},
                ],
            }],
        },
        "o5",
    )
    require(
        channel and channel.get("channel") == "O5",
        "O5 wird im beobachteten Inventar exakt gefunden",
    )

    route_source = (
        ROOT / "routes/spiderfarmer_powerstrip.py"
    ).read_text(encoding="utf-8")
    require(
        "if not _is_power_strip(controller):" in route_source,
        "POST-Route verwendet zentrale Power-Strip-Klassifikation",
    )

    proxy_source = (
        ROOT / "bridge/spiderfarmer/powerstrip_proxy.py"
    ).read_text(encoding="utf-8")
    require(
        "if len(subscribed) == 1:" in proxy_source,
        "Echte Power-Strip-DOWN-Subscription hat weiterhin Vorrang",
    )
    require(
        "if len(subscribed) > 1:" in proxy_source,
        "Mehrere echte DOWN-Subscriptions bleiben fail-closed",
    )
    require(
        'info.get("direction") != "up"' in proxy_source,
        "Fallback verwendet ausschließlich beobachtete UP-Topics",
    )
    require(
        'info.get("pid") != wanted_pid' in proxy_source,
        "Fallback bleibt strikt an dieselbe PID gebunden",
    )
    require(
        'return f"SF/GGS/{prefix}/API/DOWN/{wanted_pid}"' in proxy_source,
        "DOWN wird nur aus validiertem Prefix und derselben PID konstruiert",
    )
    require(
        '"Power-Strip-Topic-Prefix ist nicht eindeutig"' in proxy_source,
        "Mehrdeutige Power-Strip-Prefixe blockieren weiterhin",
    )

    command_source = (
        ROOT / "bridge/spiderfarmer/powerstrip_command.py"
    ).read_text(encoding="utf-8")
    require(
        'POWERSTRIP_PREFIXES = frozenset({"PS", "PS5", "PS10"})'
        in command_source,
        "Nur PS, PS5 und PS10 sind als Power-Strip-Topicfamilie zugelassen",
    )

    print("✅ Growstar 3.13.7 / SF.PS1.3a Route-Test vollständig geprüft")


if __name__ == "__main__":
    main()
