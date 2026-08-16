from copy import deepcopy
import ipaddress
import re

from core.config import config as default_config, save_config
from core.runtime import get_runtime, list_runtimes
from core.tent_config import ensure_tent_config, load_tent_config, save_tent_config
from core.tents import DEFAULT_TENT_ID, manager as tent_manager, validate_tent_id


DEVICE_HARDWARE = {
    "heating": {
        "label": "Heizung",
        "icon": "🔥",
        "ip_key": "IP_HEATING",
        "relay_key": "RELAY_HEATING",
    },
    "fan": {
        "label": "Abluft / Lüfter",
        "icon": "💨",
        "ip_key": "IP_FAN",
        "relay_key": "RELAY_FAN",
    },
    "light": {
        "label": "Beleuchtung",
        "icon": "💡",
        "ip_key": "IP_LIGHT",
        "relay_key": "RELAY_LIGHT",
    },
    "vent": {
        "label": "Ventilator",
        "icon": "🌀",
        "ip_key": "IP_VENT",
        "relay_key": "RELAY_VENT",
    },
    "irrigation": {
        "label": "Bewässerung",
        "icon": "💧",
        "ip_key": "IP_IRRIGATION",
        "relay_key": "RELAY_IRRIGATION",
    },
    "humidifier": {
        "label": "Luftbefeuchter",
        "icon": "💦",
        "ip_key": "IP_HUMIDIFIER",
        "relay_key": "RELAY_HUMIDIFIER",
    },
    "dehumidifier": {
        "label": "Entfeuchter",
        "icon": "🌬️",
        "ip_key": "IP_DEHUMIDIFIER",
        "relay_key": "RELAY_DEHUMIDIFIER",
    },
    "light2": {
        "label": "Licht 2",
        "icon": "💡",
        "ip_key": "IP_LIGHT2",
        "relay_key": "RELAY_LIGHT2",
    },
    "vent2": {
        "label": "Ventilator 2",
        "icon": "🌀",
        "ip_key": "IP_VENT2",
        "relay_key": "RELAY_VENT2",
    },
}

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)


class HardwareConflictError(ValueError):
    def __init__(self, message, *, endpoint=None, owner=None):
        super().__init__(message)
        self.endpoint = endpoint
        self.owner = owner


class HardwareAssignmentActiveModeError(ValueError):
    def __init__(self, device, *, mode, current=None, requested=None):
        self.device = str(device)
        self.mode = str(mode or "OFF").upper()
        self.current = deepcopy(current)
        self.requested = deepcopy(requested)
        super().__init__(
            f"{self.device}: Hardware-Zuordnung kann im Modus {self.mode} "
            "nicht geändert werden. Gerät zuerst auf OFF / Deaktiviert setzen."
        )


class HardwareAssignmentNotSafeOffError(ValueError):
    def __init__(self, device, *, current=None, health=None):
        self.device = str(device)
        self.current = deepcopy(current)
        self.health = deepcopy(health)
        super().__init__(
            f"{self.device}: Die bisherige Hardware-Zuordnung kann erst "
            "geändert oder entfernt werden, wenn der alte Ausgang als "
            "ONLINE · AUS bestätigt wurde."
        )


def _normalize_host(value):
    value = str(value or "").strip()
    if not value:
        return ""

    if "://" in value or "/" in value or any(ch.isspace() for ch in value):
        raise ValueError("IP/Hostname darf kein Protokoll, keinen Pfad und keine Leerzeichen enthalten")

    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        if not _HOST_RE.fullmatch(value):
            raise ValueError(f"Ungültige IP/Hostname-Angabe: {value}")
        return value.lower()

    # services/shelly.py baut aktuell klassische http://<host>/... URLs.
    # IPv6 würde dort Klammern benötigen und wird deshalb vorerst nicht
    # stillschweigend akzeptiert.
    if ip.version != 4:
        raise ValueError("IPv6-Hardwareadressen werden derzeit noch nicht unterstützt")
    return str(ip)


def _normalize_relay(value):
    if value in (None, ""):
        return None
    try:
        relay = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Relay muss eine Ganzzahl sein") from exc
    if relay < 0 or relay > 15:
        raise ValueError("Relay muss zwischen 0 und 15 liegen")
    return relay


def _runtime_map():
    return {runtime.tent_id: runtime for runtime in list_runtimes()}


def _registered_config(tent_id, runtime_map=None):
    tent_id = validate_tent_id(tent_id)
    runtime_map = runtime_map or _runtime_map()

    runtime = runtime_map.get(tent_id)
    if runtime is not None:
        return runtime.config, runtime

    if tent_id == DEFAULT_TENT_ID:
        return default_config, None

    ensure_tent_config(tent_id)
    return load_tent_config(tent_id), None


