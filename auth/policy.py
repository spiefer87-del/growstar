from dataclasses import dataclass


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class PermissionRequirement:
    permissions: tuple[str, ...]
    mode: str = "all"

    def allows(self, user_permissions):
        available = set(user_permissions or [])
        required = set(self.permissions)

        if self.mode == "any":
            return bool(required.intersection(available))

        return required.issubset(available)


def require(*permissions, mode="all"):
    return PermissionRequirement(tuple(permissions), mode=mode)


def _normalize_path(path):
    if not path:
        return "/"
    if path != "/":
        path = path.rstrip("/")
    return path


def _matches_prefix(path, prefix):
    return path == prefix or path.startswith(prefix + "/")


# ---------------------------------------------------------------------------
# Leserechte für bestehende Growstar-Seiten
# ---------------------------------------------------------------------------

READ_EXACT = {
    "/": require("dashboard.view"),
    "/grow-control": require("grow.view"),
    "/grow-control/watchdog": require("hardware.view"),
    "/pflanzenmanagement": require("plants.view"),

    # Grow / Live-Daten
    "/temperature": require("grow.view"),
    "/humidity": require("grow.view"),
    "/vpd": require("grow.view"),
    "/ph": require("grow.view"),
    "/ec": require("grow.view"),
    "/water-temp": require("grow.view"),
    "/light-level": require("grow.view"),
    "/diagrams": require("grow.view"),
    "/energie": require("grow.view"),
    "/licht": require("grow.view"),
    "/heizung": require("grow.view"),
    "/abluft": require("grow.view"),
    "/ventilator": require("grow.view"),
    "/bewaesserung": require("grow.view"),
    "/luftbefeuchter": require("grow.view"),
    "/luftentfeuchter": require("grow.view"),
    "/licht2": require("grow.view"),
    "/ventilator2": require("grow.view"),

    # Konfiguration
    "/settings": require("settings.view"),
    "/system": require("settings.view"),
    "/design": require("settings.view"),
    "/energie/settings": require("settings.view"),

    # Hardware / Sensorik
    "/sensoren": require("hardware.view"),
    "/connections": require("hardware.view"),
    "/watchdog": require("hardware.view"),
    "/devices": require("hardware.view"),

    # Betriebsdaten
    "/pflanzendaten": require("plants.view"),
    "/tagebuch": require("diary.view"),
}


READ_PREFIX = (
    # Alle Unterseiten des neuen Grow-Control-Hubs bleiben Grow-spezifisch.
    ("/grow-control", require("grow.view")),
    ("/devices", require("hardware.view")),
    ("/api/state", require("grow.view")),
    ("/api/history", require("grow.view")),
    ("/api/diagrams", require("grow.view")),
    ("/api/energy", require("grow.view")),
    ("/api/plants", require("plants.view")),
    ("/api/diary", require("diary.view")),
    ("/api/hardware", require("hardware.view")),
    ("/api/device", require("hardware.view")),
    ("/api/devices", require("hardware.view")),
    ("/api/sensor", require("hardware.view")),
    ("/api/sensors", require("hardware.view")),
    ("/api/blu", require("hardware.view")),
    ("/api/watchdog", require("hardware.view")),

    # Diese Daten werden auch für die normale Grow-Anzeige benötigt.
    ("/api/config", require("grow.view", "settings.view", mode="any")),
    ("/api/profile", require("grow.view", "settings.view", mode="any")),
)


# ---------------------------------------------------------------------------
# Schreibrechte
# ---------------------------------------------------------------------------
#
# Die Reihenfolge ist wichtig. Spezifische Aktionen werden vor generischen
# Präfixen geprüft. Dadurch unterscheiden wir bewusst zwischen:
#   grow.control       -> laufenden Grow bedienen
#   grow.configure     -> Regelparameter / Gerätekonfiguration ändern
#   hardware.control   -> Hardware-Aktionen ausführen (Scan/Refresh/Read)
#   hardware.configure -> Pairing, Zuordnung und Hardware-Konfiguration
# ---------------------------------------------------------------------------

