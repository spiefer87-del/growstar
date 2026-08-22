"""Zentrale Growstar-Release- und Patch-Informationen.

Die öffentliche Schnittstelle dieses Moduls bleibt stabil. Die eigentlichen
Release-Nodes liegen ab Growstar 3.11.3 unter ``core/releases``.
"""

from __future__ import annotations

from copy import deepcopy
import datetime

from .releases import RELEASES


def _display_date(value):
    try:
        return datetime.date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _copy_release(item):
    result = deepcopy(dict(item))
    result["changes"] = list(result.get("changes") or ())
    result["tests"] = list(result.get("tests") or ())
    result["date_label"] = _display_date(result.get("date"))
    return result


def current_release():
    return _copy_release(RELEASES[0])


def release_history():
    return [_copy_release(item) for item in RELEASES]


def release_summary():
    current = RELEASES[0]
    return {
        "version": current["version"],
        "release_date": current["date"],
        "phase": current["phase"],
        "title": current["title"],
    }


GROWSTAR_VERSION = RELEASES[0]["version"]
GROWSTAR_RELEASE_DATE = RELEASES[0]["date"]
GROWSTAR_INTERNAL_PHASE = RELEASES[0]["phase"]
