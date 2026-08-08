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
    "/energie/settings": require("settings.manage"),

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
    ("/devices", require("hardware.view")),
    ("/api/state", require("grow.view")),
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
    # /api/config wird auch vom Dashboard für Reihenfolge/Sichtbarkeit benutzt.
    # Grow-Leser dürfen diese Anzeige-Konfiguration lesen; Änderungen bleiben
    # separat geschützt.
    ("/api/config", require("grow.view", "settings.view", mode="any")),
    ("/api/profile", require("grow.view", "settings.view", mode="any")),
)


# ---------------------------------------------------------------------------
# Schreibrechte. Spezifische Regeln stehen vor generischen Regeln.
# ---------------------------------------------------------------------------

WRITE_PREFIX = (
    # Pflanzen / Tagebuch
    ("/api/plants", require("plants.edit")),
    ("/pflanzendaten", require("plants.edit")),
    ("/api/diary", require("diary.edit")),
    ("/tagebuch", require("diary.edit")),

    # Grow-Regelung konfigurieren
    ("/api/config", require("grow.configure", "settings.manage", mode="any")),
    ("/api/profile", require("grow.configure", "settings.manage", mode="any")),
    ("/settings", require("grow.configure", "settings.manage", mode="any")),

    # Hardware-Inventar / Sensorik konfigurieren
    ("/api/hardware", require("hardware.configure")),
    ("/api/device", require("hardware.configure")),
    ("/api/devices", require("hardware.configure")),
    ("/api/sensor", require("hardware.configure")),
    ("/api/sensors", require("hardware.configure")),
    ("/api/blu", require("hardware.configure")),
    ("/connections", require("hardware.configure")),
    ("/sensoren", require("hardware.configure")),
    ("/devices", require("hardware.configure")),
    ("/api/watchdog", require("hardware.configure")),

    # System-/Energieeinstellungen
    ("/energie/settings", require("settings.manage")),
    ("/api/energy/settings", require("settings.manage")),
    ("/system", require("settings.manage")),
    ("/design", require("settings.manage")),
)


# ---------------------------------------------------------------------------
# Reservierte Management-Pfade für die nächsten Module. Dadurch ist die
# Rechtearchitektur bereits vorbereitet, bevor Lager/Warenannahme dazukommen.
# ---------------------------------------------------------------------------

MANAGEMENT_PREFIXES = {
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


def permission_requirement(path, method):
    """
    Liefert die für einen Request benötigte Berechtigung.

    Auth-/Admin-Routen werden bewusst nicht hier geregelt:
    - /login und /logout werden durch Auth selbst behandelt.
    - /admin nutzt weiterhin die feineren Decorators aus routes/admin.py.
    """

    path = _normalize_path(path)
    method = (method or "GET").upper()

    if path == "/login" or path == "/logout":
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

        for prefix, requirement in READ_PREFIX:
            if _matches_prefix(path, prefix):
                return requirement

        # Unbekannte API-Lesezugriffe werden nicht einfach mit dashboard.view
        # freigegeben. Sie benötigen mindestens Grow-Leserecht.
        if _matches_prefix(path, "/api"):
            return require("grow.view")

        # Bestehende, noch nicht explizit klassifizierte HTML-Seiten bleiben
        # für Dashboard-Benutzer lesbar. Neue sensible Module sollten oben eine
        # eigene Regel bekommen.
        return require("dashboard.view")

    for prefix, requirement in WRITE_PREFIX:
        if _matches_prefix(path, prefix):
            return requirement

    # Fail-closed für bisher unbekannte Schreibzugriffe: Ein eingeloggter
    # Viewer darf niemals allein durch eine neue POST-Route Schreibrechte
    # erhalten. Standard für bestehende Grow-APIs ist grow.control.
    return require("grow.control")
