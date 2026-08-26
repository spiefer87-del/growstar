#!/usr/bin/env python3
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
    require(_is_power_strip({"prefix":"PS","devices":[]}),
            "Kanonischer Prefix PS wird erkannt")

    observed = {
        "prefix": None,
        "devices": [{
            "kind": "outlet",
            "channels": [{"channel":"O1"},{"channel":"O5"}],
        }],
    }
    require(_is_power_strip(observed),
            "Outlet-Inventar dient als sicherer Route-Fallback")

    ggs = {
        "prefix":"CB",
        "devices":[{"kind":"fan","channels":[]}],
    }
    require(not _is_power_strip(ggs),
            "GGS-Controller bleibt ausgeschlossen")

    malformed = {
        "prefix":None,
        "devices":[{
            "kind":"outlet",
            "channels":[{"channel":"relay1"},{"channel":"O99"}],
        }],
    }
    require(not _is_power_strip(malformed),
            "Ungültiges Outlet-Inventar öffnet Route nicht")

    channel = _find_outlet({
        "devices":[{
            "kind":"outlet",
            "channels":[{"channel":"O1"},{"channel":"O5"}],
        }],
    }, "o5")
    require(channel and channel["channel"] == "O5",
            "O5 wird exakt gefunden")

    proxy = (ROOT/"bridge/spiderfarmer/powerstrip_proxy.py").read_text(encoding="utf-8")
    require('str(info.get("prefix") or "").upper() != "PS"' in proxy,
            "Bridge verlangt weiterhin echtes PS-DOWN-Topic")
    require("len(matches) != 1" in proxy,
            "Bridge verlangt weiterhin eindeutiges PS-DOWN-Topic")

    print("✅ Growstar 3.13.5 / SF.PS1.2 vollständig geprüft")


if __name__ == "__main__":
    main()
