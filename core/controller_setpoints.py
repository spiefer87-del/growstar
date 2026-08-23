"""Generic controller setpoints for Growstar SF.4C.

This module validates and stores desired controller values only.
It deliberately contains no hardware transport.

Persisted shape inside DEVICE_PARAMS[device]:

    "controller": {
        "level": 7,
        "oscillation": 4,
    }

The assigned physical controller decides which values are available.
"""

from __future__ import annotations

from copy import deepcopy


SCHEMAS = {
    "light": {
        "level": {
            "label": "Lichtstärke",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit": "%",
        },
    },
    "blower": {
        "level": {
            "label": "Gebläsestärke",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit": "%",
        },
    },
    "fan": {
        "level": {
            "label": "Ventilatorstufe",
            "min": 1,
            "max": 10,
            "step": 1,
            "unit": "L",
        },
        "oscillation": {
            "label": "Oszillation",
            "min": 1,
            "max": 10,
            "step": 1,
            "unit": "L",
        },
    },
}


def controller_schema(target):
    """Return the editable setpoint schema for one assigned controller target."""

    if not isinstance(target, dict):
        return {}

    family = str(target.get("family") or "").strip()
    allowed = set(target.get("capabilities") or [])
    family_schema = SCHEMAS.get(family) or {}

    return {
        name: deepcopy(spec)
        for name, spec in family_schema.items()
        if name in allowed
    }


def normalize_controller_setpoints(raw, schema):
    """Normalize values against the capabilities of the assigned controller."""

    if raw is None:
        return {}

    if not isinstance(raw, dict):
        raise TypeError("controller_setpoints muss ein JSON-Objekt sein.")

    if not isinstance(schema, dict) or not schema:
        if raw:
            raise ValueError(
                "Für dieses Gerät ist kein einstellbarer Controller zugeordnet."
            )
        return {}

    unknown = sorted(set(raw) - set(schema))
    if unknown:
        raise ValueError(
            "Nicht unterstützte Controller-Werte: " + ", ".join(unknown)
        )

    result = {}

    for name, value in raw.items():
        spec = schema[name]

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{name}: Controller-Wert muss numerisch sein."
            ) from None

        minimum = float(spec["min"])
        maximum = float(spec["max"])
        step = float(spec.get("step", 1))

        if numeric < minimum or numeric > maximum:
            raise ValueError(
                f"{name}: Wert muss zwischen {spec['min']} und "
                f"{spec['max']} liegen."
            )

        # All currently known GGS controls are integral. Keep the validation
        # generic enough for a later fractional controller.
        if step >= 1:
            if not numeric.is_integer():
                raise ValueError(
                    f"{name}: Wert muss ganzzahlig sein."
                )
            numeric = int(numeric)

        result[name] = numeric

    return result


def stored_controller_setpoints(params):
    if not isinstance(params, dict):
        return {}

    value = params.get("controller")
    return deepcopy(value) if isinstance(value, dict) else {}