WRITE_EXACT = {
    # Grow-Konfiguration / Datenpflege
    "/api/config": require("grow.configure", "settings.manage", mode="any"),
    "/api/diagrams/import": require("grow.configure"),
    "/api/reset_history": require("settings.manage"),

    # Energiezähler zurücksetzen ist administrativer als reine Bedienung.
    "/api/energy/reset_today_all": require("grow.configure"),
    "/api/energy/reset_total_all": require("grow.configure"),

    # Hardware-Aktionen ohne dauerhafte Konfigurationsänderung
    "/api/hardware/scan": require("hardware.control"),
    "/api/watchdog/log/clear": require("hardware.control"),
}


WRITE_PREFIX = (
    # Pflanzen / Tagebuch
    ("/api/plants", require("plants.edit")),
    ("/pflanzendaten", require("plants.edit")),
    ("/api/diary", require("diary.edit")),
    ("/tagebuch", require("diary.edit")),

    # Grow-Regelung
    # Moduswechsel ist Bedienung; Geräteeinstellungen selbst sind Konfiguration.
    ("/api/device/mode", require("grow.control")),
    ("/api/device", require("grow.configure")),
    ("/api/profile", require("grow.configure", "settings.manage", mode="any")),
    ("/settings", require("grow.configure", "settings.manage", mode="any")),

    # Energiezähler einzelner Geräte zurücksetzen
    ("/api/energy/reset_today", require("grow.configure")),
    ("/api/energy/reset_total", require("grow.configure")),

    # Hardware-Inventar / Sensorik konfigurieren
    ("/api/sensors", require("hardware.configure")),
    ("/api/sensor", require("hardware.configure")),
    ("/api/blu", require("hardware.configure")),
    ("/connections", require("hardware.configure")),
    ("/sensoren", require("hardware.configure")),
    ("/devices", require("hardware.configure")),

    # System-/Energieeinstellungen
    ("/energie/settings", require("settings.manage")),
    ("/api/energy/settings", require("settings.manage")),
    ("/system", require("settings.manage")),
    ("/design", require("settings.manage")),
)


def _hardware_write_requirement(path):
    """Feingranulare Rechte für die vorhandenen Hardware-Endpunkte."""

    if not _matches_prefix(path, "/api/hardware") and not _matches_prefix(
        path, "/api/watchdog"
    ):
        return None

    # Aktionen, die Hardware nur anstoßen/abfragen, aber keine dauerhafte
    # Zuordnung verändern.
    control_suffixes = (
        "/refresh",
        "/read-values",
        "/ble/scan",
        "/log/clear",
    )
    if path == "/api/hardware/scan" or path.endswith(control_suffixes):
        return require("hardware.control")

    # Bluetooth ein/aus, Pairing, Registrierung, Sensor-Setup und Unpairing
    # verändern die Hardware-Konfiguration dauerhaft.
    configure_markers = (
        "/bluetooth/enable",
        "/bluetooth/disable",
        "/pair",
        "/unpair",
        "/setup-sensors",
        "/register-discovered",
        "/add-discovered",
    )
    if any(marker in path for marker in configure_markers):
        return require("hardware.configure")

    # Sonstige schreibende Hardware-Endpunkte bleiben fail-closed auf
    # hardware.configure.
    return require("hardware.configure")


# ---------------------------------------------------------------------------
# Reservierte Management-Pfade für kommende Module
# ---------------------------------------------------------------------------

MANAGEMENT_PREFIXES = {
    "/pflanzenmanagement": {
        "read": require("plants.view"),
        "post": require("plants.edit"),
        "write": require("plants.edit"),
    },
    "/api/plant-management": {
        "read": require("plants.view"),
        "post": require("plants.edit"),
        "write": require("plants.edit"),
    },
    "/inventory": {
        "read": require("inventory.view"),
        "post": require("inventory.create"),
        "write": require("inventory.edit"),
    },
    "/api/inventory": {
        "read": require("inventory.view"),
        "post": require("inventory.create"),
        "write": require("inventory.edit"),
    },
    "/receiving": {
        "read": require("receiving.view"),
        "post": require("receiving.create"),
        "write": require("receiving.edit"),
    },
    "/api/receiving": {
        "read": require("receiving.view"),
        "post": require("receiving.create"),
        "write": require("receiving.edit"),
    },
    "/suppliers": {
        "read": require("suppliers.view"),
        "post": require("suppliers.edit"),
        "write": require("suppliers.edit"),
    },
    "/api/suppliers": {
        "read": require("suppliers.view"),
        "post": require("suppliers.edit"),
        "write": require("suppliers.edit"),
    },
}


