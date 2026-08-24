"""Growstar release node 3.11.36 / CTRL.3.3."""

RELEASE = {
    "version": "3.11.36",
    "date": "2026-08-24",
    "phase": "CTRL.3.3",
    "title": "Shelly-Power-Gate direkt aus TentRuntime auflösen",
    "summary": (
        "CTRL.3.3 behebt den im realen Diagnosepfad bestätigten KeyError "
        "bei der Controller-Powerfreigabe. Die Shelly-Zuordnung wird nicht "
        "mehr erneut über hardware_snapshot()/tent_manager aufgelöst, sondern "
        "direkt aus der bereits geladenen runtime.config der aktiven Station."
    ),
    "changes": (
        "Shelly-Endpoint wird über DEVICE_HARDWARE direkt aus runtime.config gelesen.",
        "Kein erneutes Tent-Manager-Lookup im laufenden Controller-Regelpfad.",
        "Der vorhandene read-only actuator_health Cache bleibt die physische EIN-Bestätigung.",
        "Runtime-EIN bleibt der primäre schnelle Freigabepfad.",
        "Power AUS bleibt hart Shelly-autoritativ und sendet niemals Controllerwerte.",
        "Keine Änderung an Spider-Farmer-Payloads oder Modus-Sollwerten.",
    ),
}
