#!/usr/bin/env python3
"""Regression für rückwärtskompatible Klima-Zahlenwerte im Browserformular."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.environment_limits import validate_environment_limits


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def input_tag(template, field_id):
    match = re.search(
        rf'<input\b[^>]*\bid="{re.escape(field_id)}"[^>]*>',
        template,
    )
    if match is None:
        raise AssertionError(f"Eingabefeld {field_id} fehlt")
    return match.group(0)


def main():
    settings = (ROOT / "templates/settings.html").read_text(encoding="utf-8")
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")

    continuous_fields = (
        "TEMP_ALERT_TOL",
        "MIN_TEMP",
        "MAX_TEMP",
        "HUM_ALERT_TOL",
        "MIN_HUM",
        "MAX_HUM",
        "VPD_TARGET_DAY",
        "VPD_TOLERANCE_DAY",
        "VPD_TEMP_MIN_DAY",
        "VPD_TEMP_MAX_DAY",
        "VPD_HUM_MIN_DAY",
        "VPD_HUM_MAX_DAY",
        "VPD_TARGET_NIGHT",
        "VPD_TOLERANCE_NIGHT",
        "VPD_TEMP_MIN_NIGHT",
        "VPD_TEMP_MAX_NIGHT",
        "VPD_HUM_MIN_NIGHT",
        "VPD_HUM_MAX_NIGHT",
    )
    for field_id in continuous_fields:
        require(
            'step="any"' in input_tag(settings, field_id),
            f"{field_id} besitzt kein künstliches Browser-Schrittgitter",
        )

    for field_id in continuous_fields[6:]:
        require(
            'step="any"' in input_tag(profiles, field_id),
            f"Profilfeld {field_id} akzeptiert vorhandene Dezimalwerte",
        )

    require(
        "el(\"TEMP_ALERT_TOL\").min = 0.1" in settings
        and "el(\"TEMP_ALERT_TOL\").max = 30" in settings
        and "el(\"HUM_ALERT_TOL\").min = 0.1" in settings
        and "el(\"HUM_ALERT_TOL\").max = 100" in settings
        and "el(\"MIN_HUM\").min = 0" in settings
        and "el(\"MAX_HUM\").max = 100" in settings,
        "Sinnvolle Browser-Min-/Max-Grenzen bleiben erhalten",
    )
    require(
        'step="5"' in input_tag(settings, "RAMP_DURATION_MIN")
        and "step('RAMP_DURATION_MIN',-5)" in settings
        and "step('RAMP_DURATION_MIN',5)" in settings,
        "Rampenfeld und Plus/Minus verwenden gemeinsam fünf Minuten",
    )
    require(
        "input.checkValidity()" in settings
        and "invalid.reportValidity()" in settings,
        "Browserprüfung für leere Werte und echte Bereichsfehler bleibt aktiv",
    )

    legacy_values = {
        "MIN_TEMP": 12.0,
        "MAX_TEMP": 30.0,
        "MIN_HUM": 0.0,
        "MAX_HUM": 80.0,
        "TEMP_ALERT_TOL": 5.0,
        "HUM_ALERT_TOL": 15.1,
        "DAY_TEMP_TOL": 0.1,
        "NIGHT_TEMP_TOL": 0.1,
        "DAY_HUM_TOL": 3.0,
        "NIGHT_HUM_TOL": 3.0,
    }
    validated = validate_environment_limits(legacy_values)
    require(
        validated["temp_alert_tol"] == 5.0
        and validated["hum_alert_tol"] == 15.1
        and validated["max_hum"] == 80.0,
        "Die im Fehlerbild vorhandenen Altwerte bleiben serverseitig gültig",
    )

    fractional_limits = {
        **legacy_values,
        "MIN_TEMP": 12.3,
        "MAX_TEMP": 30.2,
        "MIN_HUM": 20.5,
        "MAX_HUM": 80.5,
    }
    validated_fractional = validate_environment_limits(fractional_limits)
    require(
        validated_fractional["min_temp"] == 12.3
        and validated_fractional["max_hum"] == 80.5,
        "Auch bestehende Dezimalgrenzen bleiben rückwärtskompatibel",
    )

    try:
        validate_environment_limits({**legacy_values, "MIN_HUM": 90.0})
    except ValueError:
        pass
    else:
        raise AssertionError("Unsicherer Feuchtebereich wurde akzeptiert")
    require(
        True,
        "Serverseitige Sicherheitsinvarianten blockieren weiterhin echte Fehler",
    )

    print("✅ Growstar 3.15.12 / SETTINGS.VALIDATION.1 vollständig geprüft")


if __name__ == "__main__":
    main()
