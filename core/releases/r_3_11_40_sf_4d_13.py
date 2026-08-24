"""Growstar release node 3.11.40 / SF.4D.13."""

RELEASE = {
    "version": "3.11.40",
    "date": "2026-08-24",
    "phase": "SF.4D.13",
    "title": "Spider-Farmer-Bridge bei Growstar-Restart sauber neu verbinden",
    "summary": (
        "SF.4D.13 behebt den reproduzierten Lifecycle-Fehler, bei dem Sensorwerte "
        "nach einem Growstar-Restart bereits wieder vorhanden waren, Fan- und "
        "Blower-Kommandos aber sporadisch an einer alten Bridge-Session haengen "
        "blieben. Die Spider-Farmer-Bridge wird nun ueber systemd PartOf zusammen "
        "mit growstar.service neu gestartet. Der root-owned Network-Service bleibt "
        "bewusst unangetastet."
    ),
    "changes": (
        "growstar-spiderfarmer.service erhaelt PartOf=growstar.service.",
        "Ein Restart/Stop von growstar.service propagiert damit auf die Spider-Farmer-Bridge.",
        "Der Bridge-Restart verwirft alte Controller-Writer und Subscriptions und erzwingt eine frische Controller-Session.",
        "growstar-spiderfarmer-network.service wird nicht mitgestartet oder neugestartet.",
        "Growstar-SF Autoconnect, nftables NAT/Guard und NetworkManager-Konfiguration bleiben unveraendert.",
        "Keine Aenderung an Fan-, Blower-, Licht-, Shelly- oder Controller-Setpoint-Logik.",
        "Neue Offline-Regression schuetzt die systemd-Restart-Kopplung.",
    ),
    "tests": (
        "python3 tests/regression/check_spiderfarmer_restart_coupling.py",
        "python3 tests/regression/check_spiderfarmer_network_autoconnect.py",
        "python3 tests/regression/check_release_loader.py",
    ),
}
