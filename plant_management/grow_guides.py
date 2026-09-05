"""Fachliche, schreibgeschützte Anbauhilfen für Growstar.

Die Empfehlungen sind bewusst von der Regelung getrennt. Dieses Modul ordnet
aktive Pflanzen einer VPD-Leitfadenzeile zu, ändert aber niemals Stations- oder
Profilwerte. So bleibt die Hilfestellung nachvollziehbar und kann später um
weitere Leitfäden ergänzt werden.
"""

from __future__ import annotations

from copy import deepcopy

from core.helpers import calculate_target_vpd


VPD_GUIDE_PHASES = (
    {
        "id": "germination",
        "label": "Keimung / Stecklinge",
        "period": "bis zur sicheren Bewurzelung",
        "day": {"target": 0.60, "min": 0.45, "max": 0.75, "temp": 22.0, "hum": 75.0},
        "night": {"target": 0.50, "min": 0.40, "max": 0.60, "temp": 20.0, "hum": 80.0},
        "note": "Sehr sanfte Transpiration; Austrocknung junger Wurzeln vermeiden.",
    },
    {
        "id": "seedling",
        "label": "Sämling",
        "period": "erste echte Blattpaare",
        "day": {"target": 0.75, "min": 0.65, "max": 0.85, "temp": 23.0, "hum": 73.0},
        "night": {"target": 0.60, "min": 0.50, "max": 0.70, "temp": 20.0, "hum": 75.0},
        "note": "Langsam an stärkere Transpiration gewöhnen.",
    },
    {
        "id": "vegetative_early",
        "label": "Frühe Vegetation",
        "period": "erste Hälfte der Vegetation",
        "day": {"target": 0.90, "min": 0.80, "max": 1.00, "temp": 24.0, "hum": 70.0},
        "night": {"target": 0.75, "min": 0.65, "max": 0.85, "temp": 21.0, "hum": 70.0},
        "note": "Aktives Blatt- und Wurzelwachstum bei moderatem Dampfdruckdefizit.",
    },
    {
        "id": "vegetative_late",
        "label": "Späte Vegetation",
        "period": "zweite Hälfte bis Blütewechsel",
        "day": {"target": 1.10, "min": 1.00, "max": 1.20, "temp": 25.0, "hum": 65.0},
        "night": {"target": 0.90, "min": 0.80, "max": 1.00, "temp": 22.0, "hum": 65.0},
        "note": "Kräftige Transpiration vor dem Übergang in die Blüte.",
    },
    {
        "id": "flowering_early",
        "label": "Frühe Blüte",
        "period": "0–35 % der Sorten-Blütezeit",
        "day": {"target": 1.20, "min": 1.10, "max": 1.30, "temp": 25.0, "hum": 62.0},
        "night": {"target": 1.00, "min": 0.90, "max": 1.10, "temp": 22.0, "hum": 62.0},
        "note": "Stretch und Blütenansatz; Feuchtespitzen in der Dunkelphase vermeiden.",
    },
    {
        "id": "flowering_mid",
        "label": "Mittlere Blüte",
        "period": "35–75 % der Sorten-Blütezeit",
        "day": {"target": 1.35, "min": 1.25, "max": 1.45, "temp": 25.0, "hum": 57.0},
        "night": {"target": 1.10, "min": 1.00, "max": 1.20, "temp": 21.0, "hum": 56.0},
        "note": "Dichtere Blüten: Luftaustausch und Feuchteentwicklung besonders beobachten.",
    },
    {
        "id": "flowering_late",
        "label": "Späte Blüte / Reifung",
        "period": "75–100 % der Sorten-Blütezeit",
        "day": {"target": 1.45, "min": 1.35, "max": 1.55, "temp": 24.0, "hum": 50.0},
        "night": {"target": 1.25, "min": 1.15, "max": 1.35, "temp": 20.0, "hum": 45.0},
        "note": "Schimmelrisiko begrenzen, ohne die Pflanze unnötig stark auszutrocknen.",
    },
)


def _progress(stage_days, expected_days, *, fallback_split):
    try:
        elapsed = max(0.0, float(stage_days))
    except (TypeError, ValueError):
        elapsed = 0.0

    try:
        planned = float(expected_days)
    except (TypeError, ValueError):
        planned = 0.0

    if planned > 0.0:
        return elapsed / planned, "Sorten-Planwert"

    return elapsed / float(fallback_split), "Phasentage ohne Planwert"


def vpd_guide_phase_for_plant(plant):
    """Ordnet eine Pflanze nachvollziehbar einer Leitfadenphase zu."""

    stage = str((plant or {}).get("current_stage") or "").strip().lower()
    if stage == "germination":
        return "germination", "Aktuelle Pflanzenphase: Keimung"
    if stage == "seedling":
        return "seedling", "Aktuelle Pflanzenphase: Sämling"

    if stage == "vegetative":
        progress, source = _progress(
            plant.get("stage_days"),
            plant.get("expected_veg_days"),
            fallback_split=42.0,
        )
        phase_id = "vegetative_early" if progress < 0.5 else "vegetative_late"
        return phase_id, f"Vegetationsfortschritt {progress * 100:.0f} % · {source}"

    if stage == "flowering":
        progress, source = _progress(
            plant.get("stage_days"),
            plant.get("expected_flower_days"),
            fallback_split=56.0,
        )
        if progress < 0.35:
            phase_id = "flowering_early"
        elif progress < 0.75:
            phase_id = "flowering_mid"
        else:
            phase_id = "flowering_late"
        return phase_id, f"Blütefortschritt {progress * 100:.0f} % · {source}"

    return None, "Für diese Pflanzenphase ist noch kein VPD-Leitwert definiert"


def build_vpd_guide(active_plants):
    """Ergänzt Leitfadenzeilen um Beispiele und aktive Pflanzenbezüge."""

    phases = deepcopy(list(VPD_GUIDE_PHASES))
    by_id = {phase["id"]: phase for phase in phases}
    for phase in phases:
        phase["active_plants"] = []
        phase["active_count"] = 0
        for period in ("day", "night"):
            example = phase[period]
            example["calculated"] = calculate_target_vpd(
                example["temp"],
                example["hum"],
            )

    unmapped = []
    for plant in active_plants or []:
        phase_id, reason = vpd_guide_phase_for_plant(plant)
        summary = {
            "id": plant.get("id"),
            "code": plant.get("code"),
            "name": plant.get("display_name") or plant.get("code") or "Pflanze",
            "stage_label": plant.get("stage_label") or plant.get("current_stage"),
            "reason": reason,
        }
        if phase_id in by_id:
            by_id[phase_id]["active_plants"].append(summary)
            by_id[phase_id]["active_count"] += 1
        else:
            unmapped.append(summary)

    active_phases = [phase for phase in phases if phase["active_count"]]
    if active_phases:
        initial = max(
            active_phases,
            key=lambda phase: (phase["active_count"], phases.index(phase)),
        )["id"]
    else:
        initial = "vegetative_late"

    return {
        "phases": phases,
        "initial_phase_id": initial,
        "active_plant_count": sum(phase["active_count"] for phase in phases),
        "unmapped_plants": unmapped,
        "disclaimer": (
            "Growstar zeigt Luft-VPD aus Lufttemperatur und relativer Feuchte. "
            "Ein späterer Blatt-VPD benötigt eine gemessene Blatttemperatur "
            "oder einen bewusst gesetzten Blatt-Offset."
        ),
    }


__all__ = (
    "VPD_GUIDE_PHASES",
    "build_vpd_guide",
    "vpd_guide_phase_for_plant",
)
