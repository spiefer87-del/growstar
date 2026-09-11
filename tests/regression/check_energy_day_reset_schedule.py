#!/usr/bin/env python3
"""Regression für den konfigurierten Energie-Abrechnungstag."""

import datetime
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from core.runtime import create_isolated_runtime
from services import energy


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def local_timestamp(year, month, day, hour, minute):
    return datetime.datetime(year, month, day, hour, minute).astimezone().timestamp()


def main():
    before_midnight = local_timestamp(2026, 9, 10, 23, 59)
    after_midnight = local_timestamp(2026, 9, 11, 0, 4)
    scheduled_reset = local_timestamp(2026, 9, 11, 5, 30)

    context_before = energy.energy_day_context(now=before_midnight, reset_min=330)
    context_after = energy.energy_day_context(now=after_midnight, reset_min=330)
    context_reset = energy.energy_day_context(now=scheduled_reset, reset_min=330)
    require(
        context_before["day"] == "2026-09-10"
        and context_after["day"] == "2026-09-10",
        "Mitternacht wechselt den Energie-Abrechnungstag bei 05:30 nicht",
    )
    require(
        context_reset["day"] == "2026-09-11"
        and datetime.datetime.fromtimestamp(
            context_after["next_reset_at"]
        ).strftime("%H:%M") == "05:30",
        "Der neue Abrechnungstag beginnt exakt zur konfigurierten Uhrzeit",
    )

    saved = []
    runtime = create_isolated_runtime(
        "tent_reset_test",
        config_data={
            "ENERGY_DAY_RESET_MIN": 330,
            "ENERGY_DAY_OFFSET": {},
            "ENERGY_RESET": {},
        },
        save_config_callback=lambda cfg: saved.append(dict(cfg)),
    )
    original_default_runtime = energy.get_default_runtime
    energy.get_default_runtime = lambda: runtime
    try:
        first, changed_first = energy._apply_runtime_offsets(
            runtime, "light", 10.0, today=context_before["day"]
        )
        after, changed_after = energy._apply_runtime_offsets(
            runtime, "light", 10.1, today=context_after["day"]
        )
        at_reset, changed_reset = energy._apply_runtime_offsets(
            runtime, "light", 10.2, today=context_reset["day"]
        )
        require(
            changed_first is True
            and changed_after is False
            and after["today"] == 0.1,
            "Der Energieoffset bleibt über 00:00 hinweg erhalten",
        )
        require(
            changed_reset is True and at_reset["today"] == 0.0,
            "Der Energieoffset wechselt erst an der 05:30-Grenze",
        )

        runtime.config["ENERGY_DAY_OFFSET"]["light"] = {
            "day": "2026-09-11",
            "offset": 10.15,
        }
        migrated, migrated_changed = energy._apply_runtime_offsets(
            runtime,
            "light",
            10.2,
            today=context_after["day"],
            now=after_midnight,
        )
        require(
            migrated_changed is True
            and migrated["today"] == 0.05
            and runtime.config["ENERGY_DAY_OFFSET"]["light"]["day"] == "2026-09-10",
            "Alter Mitternachts-Offset wird übernommen statt erneut zurückgesetzt",
        )

        runtime.config["ENERGY_LAST_DAY_RESET"] = "2026-09-10"
        require(
            energy.energy_day_reset_due(now=after_midnight) is False
            and energy.energy_day_reset_due(now=scheduled_reset) is True,
            "Scheduler wird anhand des Abrechnungstags statt der Mitternacht fällig",
        )

        audit = energy.record_energy_day_reset(
            source="manual",
            scope="tent_reset_test/light",
            now=scheduled_reset,
        )
        settings = energy.get_energy_settings(now=scheduled_reset)
        require(
            audit["source"] == "manual"
            and audit["scope"] == "tent_reset_test/light"
            and settings["last_day_reset_at"] == int(scheduled_reset)
            and runtime.config["ENERGY_LAST_DAY_RESET"] == "2026-09-10"
            and energy.energy_day_reset_due(now=scheduled_reset) is True
            and saved,
            "Teilresets werden protokolliert, unterdrücken aber den globalen Zeitplan nicht",
        )

        window = energy._history_window("today", after_midnight)
        require(
            window["start"] == context_after["started_at"],
            "Heute-Diagramm beginnt ebenfalls an der konfigurierten Reset-Grenze",
        )
    finally:
        energy.get_default_runtime = original_default_runtime

    thread_source = (ROOT / "threads/shelly.py").read_text(encoding="utf-8")
    route_source = (ROOT / "routes/energy.py").read_text(encoding="utf-8")
    settings_template = (ROOT / "templates/energie_settings.html").read_text(
        encoding="utf-8"
    )
    overview_template = (ROOT / "templates/energie.html").read_text(encoding="utf-8")
    require(
        "energy_day_reset_due(now=now)" in thread_source
        and "now_min >= reset_min" not in thread_source,
        "Hintergrunddienst verwendet ausschließlich die gemeinsame Abrechnungstag-Logik",
    )
    require(
        route_source.count('record_energy_day_reset(source="manual"') >= 1
        and 'source="manual"' in route_source,
        "Manuelle API-Resets schreiben den Reset-Nachweis",
    )
    for element_id in (
        "lastResetValue", "lastResetMeta", "energyDayValue", "nextResetValue"
    ):
        require(
            f'id="{element_id}"' in settings_template,
            f"Energie-Einstellungen zeigen {element_id}",
        )
    require(
        'id="resetBadge"' in overview_template
        and "current_day_started_at" in overview_template,
        "Energieübersicht zeigt Reset-Uhrzeit und Beginn des Abrechnungstags",
    )

    print("✅ Energie-Tagesreset 05:30 vollständig geprüft")


if __name__ == "__main__":
    main()