def _save_registered_config(tent_id, cfg, runtime=None):
    tent_id = validate_tent_id(tent_id)

    if runtime is not None:
        runtime.config.clear()
        runtime.config.update(cfg)
        runtime.persist_config()
        return

    if tent_id == DEFAULT_TENT_ID:
        default_config.clear()
        default_config.update(cfg)
        save_config(default_config)
        return

    save_tent_config(tent_id, cfg)


def _config_device_mode(cfg, device):
    """Liest den Gerätemodus direkt aus der stationsbezogenen Config."""
    modes = cfg.get("DEVICE_MODES", {})
    value = modes.get(device, "OFF") if isinstance(modes, dict) else "OFF"
    if isinstance(value, dict):
        value = value.get("mode", "OFF")
    return str(value or "OFF").upper()


def hardware_snapshot(tent_id):
    tent_id = validate_tent_id(tent_id)
    tent = tent_manager.get(tent_id)
    if tent is None:
        raise KeyError(tent_id)

    runtime_map = _runtime_map()
    cfg, runtime = _registered_config(tent_id, runtime_map)

    assignments = {}
    for device, meta in DEVICE_HARDWARE.items():
        host = str(cfg.get(meta["ip_key"]) or "").strip()
        relay = cfg.get(meta["relay_key"])
        try:
            relay = int(relay) if relay not in (None, "") else None
        except (TypeError, ValueError):
            relay = None

        assignments[device] = {
            "device": device,
            "label": meta["label"],
            "icon": meta["icon"],
            "ip": host,
            "relay": relay,
            "configured": bool(host) and relay is not None,
        }

        assignments[device]["mode"] = _config_device_mode(
            cfg,
            device,
        )

    control_enabled = bool(runtime.control_enabled) if runtime else bool(tent.get("control_enabled", False))
    return {
        "success": True,
        "tent_id": tent_id,
        "name": (runtime.name if runtime else tent.get("name")) or tent_id,
        "runtime_loaded": runtime is not None,
        "control_enabled": control_enabled,
        "shadow_enabled": bool(runtime.shadow_enabled) if runtime else bool(tent.get("shadow_enabled", False)),
        "hardware_actuation_blocked": not control_enabled,
        "editable": True,
        "assignments": assignments,
    }


def device_assignment(tent_id, device):
    """Liefert genau eine Zuordnung ohne Netzwerkzugriff."""
    if device not in DEVICE_HARDWARE:
        raise ValueError(f"Unbekanntes Gerät: {device}")
    return deepcopy(hardware_snapshot(tent_id)["assignments"][device])


def _endpoint_tuple(assignment):
    if not assignment or not assignment.get("configured"):
        return None
    return (
        str(assignment.get("ip") or "").strip().lower(),
        int(assignment.get("relay")),
    )


def _assert_assignment_change_safe(tent_id, runtime, current_snapshot, normalized):
    """Read-only Guard vor einer Endpoint-Änderung."""
    from core.hardware.actuator_health import get_endpoint_health

    for device, endpoint in normalized.items():
        current = current_snapshot["assignments"][device]
        current_endpoint = _endpoint_tuple(current)
        requested_endpoint = (
            None if endpoint is None
            else (str(endpoint[0]).strip().lower(), int(endpoint[1]))
        )

        if current_endpoint == requested_endpoint:
            continue

        mode = str(current.get("mode") or "OFF").upper()
        if mode != "OFF":
            raise HardwareAssignmentActiveModeError(
                device,
                mode=mode,
                current=current,
                requested=(
                    {"ip": requested_endpoint[0], "relay": requested_endpoint[1]}
                    if requested_endpoint else None
                ),
            )

        # Bei LIVE niemals die Adresse eines möglicherweise noch laufenden
        # Relais verlieren. Der zentrale read-only Health-Poll muss den alten
        # Endpoint frisch als ONLINE · AUS bestätigt haben.
        if not runtime or not runtime.control_enabled or current_endpoint is None:
            continue

        health = get_endpoint_health(current_endpoint[0], current_endpoint[1])
        confirmed_off = bool(
            health
            and health.get("state") == "ok"
            and health.get("reachable") is True
            and health.get("actual_state") is False
        )
        if not confirmed_off:
            raise HardwareAssignmentNotSafeOffError(
                device,
                current=current,
                health=health,
            )


