"""Read-only Systemmetriken des Growstar-Hosts ohne Zusatzabhängigkeiten."""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import socket
import threading
from pathlib import Path


_CPU_SAMPLE_LOCK = threading.Lock()
_CPU_SAMPLES = {}


def _round(value, digits=1):
    return None if value is None else round(float(value), digits)


def _read_cpu_counters(proc_root):
    first_line = (Path(proc_root) / "stat").read_text(encoding="utf-8").splitlines()[0]
    fields = first_line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("/proc/stat enthält keine gültigen CPU-Zähler.")
    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    # guest/guest_nice sind bereits in user/nice enthalten und dürfen nicht
    # ein zweites Mal in die Linux-Gesamtsumme einfließen.
    total = sum(values[:8])
    return total, idle


def _cpu_usage_percent(proc_root):
    sample_key = str(Path(proc_root).resolve())
    current_total, current_idle = _read_cpu_counters(proc_root)
    with _CPU_SAMPLE_LOCK:
        previous = _CPU_SAMPLES.get(sample_key)
        _CPU_SAMPLES[sample_key] = (current_total, current_idle)
    if not previous:
        return None

    total_delta = current_total - previous[0]
    idle_delta = current_idle - previous[1]
    if total_delta <= 0:
        return None
    busy = max(0, total_delta - max(0, idle_delta))
    return _round(max(0, min(100, (busy / total_delta) * 100)))


def _read_cpu_temperature(sys_root):
    root = Path(sys_root)
    candidates = list((root / "class" / "thermal").glob("thermal_zone*/temp"))
    candidates += list((root / "class" / "hwmon").glob("hwmon*/temp1_input"))
    for path in candidates:
        try:
            raw = float(path.read_text(encoding="utf-8").strip())
            temperature = raw / 1000 if abs(raw) > 300 else raw
            if -20 <= temperature <= 150:
                return _round(temperature)
        except (OSError, ValueError):
            continue
    return None


def _read_meminfo(proc_root):
    values = {}
    for line in (Path(proc_root) / "meminfo").read_text(encoding="utf-8").splitlines():
        key, separator, raw = line.partition(":")
        if not separator:
            continue
        number = raw.strip().split()[0]
        try:
            values[key] = int(number) * 1024
        except (ValueError, IndexError):
            continue

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(0, total - available)
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "used_percent": _round((used / total) * 100) if total else None,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
        "swap_percent": _round((swap_used / swap_total) * 100) if swap_total else 0.0,
    }


def _read_uptime_seconds(proc_root):
    return max(
        0,
        int(float((Path(proc_root) / "uptime").read_text(encoding="utf-8").split()[0])),
    )


def _format_uptime(seconds):
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days} T")
    if hours or days:
        parts.append(f"{hours} Std")
    parts.append(f"{minutes} Min")
    return " ".join(parts)


def _load_average():
    try:
        values = os.getloadavg()
        return {
            "one_min": _round(values[0], 2),
            "five_min": _round(values[1], 2),
            "fifteen_min": _round(values[2], 2),
        }
    except (AttributeError, OSError):
        return {"one_min": None, "five_min": None, "fifteen_min": None}


def _component(snapshot, name, function, fallback, errors):
    try:
        snapshot[name] = function()
    except Exception as exc:
        snapshot[name] = fallback
        errors.append({"component": name, "message": str(exc)})


def build_system_metrics(*, proc_root="/proc", sys_root="/sys", disk_path="/"):
    """Erzeugt einen fehlertoleranten, vollständig read-only System-Snapshot."""
    errors = []
    snapshot = {
        "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "read_only": True,
        "errors": errors,
    }

    def cpu_metrics():
        return {
            "usage_percent": _cpu_usage_percent(proc_root),
            "temperature_c": _read_cpu_temperature(sys_root),
            "logical_cores": os.cpu_count() or 1,
            "load": _load_average(),
        }

    def disk_metrics():
        usage = shutil.disk_usage(disk_path)
        used = max(0, usage.total - usage.free)
        return {
            "mount": str(disk_path),
            "total_bytes": usage.total,
            "used_bytes": used,
            "free_bytes": usage.free,
            "used_percent": _round((used / usage.total) * 100) if usage.total else None,
        }

    def uptime_metrics():
        seconds = _read_uptime_seconds(proc_root)
        return {"seconds": seconds, "formatted": _format_uptime(seconds)}

    _component(
        snapshot,
        "cpu",
        cpu_metrics,
        {
            "usage_percent": None,
            "temperature_c": None,
            "logical_cores": os.cpu_count() or 1,
            "load": _load_average(),
        },
        errors,
    )
    _component(snapshot, "memory", lambda: _read_meminfo(proc_root), {}, errors)
    _component(snapshot, "disk", disk_metrics, {"mount": str(disk_path)}, errors)
    _component(snapshot, "uptime", uptime_metrics, {}, errors)
    snapshot["system"] = {
        "hostname": socket.gethostname(),
        "operating_system": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
    }
    snapshot["ok"] = not errors
    return snapshot


def reset_cpu_sampler():
    """Setzt nur den flüchtigen CPU-Abtastzustand zurück (für Regressionstests)."""
    with _CPU_SAMPLE_LOCK:
        _CPU_SAMPLES.clear()
