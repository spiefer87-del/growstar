"""Validierung der stationsbezogenen Klima- und Alarmgrenzen."""

from __future__ import annotations

import math


def _finite_number(cfg, key):
    try:
        value = float(cfg[key])
    except KeyError as exc:
        raise ValueError(f"{key} fehlt") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss numerisch sein") from exc

    if not math.isfinite(value):
        raise ValueError(f"{key} muss endlich sein")

    return value


def validate_environment_limits(cfg):
    """Validiert nur die grundlegenden Sicherheitsinvarianten.

    Sollwerte werden absichtlich nicht gegen MIN/MAX verriegelt, weil Profile
    bestehende Sollwerte laden können. Die Web-UI begrenzt neue Sollwerte
    dennoch auf den aktuell gewählten Bereich.
    """

    min_temp = _finite_number(cfg, "MIN_TEMP")
    max_temp = _finite_number(cfg, "MAX_TEMP")
    min_hum = _finite_number(cfg, "MIN_HUM")
    max_hum = _finite_number(cfg, "MAX_HUM")

    temp_alert_tol = _finite_number(cfg, "TEMP_ALERT_TOL")
    hum_alert_tol = _finite_number(cfg, "HUM_ALERT_TOL")

    if min_temp >= max_temp:
        raise ValueError("MIN_TEMP muss kleiner als MAX_TEMP sein")

    if not 0.0 <= min_hum < max_hum <= 100.0:
        raise ValueError(
            "Luftfeuchte-Grenzen müssen 0 <= MIN_HUM < MAX_HUM <= 100 erfüllen"
        )

    if temp_alert_tol <= 0:
        raise ValueError("TEMP_ALERT_TOL muss größer als 0 sein")

    if hum_alert_tol <= 0:
        raise ValueError("HUM_ALERT_TOL muss größer als 0 sein")

    for key in (
        "DAY_TEMP_TOL",
        "NIGHT_TEMP_TOL",
        "DAY_HUM_TOL",
        "NIGHT_HUM_TOL",
    ):
        if _finite_number(cfg, key) < 0:
            raise ValueError(f"{key} darf nicht negativ sein")

    return {
        "min_temp": min_temp,
        "max_temp": max_temp,
        "min_hum": min_hum,
        "max_hum": max_hum,
        "temp_alert_tol": temp_alert_tol,
        "hum_alert_tol": hum_alert_tol,
    }
