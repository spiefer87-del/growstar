#!/usr/bin/env python3
"""Regression für sichtbare VPD-Aktorübernahme und schreibgeschützte Geräte."""

from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Der Regressionstest ruft ausschließlich die interne Save-Grenze auf. Ein
# schlanker Flask-Stub hält diesen Test deshalb auch auf dem Raspberry-
# Prüfpfad ohne installierte Web-Abhängigkeiten ausführbar.
if "flask" not in sys.modules:
    flask_stub = types.ModuleType("flask")
    flask_stub.jsonify = lambda *args, **kwargs: {"args": args, **kwargs}
    flask_stub.request = types.SimpleNamespace()
    sys.modules["flask"] = flask_stub


from check_vpd_intelligent_control import runtime_for
from core.vpd import vpd_device_context
from core.vpd_control import update_vpd_control
from routes.device import VpdDeviceLockedError, _save_device


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    automatic = runtime_for(mode="AUTO")
    plan = update_vpd_control(automatic, now=1000)
    fan = vpd_device_context("fan", runtime=automatic)
    vent = vpd_device_context("vent", runtime=automatic)

    require(
        fan["participating"] is True
        and fan["managed"] is True
        and fan["locked"] is True
        and fan["status"] == "controlled"
        and fan["action"] == plan["actions"]["fan"],
        "AUTO kennzeichnet und sperrt einen übernommenen ENV-Aktor eindeutig",
    )
    require(
        vent["supported"] is False
        and vent["participating"] is False
        and vent["locked"] is False,
        "Der Umluft-Ventilator bleibt außerhalb der VPD-Aktorgruppe bedienbar",
    )

    try:
        _save_device(automatic, "fan", {"mode": "OFF"})
    except VpdDeviceLockedError as exc:
        require(
            exc.context["locked"] is True,
            "Auch ein direkter API-Schreibversuch wird bei VPD-AUTO abgewiesen",
        )
    else:
        raise AssertionError("Gesperrtes VPD-Gerät ließ sich über die API ändern")

    waiting = runtime_for(mode="AUTO", outside=False)
    update_vpd_control(waiting, now=1000)
    waiting_fan = vpd_device_context("fan", runtime=waiting)
    require(
        waiting_fan["participating"] is True
        and waiting_fan["managed"] is False
        and waiting_fan["locked"] is True
        and waiting_fan["status"] == "waiting",
        "AUTO/ENV bleibt im Sensor-Fallback gesperrt und wird als wartend markiert",
    )

    monitor = runtime_for(mode="MONITOR")
    monitor_plan = update_vpd_control(monitor, now=1000)
    monitor_fan = vpd_device_context("fan", runtime=monitor)
    require(
        monitor_fan["automatic"] is False
        and monitor_fan["locked"] is False
        and monitor_plan["next_step_label"],
        "Beobachten bleibt schreibbar und veröffentlicht dennoch den nächsten Prüfschritt",
    )

    dashboard = (ROOT / "templates" / "grow_control.html").read_text(
        encoding="utf-8"
    )
    detail = (ROOT / "templates" / "device_control.html").read_text(
        encoding="utf-8"
    )
    device_route = (ROOT / "routes" / "device.py").read_text(encoding="utf-8")
    tent_route = (ROOT / "routes" / "tents.py").read_text(encoding="utf-8")

    require(
        'id="vpd-live-card"' in dashboard
        and 'id="vpd-live-stage"' in dashboard
        and 'id="vpd-live-effect"' in dashboard
        and 'id="vpd-live-outside"' in dashboard
        and 'id="vpd-live-progress"' in dashboard
        and 'id="vpd-live-next"' in dashboard
        and 'id="vpd-action-chips"' in dashboard,
        "Das Dashboard zeigt Strategie, Wirkung, Außenluft, Stufenweg, Aktorplan und Folgeschritt",
    )
    require(
        "vpd.participating" in dashboard
        and "VPD intelligent" in dashboard
        and "vpd-device-badge" in dashboard
        and "vpdActionText(name, vpd.action)" in dashboard,
        "Übernommene Gerätekacheln tragen Live-Badge, Modus und konkreten Aktorplan",
    )
    require(
        'id="vpd-lock-warning"' in detail
        and 'id="device-config-card"' in detail
        and "control.disabled = !CAN_CONFIGURE || vpdLocked" in detail
        and "if (vpdLocked)" in detail
        and "vpd_device_locked" in detail,
        "Die Gerätedetailseite erklärt und sperrt sämtliche manuellen Regler",
    )
    require(
        'error="vpd_device_locked"' in device_route
        and "), 423" in device_route
        and '"vpd_control": vpd_device_context' in device_route
        and '"vpd_control": vpd_device_context' in tent_route,
        "Geräte- und Stations-API liefern denselben VPD-Status und HTTP 423 bei Schreibzugriff",
    )

    print("✅ Growstar 3.16.7 / VPD.UI.2 vollständig geprüft")


if __name__ == "__main__":
    main()
