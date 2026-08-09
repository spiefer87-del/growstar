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


PLANT_ROLES = (
    ("production", "Produktion"),
    ("mother", "Mutterpflanze"),
    ("donor", "Spenderpflanze"),
    ("breeding", "Zucht / Selektion"),
    ("retired", "Außer Betrieb"),
)

PLANT_ROLE_LABELS = dict(PLANT_ROLES)

GENETIC_LINE_STATUSES = (
    ("active", "Aktiv"),
    ("hold", "Beobachtung"),
    ("retired", "Beendet"),
)

GENETIC_LINE_STATUS_LABELS = dict(GENETIC_LINE_STATUSES)

SEED_LOT_STATUSES = (
    ("available", "Verfügbar"),
    ("quarantine", "Quarantäne"),
    ("blocked", "Gesperrt"),
    ("depleted", "Aufgebraucht"),
    ("archived", "Archiviert"),
)

SEED_LOT_STATUS_LABELS = dict(SEED_LOT_STATUSES)

SEED_TYPES = (
    ("regular", "Regulär"),
    ("feminized", "Feminisiert"),
    ("auto", "Auto"),
    ("unknown", "Unbekannt"),
)

SEED_TYPE_LABELS = dict(SEED_TYPES)

SEED_ORIGIN_TYPES = (
    ("purchased", "Gekauft"),
    ("internal", "Eigene Produktion"),
    ("gift", "Übernommen / Geschenk"),
    ("other", "Sonstige Herkunft"),
)

SEED_ORIGIN_TYPE_LABELS = dict(SEED_ORIGIN_TYPES)

SEED_MOVEMENT_TYPES = (
    ("receipt", "Wareneingang"),
    ("propagation_issue", "Entnahme Vermehrung"),
    ("adjustment", "Bestandskorrektur"),
    ("return", "Rückbuchung"),
    ("disposal", "Ausbuchung"),
)

SEED_MOVEMENT_TYPE_LABELS = dict(SEED_MOVEMENT_TYPES)

PROPAGATION_METHODS = (
    ("seed", "Samen"),
    ("cutting", "Steckling"),
)

PROPAGATION_METHOD_LABELS = dict(PROPAGATION_METHODS)

PROPAGATION_STATUSES = (
    ("active", "Aktiv"),
    ("completed", "Abgeschlossen"),
    ("cancelled", "Storniert"),
)

PROPAGATION_STATUS_LABELS = dict(PROPAGATION_STATUSES)

PROPAGATION_UNIT_STATUS_LABELS = {
    "germinating": "Keimung läuft",
    "germinated": "Erfolgreich gekeimt",
    "rooting": "Bewurzelung läuft",
    "rooted": "Erfolgreich bewurzelt",
    "started": "Gestartet",
    "successful": "Erfolgreich",
    "failed": "Ausgefallen",
    "plant_created": "Pflanze erzeugt",
}
