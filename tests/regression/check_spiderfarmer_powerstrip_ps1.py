#!/usr/bin/env python3
"""Growstar 3.13.3 / SF.PS1 static + compiler regression."""

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.spiderfarmer.powerstrip_command import (
    compile_outlet_power_command,
    normalize_outlet,
    normalize_power,
)



def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    require(normalize_outlet("o5") == "O5", "Outlet-Namen werden kanonisch normalisiert")
    require(normalize_power(True) == 1, "EIN wird zu mOnOff=1")
    require(normalize_power("aus") == 0, "AUS wird zu mOnOff=0")

    with tempfile.TemporaryDirectory() as temp_dir:
        capture = Path(temp_dir) / "raw_frames.jsonl"
        capture.write_text(
            json.dumps({
                "direction": "down",
                "topic": "SF/GGS/PS/API/DOWN/7C2C67F2C5B8",
                "payload": {
                    "method": "getDevSta",
                    "pid": "7C2C67F2C5B8",
                    "uid": "31049",
                },
            }) + "\n",
            encoding="utf-8",
        )

        compiled = compile_outlet_power_command(
            capture,
            pid="7C2C67F2C5B8",
            outlet="O4",
            power=False,
            topic="SF/GGS/PS/API/DOWN/7C2C67F2C5B8",
        )

    payload = compiled["payload"]
    params = payload["params"]

    require(
        compiled["topic"] == "SF/GGS/PS/API/DOWN/7C2C67F2C5B8",
        "PS-DOWN-Topic bleibt exakt die aktive Subscription",
    )
    require(
        params["keyPath"] == ["outlet", "O4"],
        "Outlet-Write nutzt keyPath outlet/O4",
    )
    require(
        params["O4"] == {"modeType": 0, "mOnOff": 0},
        "Outlet-Write sendet ausschließlich manuellen EIN/AUS-Minimalblock",
    )
    require(payload["pid"] == "7C2C67F2C5B8", "PID wird in den SF-Envelope übernommen")
    require(payload["uid"] == "31049", "UID wird ausschließlich aus beobachtetem Traffic übernommen")
    require(str(payload["msgId"]).isdigit(), "msgId ist eine numerische Millisekunden-ID")

    main_py = (ROOT / "bridge/spiderfarmer/main.py").read_text(encoding="utf-8")
    proxy_py = (ROOT / "bridge/spiderfarmer/powerstrip_proxy.py").read_text(encoding="utf-8")
    route_py = (ROOT / "routes/spiderfarmer_powerstrip.py").read_text(encoding="utf-8")
    app_py = (ROOT / "app.py").read_text(encoding="utf-8")
    ui = (ROOT / "templates/spiderfarmer.html").read_text(encoding="utf-8")

    require(
        "PowerStripCommandSpiderFarmerProxy" in main_py,
        "Command-Bridge lädt die isolierte Power-Strip-Erweiterung",
    )
    require(
        'action != "set_powerstrip_outlet"' in proxy_py,
        "Bestehende Controller-Aktionen werden unverändert an den Altpfad delegiert",
    )
    require(
        'prefix") or "").upper() != "PS"' in proxy_py,
        "Power-Strip-Schreiben akzeptiert ausschließlich Prefix PS",
    )
    require(
        "/outlets/<outlet>/power" in route_py,
        "Power-Strip besitzt einen getrennten Growstar-API-Endpunkt",
    )
    require(
        "register_spiderfarmer_powerstrip_routes(app)" in app_py,
        "Power-Strip-Route wird registriert",
    )
    require(
        "X-CSRF-Token" in ui,
        "Power-Strip-UI sendet das vorhandene Growstar-CSRF-Token",
    )
    require(
        "Shelly" in ui and "vollständig getrennt" in ui,
        "UI dokumentiert die getrennte Hardwarefamilie",
    )

    print("✅ Growstar 3.13.3 / SF.PS1 vollständig geprüft")


if __name__ == "__main__":
    main()