def _normalize_patch(data):
    if not isinstance(data, dict):
        raise TypeError("Hardware-Update muss ein JSON-Objekt sein")

    raw_assignments = data.get("assignments", data)
    if not isinstance(raw_assignments, dict):
        raise TypeError("assignments muss ein JSON-Objekt sein")

    normalized = {}
    unknown = sorted(set(raw_assignments) - set(DEVICE_HARDWARE))
    if unknown:
        raise ValueError("Unbekannte Geräte: " + ", ".join(unknown))

    for device, raw in raw_assignments.items():
        if not isinstance(raw, dict):
            raise TypeError(f"Hardware-Zuordnung für {device} muss ein JSON-Objekt sein")

        host = _normalize_host(raw.get("ip", raw.get("host")))
        relay = _normalize_relay(raw.get("relay"))

        # Ein nicht verwendeter Aktor darf vollständig offen bleiben.
        # Das UI kann bei einem leeren IP-Feld trotzdem noch Relay 0 anzeigen;
        # ohne Host existiert bewusst keine Hardware-Zuordnung.
        if not host:
            normalized[device] = None
            continue

        # Shelly Plug / Plug S und viele 1-Kanal-Shellys verwenden Relay 0.
        # Wird nur eine IP/Hostname angegeben, ist Relay 0 daher der sichere
        # und rückwärtskompatible Standard. Mehrkanal-Geräte können weiterhin
        # explizit Relay 1..15 wählen.
        if relay is None:
            relay = 0

        normalized[device] = (host, relay)

    return normalized


def _endpoint_owners(*, exclude_tent_id=None, candidate_cfg=None):
    runtime_map = _runtime_map()
    owners = {}

    for tent in tent_manager.list_tents():
        tent_id = tent["id"]
        if tent_id == exclude_tent_id and candidate_cfg is not None:
            cfg = candidate_cfg
        else:
            cfg, _ = _registered_config(tent_id, runtime_map)

        for device, meta in DEVICE_HARDWARE.items():
            host = str(cfg.get(meta["ip_key"]) or "").strip()
            relay = cfg.get(meta["relay_key"])
            if not host or relay in (None, ""):
                continue
            try:
                relay = int(relay)
            except (TypeError, ValueError):
                continue

            endpoint = (host.lower(), relay)
            owner = owners.get(endpoint)
            current = {"tent_id": tent_id, "device": device}
            if owner is not None and owner != current:
                raise HardwareConflictError(
                    f"Hardware-Endpunkt {host} / Relay {relay} ist mehrfach belegt",
                    endpoint={"ip": host, "relay": relay},
                    owner=owner,
                )
            owners[endpoint] = current

    return owners


def update_hardware_assignments(tent_id, data):
    """Ändert IP-/Relay-Zuordnungen einer Station sicher und atomar.

    Die Zuordnung darf auch bei einer LIVE-Station bearbeitet werden.
    Die Änderung betrifft ausschließlich die gespeicherte Zieladresse des
    Aktors; sie löst in dieser Funktion niemals selbst einen Shelly-Schaltbefehl
    aus. Der globale Doppelbelegungsschutz bleibt aktiv.
    """

    tent_id = validate_tent_id(tent_id)
    tent = tent_manager.get(tent_id)
    if tent is None:
        raise KeyError(tent_id)

    runtime_map = _runtime_map()
    cfg, runtime = _registered_config(tent_id, runtime_map)

    normalized = _normalize_patch(data)
    current_snapshot = hardware_snapshot(tent_id)
    _assert_assignment_change_safe(
        tent_id,
        runtime,
        current_snapshot,
        normalized,
    )
    working = deepcopy(cfg)

    for device, endpoint in normalized.items():
        meta = DEVICE_HARDWARE[device]
        if endpoint is None:
            working.pop(meta["ip_key"], None)
            working.pop(meta["relay_key"], None)
            continue

        host, relay = endpoint
        working[meta["ip_key"]] = host
        working[meta["relay_key"]] = relay

    # Prüft sowohl Doppelbelegungen innerhalb der Station als auch zwischen
    # allen registrierten Stationen, inklusive aktuell deaktivierter Runtimes.
    _endpoint_owners(exclude_tent_id=tent_id, candidate_cfg=working)

    _save_registered_config(tent_id, working, runtime=runtime)
    return hardware_snapshot(tent_id)


def validate_hardware_assignments():
    """Validiert die globale Host/Relay-Eindeutigkeit read-only.

    Wird vom LIVE-Preflight verwendet, damit auch manuell veränderte Configs
    niemals an der normalen Zuordnungs-API vorbei in den LIVE-Betrieb gelangen.
    """
    _endpoint_owners()
    return True