def _management_requirement(path, method):

    # Das neue Betriebsjournal liegt bewusst im Pflanzenmanagement,
    # behält aber seine eigenständigen diary.* Berechtigungen.
    if _matches_prefix(path, "/pflanzenmanagement/tagebuch"):
        if method in SAFE_METHODS:
            return require("diary.view")
        return require("diary.edit")

    for prefix, rules in MANAGEMENT_PREFIXES.items():
        if not _matches_prefix(path, prefix):
            continue

        if prefix in {"/inventory", "/api/inventory"} and "/adjust" in path:
            return require("inventory.adjust")

        if method in SAFE_METHODS:
            return rules["read"]
        if method == "POST":
            return rules["post"]
        return rules["write"]

    return None




def _grow_control_read_requirement(path):
    """Feinere Rechte innerhalb des Grow-Control-Moduls."""

    if path == "/grow-control/sensors":
        return require("hardware.view")

    if path == "/grow-control/connections":
        return require("hardware.view")

    if path == "/grow-control/setup":
        return require("settings.view", "grow.view", mode="any")

    if not _matches_prefix(path, "/grow-control/tents"):
        return None

    if path.endswith("/settings"):
        return require("settings.view")

    if path.endswith("/design"):
        return require("settings.view")

    if path.endswith("/sensors"):
        return require("hardware.view")

    return require("grow.view")


def _tent_api_read_requirement(path):
    if not _matches_prefix(path, "/api/tents"):
        return None

    if path.endswith("/live-preflight"):
        return require("grow.view", "hardware.view")

    if "/sensors" in path or path.endswith("/hardware"):
        return require("hardware.view")

    if path.endswith("/config") or "/profile/" in path:
        return require("grow.view", "settings.view", mode="any")

    return require("grow.view")


def _tent_api_write_requirement(path):
    if not _matches_prefix(path, "/api/tents"):
        return None

    # LIVE opens/closes real hardware actuation and therefore requires BOTH
    # runtime Grow control and explicit hardware control rights.
    if path.endswith("/live"):
        return require("grow.control", "hardware.control")

    if "/sensors" in path or path.endswith("/hardware"):
        return require("hardware.configure")

    if "/devices/" in path:
        return require("grow.configure")

    if path.endswith("/config") or "/profile/" in path:
        return require("grow.configure", "settings.manage", mode="any")

    if path.endswith("/history/reset"):
        return require("settings.manage")

    # Unbekannte stationsbezogene Schreibzugriffe sind Konfiguration, nicht
    # bloße Laufzeitbedienung. Das ist absichtlich fail-closed.
    return require("grow.configure")


def permission_requirement(path, method):
    """
    Liefert die für einen Request benötigte Berechtigung.

    Auth-/Admin-Routen werden bewusst nicht hier geregelt:
    - /login und /logout werden durch Auth selbst behandelt.
    - /admin nutzt die feineren Decorators aus routes/admin.py.
    """

    path = _normalize_path(path)
    method = (method or "GET").upper()

    if path in {"/login", "/logout"}:
        return None

    if _matches_prefix(path, "/static"):
        return None

    if _matches_prefix(path, "/admin"):
        return None

    management = _management_requirement(path, method)
    if management:
        return management

    if method in SAFE_METHODS:
        exact = READ_EXACT.get(path)
        if exact:
            return exact

        grow_control = _grow_control_read_requirement(path)
        if grow_control:
            return grow_control

        tent_api = _tent_api_read_requirement(path)
        if tent_api:
            return tent_api

        for prefix, requirement in READ_PREFIX:
            if _matches_prefix(path, prefix):
                return requirement

        # Unbekannte API-Lesezugriffe benötigen mindestens Grow-Leserecht.
        if _matches_prefix(path, "/api"):
            return require("grow.view")

        # Unklassifizierte HTML-Seiten bleiben nur für Dashboard-Benutzer
        # lesbar. Sensible neue Module sollten explizit ergänzt werden.
        return require("dashboard.view")

    exact = WRITE_EXACT.get(path)
    if exact:
        return exact

    tent_api = _tent_api_write_requirement(path)
    if tent_api:
        return tent_api

    hardware = _hardware_write_requirement(path)
    if hardware:
        return hardware

    for prefix, requirement in WRITE_PREFIX:
        if _matches_prefix(path, prefix):
            return requirement

    # Fail-closed für unbekannte Schreibzugriffe.
    return require("grow.control")
