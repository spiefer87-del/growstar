#!/usr/bin/env python3
"""Regression für das kompakte Dashboard und den separaten VPD-Regellog."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
for path in (ROOT, REGRESSION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


from check_vpd_intelligent_control import runtime_for
from core.vpd_control import _set_stage, update_vpd_control


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    engine = {}
    for index in range(35):
        engine["fan_level"] = index
        engine["temp_target"] = 22.0 + index / 10.0
        _set_stage(
            engine,
            direction="raise",
            stage="exhaust",
            now=1000 + index,
            vpd=0.8 + index / 1000.0,
            temp=24.0,
            note=f"Prüfschritt {index}",
        )

    require(
        len(engine["events"]) == 30
        and engine["events"][0]["note"] == "Prüfschritt 5"
        and engine["events"][-1]["fan_level"] == 34,
        "Der interne Entscheidungsverlauf ist auf die letzten 30 Übergänge begrenzt",
    )

    runtime = runtime_for(mode="MONITOR")
    public = update_vpd_control(runtime, now=2000)
    events = public.get("events") or []
    require(
        len(events) == 1
        and events[0]["stage"] == public["stage"]
        and events[0]["note"] == public["reason"]
        and isinstance(events[0].get("at"), float),
        "Der öffentliche VPD-Status veröffentlicht nur den begrenzten Entscheidungsverlauf",
    )
    with runtime.state_lock:
        runtime.state.current_profile = "NACHT"
        runtime.state.live_state["profile"] = "NACHT"
    night = update_vpd_control(runtime, now=2001)
    require(
        len(night.get("events") or []) >= 2
        and night["events"][0] == events[0],
        "Ein Tag-/Nachtwechsel startet die Strategie neu, behält aber den kurzen Regellog",
    )
    with runtime.state_lock:
        runtime.state.live_state["outside_temp"] = None
    waiting = update_vpd_control(runtime, now=2002)
    require(
        waiting["stage"] == "waiting_sensors"
        and waiting.get("events") == night.get("events"),
        "Ein vorübergehender Sensor-Fallback löscht die letzten Regelentscheidungen nicht",
    )

    dashboard = (ROOT / "templates" / "grow_control.html").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "templates" / "settings.html").read_text(
        encoding="utf-8"
    )
    vpd_log = (ROOT / "templates" / "vpd_control_log.html").read_text(
        encoding="utf-8"
    )
    route = (ROOT / "routes" / "dashboard.py").read_text(encoding="utf-8")

    require(
        '<section id="vpd-live-card"' not in dashboard
        and "renderVpdLiveCard" not in dashboard
        and 'id="vpd-card-slot"' in dashboard
        and 'id="vpd-log-link"' in dashboard
        and 'cardSlot.classList.toggle("has-vpd-log",showLog)' in dashboard,
        "Die große Diagnosekarte ist entfernt und der kleine Regellog-Zugang folgt dem VPD-Modus",
    )
    require(
        'data-settings-tab="classic"' in settings
        and 'data-settings-tab="vpd"' in settings
        and 'data-settings-panel="classic"' in settings
        and 'data-settings-panel="vpd"' in settings
        and 'id="settings-vpd-log-link"' in settings
        and 'function selectSettingsSection' in settings
        and 'el("VPD_CONTROL_MODE").value === "OFF" ? "classic" : "vpd"' in settings,
        "Die Klimaseite trennt klassische und intelligente Regelwerte und öffnet passend zur aktiven Betriebsart",
    )
    require(
        'id="vpd-event-list"' in vpd_log
        and "renderEvents(control.events)" in vpd_log
        and 'fetch(STATE_URL,{cache:"no-store"})' in vpd_log
        and "textContent" in vpd_log
        and "innerHTML" not in vpd_log,
        "Der Live-Regellog aktualisiert Diagnosen sicher aus der vorhandenen Stations-State-API",
    )
    require(
        '@app.route("/grow-control/tents/<tent_id>/vpd-control")' in route
        and '"vpd_control_log.html"' in route,
        "Der stationsbezogene Regellog besitzt eine eigene Route",
    )
    for name, source in (("Klimaseite", settings), ("VPD-Regellog", vpd_log)):
        ids = re.findall(r'\bid="([^"]+)"', source)
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        require(
            not duplicates,
            f"{name} besitzt keine doppelten HTML-IDs",
        )

    print("✅ Growstar 3.16.9 / VPD.UI.3 UI-Aufräumung vollständig geprüft")


if __name__ == "__main__":
    main()
