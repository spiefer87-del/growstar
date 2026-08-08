STAGES = (
    ("germination", "Keimung", "#f59e0b"),
    ("seedling", "Sämling", "#84cc16"),
    ("vegetative", "Vegetation", "#22c55e"),
    ("flowering", "Blüte", "#a855f7"),
    ("harvest", "Ernte", "#f97316"),
    ("finished", "Abgeschlossen", "#64748b"),
)

STAGE_LABELS = {code: label for code, label, _ in STAGES}
STAGE_COLORS = {code: color for code, _, color in STAGES}

PLANT_STATUSES = (
    ("active", "Aktiv"),
    ("finished", "Abgeschlossen"),
    ("archived", "Archiviert"),
    ("lost", "Ausgeschieden"),
)

PLANT_STATUS_LABELS = dict(PLANT_STATUSES)

BATCH_STATUSES = (
    ("active", "Aktiv"),
    ("finished", "Abgeschlossen"),
    ("archived", "Archiviert"),
)

BATCH_STATUS_LABELS = dict(BATCH_STATUSES)
