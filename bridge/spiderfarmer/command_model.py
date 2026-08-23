"""Observed-template Spider Farmer command compiler for SF.4D.

The normal compiler reuses a full real DOWN/setConfigField payload and changes
only Growstar-owned fields.

SF.4D.4 additionally exposes one deliberately separate diagnostic compiler for
the minimal-write experiment. It preserves the observed command envelope and
observed keyPath but sends only the requested module fields. The diagnostic
compiler is not used by the normal Growstar device/UI path.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from core.controller_setpoints import (
    controller_schema_for_family,
    normalize_controller_setpoints,
)

from .state_model import parse_topic


_FIELD_MAP = {
    "fan": {
        "level": "mLevel",
        "oscillation": "shakeLevel",
    },
    "blower": {
        "level": "maxSpeed",
    },
    "light": {
        "level": "mLevel",
    },
    "light2": {
        "level": "mLevel",
    },
}

_MODULE_FAMILY = {
    "fan": "fan",
    "blower": "blower",
    "light": "light",
    "light2": "light",
}


class SpiderFarmerCommandError(RuntimeError):
    pass


def _command_schema(module):
    family = _MODULE_FAMILY.get(str(module))
    field_map = _FIELD_MAP.get(str(module)) or {}

    if not family or not field_map:
        return {}

    return controller_schema_for_family(
        family,
        field_map.keys(),
    )


def _normalize_command_setpoints(module, setpoints):
    schema = _command_schema(module)

    if not schema:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    try:
        return normalize_controller_setpoints(
            setpoints,
            schema,
        )
    except (TypeError, ValueError) as exc:
        raise SpiderFarmerCommandError(str(exc)) from exc


def _payload_matches_module(payload, module):
    if not isinstance(payload, dict):
        return False
    if payload.get("method") != "setConfigField":
        return False

    params = payload.get("params")
    if not isinstance(params, dict):
        return False

    if isinstance(params.get(module), dict):
        return True

    key_path = params.get("keyPath")
    return (
        isinstance(key_path, list)
        and key_path
        and str(key_path[-1]) == module
        and isinstance(params.get(module), dict)
    )


def _template_owned_values_valid(payload, module):
    """Reject observed templates carrying invalid Growstar-owned values."""

    if not _payload_matches_module(payload, module):
        return False

    params = payload.get("params") or {}
    block = params.get(module) or {}
    field_map = _FIELD_MAP.get(str(module)) or {}

    observed = {
        name: block[raw_field]
        for name, raw_field in field_map.items()
        if raw_field in block
    }

    if not observed:
        return True

    try:
        _normalize_command_setpoints(
            module,
            observed,
        )
    except SpiderFarmerCommandError:
        return False

    return True


def _capture_candidates(capture_path):
    """Return capture files from newest generation to oldest generation."""

    capture_path = Path(capture_path)
    candidates = [capture_path]

    rotated = Path(str(capture_path) + ".1")
    if rotated.exists():
        candidates.append(rotated)

    return candidates


def find_latest_template(capture_path, *, pid, module):
    """Return latest safe observed real setConfigField command for module/PID."""

    capture_path = Path(capture_path)
    pid = str(pid or "").strip().upper()
    module = str(module or "").strip()

    if not pid:
        raise SpiderFarmerCommandError("Controller-PID fehlt")
    if module not in _FIELD_MAP:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    readable_capture_seen = False
    last_read_error = None

    for candidate in _capture_candidates(capture_path):
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
            readable_capture_seen = True
        except FileNotFoundError:
            continue
        except OSError as exc:
            last_read_error = exc
            continue

        for line in reversed(lines):
            try:
                row = json.loads(line)
            except (TypeError, ValueError):
                continue

            if not isinstance(row, dict) or row.get("direction") != "down":
                continue

            topic = str(row.get("topic") or "")
            topic_info = parse_topic(topic)

            if not topic_info or topic_info.get("pid") != pid:
                continue

            payload = row.get("payload")
            if not _payload_matches_module(payload, module):
                continue

            if not _template_owned_values_valid(payload, module):
                continue

            return {
                "topic": topic,
                "payload": deepcopy(payload),
                "observed_at": row.get("ts"),
                "session_id": row.get("session_id"),
            }

    if not readable_capture_seen and last_read_error is not None:
        raise SpiderFarmerCommandError(
            f"Spider-Farmer-Rohcapture nicht lesbar: {last_read_error}"
        ) from last_read_error

    if not readable_capture_seen:
        raise SpiderFarmerCommandError(
            f"Spider-Farmer-Rohcapture nicht gefunden: {capture_path}"
        )

    raise SpiderFarmerCommandError(
        f"Noch kein gültiges echtes setConfigField-Template für {module} / {pid} "
        "beobachtet. Einmal in der Spider-Farmer-App einen gültigen Wert dieses "
        "Geräts ändern und danach erneut versuchen."
    )



def _confirmed_manual_fan_payload(pid, normalized_setpoints, *, diagnostic=None):
    """Build the controller-confirmed manual fan command without capture data.

    Real-controller tests confirmed that the GGS controller accepts the stable
    DOWN topic/keyPath together with modeType=0, mOnOff=1 and mLevel L1..L10.
    This helper is intentionally fan-only; other modules still require a real
    observed template.
    """

    pid = str(pid or "").strip().upper()
    if not pid:
        raise SpiderFarmerCommandError("Controller-PID fehlt")

    fan_block = {
        "modeType": 0,
        "mOnOff": 1,
    }
    changed_fields = {
        "modeType": 0,
        "mOnOff": 1,
    }

    for name, value in normalized_setpoints.items():
        raw_field = _FIELD_MAP["fan"][name]
        fan_block[raw_field] = value
        changed_fields[raw_field] = value

    result = {
        "topic": f"SF/GGS/CB/API/DOWN/{pid}",
        "payload": {
            "method": "setConfigField",
            "params": {
                "keyPath": ["device", "fan"],
                "fan": fan_block,
            },
        },
        "observed_at": None,
        "session_id": None,
        "module": "fan",
        "changed_fields": changed_fields,
    }
    if diagnostic:
        result["diagnostic"] = diagnostic
    return result


def compile_manual_fan_command(*, pid, setpoints):
    """Compatibility diagnostic for the controller-confirmed manual fan write.

    The historical chat/hardware test used raw Spider-Farmer names:
    modeType=0 plus mLevel=N.  Restore that exact private diagnostic action so
    it can be repeated without first generating an app-side template.
    """

    if not isinstance(setpoints, dict):
        raise SpiderFarmerCommandError("Manueller Fan-Test erwartet setpoints")

    mode_type = setpoints.get("modeType")
    level = setpoints.get("mLevel")
    on_off = setpoints.get("mOnOff", 1)

    if mode_type != 0:
        raise SpiderFarmerCommandError(
            "Manueller Fan-Test erwartet modeType=0"
        )
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 10:
        raise SpiderFarmerCommandError(
            "Manueller Fan-Test erwartet mLevel zwischen 1 und 10"
        )
    if on_off != 1:
        raise SpiderFarmerCommandError(
            "Manueller Fan-Test erwartet mOnOff=1"
        )

    normalized = {"level": level}

    if "shakeLevel" in setpoints:
        shake = setpoints["shakeLevel"]
        try:
            normalized.update(
                _normalize_command_setpoints(
                    "fan",
                    {"oscillation": shake},
                )
            )
        except SpiderFarmerCommandError:
            raise

    return _confirmed_manual_fan_payload(
        pid,
        normalized,
        diagnostic="confirmed_manual_fan",
    )

def compile_controller_command(
    capture_path,
    *,
    pid,
    module,
    setpoints,
):
    if not isinstance(setpoints, dict) or not setpoints:
        raise SpiderFarmerCommandError("Keine Controller-Sollwerte angegeben")

    module = str(module)
    field_map = _FIELD_MAP.get(module)
    if not field_map:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    normalized_setpoints = _normalize_command_setpoints(
        module,
        setpoints,
    )

    try:
        template = find_latest_template(
            capture_path,
            pid=pid,
            module=module,
        )
    except SpiderFarmerCommandError:
        # Fan is the one controller family for which the complete manual
        # envelope was confirmed on real hardware.  If no safe observed
        # template exists yet (for example after capture rotation/restart),
        # use that confirmed envelope instead of blocking Growstar control.
        if module == "fan":
            return _confirmed_manual_fan_payload(
                pid,
                normalized_setpoints,
                diagnostic="confirmed_manual_fan_fallback",
            )
        raise

    payload = deepcopy(template["payload"])
    params = payload.get("params")

    if not isinstance(params, dict):
        raise SpiderFarmerCommandError(
            "Beobachtetes Template enthält keinen params-Block"
        )

    changed_fields = {}

    if module == "fan":
        key_path = params.get("keyPath")
        if not isinstance(key_path, list) or not key_path:
            raise SpiderFarmerCommandError(
                "Beobachtetes Template enthält keinen gültigen keyPath"
            )

        # Am realen GGS-Controller bestätigt:
        #   modeType=0 -> Manueller Modus
        #   mOnOff=1   -> controller-interner Fan EIN
        #   mLevel=N   -> manuelle Ventilatorstufe L1..L10
        #
        # Spider-Farmer-Zeitfenster, Zyklus, Standby und Natural Wind werden
        # bewusst nicht aus einem alten Template zurückgesendet.
        fan_block = {
            "modeType": 0,
            "mOnOff": 1,
        }
        changed_fields.update({
            "modeType": 0,
            "mOnOff": 1,
        })

        for name, value in normalized_setpoints.items():
            raw_field = field_map[name]
            fan_block[raw_field] = value
            changed_fields[raw_field] = value

        payload["params"] = {
            "keyPath": deepcopy(key_path),
            "fan": fan_block,
        }

    else:
        block = params.get(module)

        if not isinstance(block, dict):
            raise SpiderFarmerCommandError(
                f"Beobachtetes Template enthält keinen {module}-Block"
            )

        for name, value in normalized_setpoints.items():
            raw_field = field_map[name]
            block[raw_field] = value
            changed_fields[raw_field] = value

    return {
        "topic": template["topic"],
        "payload": payload,
        "observed_at": template.get("observed_at"),
        "session_id": template.get("session_id"),
        "module": module,
        "changed_fields": changed_fields,
    }


def compile_minimal_controller_command(
    capture_path,
    *,
    pid,
    module,
    setpoints,
):
    """Compile the SF.4D.4 one-off minimal-write diagnostic payload.

    This is intentionally separate from compile_controller_command().

    It preserves:
      - the real observed DOWN topic,
      - the real observed command envelope,
      - the real observed params.keyPath.

    It removes every unrelated field from params[module] and keeps only the
    explicitly requested Growstar-owned raw field(s).

    The result is meant only for the controlled minimal-write experiment.
    """

    if not isinstance(setpoints, dict) or not setpoints:
        raise SpiderFarmerCommandError("Keine Controller-Sollwerte angegeben")

    field_map = _FIELD_MAP.get(str(module))
    if not field_map:
        raise SpiderFarmerCommandError(
            f"Modul {module!r} wird noch nicht geschrieben"
        )

    normalized_setpoints = _normalize_command_setpoints(
        module,
        setpoints,
    )

    template = find_latest_template(
        capture_path,
        pid=pid,
        module=module,
    )

    observed_payload = template["payload"]
    observed_params = observed_payload.get("params")

    if not isinstance(observed_params, dict):
        raise SpiderFarmerCommandError(
            "Beobachtetes Template enthält keinen params-Block"
        )

    key_path = observed_params.get("keyPath")
    if not isinstance(key_path, list) or not key_path:
        raise SpiderFarmerCommandError(
            "Beobachtetes Template enthält keinen gültigen keyPath"
        )

    payload = deepcopy(observed_payload)

    minimal_block = {}
    changed_fields = {}

    for name, value in normalized_setpoints.items():
        raw_field = field_map[name]
        minimal_block[raw_field] = value
        changed_fields[raw_field] = value

    payload["params"] = {
        "keyPath": deepcopy(key_path),
        str(module): minimal_block,
    }

    return {
        "topic": template["topic"],
        "payload": payload,
        "observed_at": template.get("observed_at"),
        "session_id": template.get("session_id"),
        "module": str(module),
        "changed_fields": changed_fields,
        "diagnostic": "minimal_write",
    }


def compile_powered_minimal_fan_command(
    capture_path,
    *,
    pid,
    setpoints,
):
    """Compile the isolated SF.4D.5 powered-minimal fan experiment.

    This is intentionally NOT the production controller compiler.

    The historical SF.4D.4/SF.4D.5 experiments isolated the smallest fan
    blocks. The corrected fan field map now resolves Growstar fan level to
    mLevel. This diagnostic therefore sends:

        fan:
            mOnOff: 1
            <exactly one requested Growstar-owned fan field>

    The production compiler additionally owns the confirmed modeType=0 envelope.
    """

    if not isinstance(setpoints, dict) or len(setpoints) != 1:
        raise SpiderFarmerCommandError(
            "SF.4D.5 Powered-Minimaltest erwartet genau einen Fan-Sollwert"
        )

    normalized_setpoints = _normalize_command_setpoints(
        "fan",
        setpoints,
    )

    template = find_latest_template(
        capture_path,
        pid=pid,
        module="fan",
    )

    observed_payload = template["payload"]
    observed_params = observed_payload.get("params")

    if not isinstance(observed_params, dict):
        raise SpiderFarmerCommandError(
            "Beobachtetes Template enthält keinen params-Block"
        )

    key_path = observed_params.get("keyPath")

    if not isinstance(key_path, list) or not key_path:
        raise SpiderFarmerCommandError(
            "Beobachtetes Template enthält keinen gültigen keyPath"
        )

    payload = deepcopy(observed_payload)

    fan_block = {
        "mOnOff": 1,
    }
    changed_fields = {
        "mOnOff": 1,
    }

    for name, value in normalized_setpoints.items():
        raw_field = _FIELD_MAP["fan"][name]
        fan_block[raw_field] = value
        changed_fields[raw_field] = value

    payload["params"] = {
        "keyPath": deepcopy(key_path),
        "fan": fan_block,
    }

    return {
        "topic": template["topic"],
        "payload": payload,
        "observed_at": template.get("observed_at"),
        "session_id": template.get("session_id"),
        "module": "fan",
        "changed_fields": changed_fields,
        "diagnostic": "powered_minimal_fan_write",
    }
