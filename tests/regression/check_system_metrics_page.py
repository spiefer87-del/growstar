#!/usr/bin/env python3
"""Regression für Growstar 3.16.25 / WATCHDOG.SYSTEM.1."""

from pathlib import Path
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.system_metrics import build_system_metrics, reset_cpu_sampler


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def write_fixture(root, relative, content):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory(prefix="growstar-system-metrics-") as temp_dir:
        root = Path(temp_dir)
        proc_root = root / "proc"
        sys_root = root / "sys"
        disk_root = root / "disk"
        disk_root.mkdir()

        write_fixture(proc_root, "stat", "cpu 100 0 50 850 0 0 0 0\n")
        write_fixture(
            proc_root,
            "meminfo",
            "MemTotal:       8000000 kB\n"
            "MemFree:        1000000 kB\n"
            "MemAvailable:   2000000 kB\n"
            "SwapTotal:      1000000 kB\n"
            "SwapFree:        750000 kB\n",
        )
        write_fixture(proc_root, "uptime", "90061.25 1000.00\n")
        write_fixture(
            sys_root,
            "class/thermal/thermal_zone0/temp",
            "55250\n",
        )

        reset_cpu_sampler()
        first = build_system_metrics(
            proc_root=proc_root,
            sys_root=sys_root,
            disk_path=disk_root,
        )
        require(
            first["cpu"]["usage_percent"] is None
            and first["cpu"]["temperature_c"] == 55.2,
            "Die erste Abtastung initialisiert CPU-Zähler und liest die Raspberry-Temperatur",
        )

        write_fixture(proc_root, "stat", "cpu 160 0 80 860 0 0 0 0\n")
        second = build_system_metrics(
            proc_root=proc_root,
            sys_root=sys_root,
            disk_path=disk_root,
        )
        require(
            second["cpu"]["usage_percent"] == 90.0,
            "Die CPU-Auslastung wird aus zwei aufeinanderfolgenden /proc-Abtastungen berechnet",
        )
        require(
            second["memory"]["total_bytes"] == 8000000 * 1024
            and second["memory"]["used_bytes"] == 6000000 * 1024
            and second["memory"]["used_percent"] == 75.0
            and second["memory"]["swap_percent"] == 25.0,
            "Arbeitsspeicher und Swap werden ohne externe Python-Pakete ausgelesen",
        )
        require(
            second["disk"]["total_bytes"] > 0
            and second["disk"]["free_bytes"] >= 0
            and second["disk"]["mount"] == str(disk_root),
            "Datenträgerbelegung wird über den gewählten Systempfad ermittelt",
        )
        require(
            second["uptime"]["seconds"] == 90061
            and second["uptime"]["formatted"] == "1 T 1 Std 1 Min"
            and second["read_only"] is True,
            "Systemlaufzeit und Read-only-Kennzeichnung sind vollständig",
        )

    module_source = (ROOT / "core/system_metrics.py").read_text(encoding="utf-8")
    route_source = (ROOT / "routes/watchdog.py").read_text(encoding="utf-8")
    watchdog_source = (ROOT / "templates/watchdog.html").read_text(encoding="utf-8")
    page_source = (ROOT / "templates/system_metrics.html").read_text(encoding="utf-8")
    policy_source = (ROOT / "auth/policy.py").read_text(encoding="utf-8")
    base_source = (ROOT / "templates/base.html").read_text(encoding="utf-8")

    require(
        "import psutil" not in module_source
        and '"/api/watchdog/systemdaten"' in route_source
        and "build_system_metrics()" in route_source,
        "Die Systemdaten-API ist read-only und benötigt kein zusätzliches psutil-Paket",
    )
    require(
        "watchdog_system_data" in watchdog_source
        and "🖥️ Systemdaten" in watchdog_source
        and "CPU-Auslastung" in page_source
        and "Arbeitsspeicher" in page_source
        and "Datenträger" in page_source
        and "setInterval(refresh, 3000)" in page_source,
        "Watchdog-Button und responsive Live-Systemseite sind vollständig verdrahtet",
    )
    require(
        '"/grow-control/watchdog/systemdaten": require("hardware.view")' in policy_source
        and "'watchdog_system_data'" in base_source,
        "Seite und Navigation verwenden die bestehende Watchdog-Leseberechtigung",
    )
    print("✅ Growstar 3.16.25 / WATCHDOG.SYSTEM.1 vollständig geprüft")


if __name__ == "__main__":
    main()
