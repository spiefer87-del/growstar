import json
import os
import re
import tempfile
import threading


TENTS_FILE = "tents.json"

DEFAULT_TENT_ID = "tent_1"
DEFAULT_TENT_NAME = "Zelt 1"
DEFAULT_CONTROLLER_ID = "local"

_TENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_tent_id(tent_id):
    """Prüft eine Zelt-ID, bevor sie als Dateiname/Registry-Key verwendet wird."""

    if not isinstance(tent_id, str):
        raise ValueError("tent_id muss ein String sein")

    tent_id = tent_id.strip()
    if not tent_id:
        raise ValueError("tent_id darf nicht leer sein")

    if not _TENT_ID_RE.fullmatch(tent_id):
        raise ValueError(
            "tent_id darf nur Buchstaben, Zahlen, '_' und '-' enthalten"
        )

    return tent_id


def _atomic_write_json(path, data):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".tents-",
        suffix=".tmp",
        dir=directory,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class TentManager:
    """Persistente Metadaten aller Grow-Zelte dieses Controllers.

    Phase 3B unterscheidet bewusst drei Zustände:

    - ``enabled``: Runtime wird geladen.
    - ``shadow_enabled``: Regelkreis darf rechnen, aber keine Hardware schalten.
    - ``control_enabled``: echte Hardware-Aktorik. Diese bleibt in Phase 3B
      ausschließlich für ``tent_1`` aktiv.
    """

    def __init__(self, path=TENTS_FILE):
        self.path = path
        self._lock = threading.RLock()
        self._data = {
            "default_tent_id": DEFAULT_TENT_ID,
            "tents": {},
        }

    def _default_tent(self):
        return {
            "id": DEFAULT_TENT_ID,
            "name": DEFAULT_TENT_NAME,
            "enabled": True,
            "shadow_enabled": False,
            "control_enabled": True,
            "controller_id": DEFAULT_CONTROLLER_ID,
        }

    def _normalize_tent(self, tent_id, tent):
        tent_id = validate_tent_id(tent_id)
        item = dict(tent or {})

        item["id"] = tent_id
        item["name"] = str(
            item.get("name")
            or (DEFAULT_TENT_NAME if tent_id == DEFAULT_TENT_ID else tent_id)
        ).strip()
        item["enabled"] = bool(item.get("enabled", True))
        item["shadow_enabled"] = bool(item.get("shadow_enabled", False))
        item["control_enabled"] = bool(
            item.get("control_enabled", tent_id == DEFAULT_TENT_ID)
        )
        item["controller_id"] = str(
            item.get("controller_id") or DEFAULT_CONTROLLER_ID
        ).strip()

        # Das Default-Zelt bleibt für die Rückwärtskompatibilität produktiv.
        if tent_id == DEFAULT_TENT_ID:
            item["enabled"] = True
            item["shadow_enabled"] = False
            item["control_enabled"] = True
        else:
            # Phase-3B-Sicherheitsgrenze: zusätzliche Zelte besitzen noch
            # grundsätzlich KEINE physische Hardware-Freigabe. Selbst ein
            # manuell gesetztes control_enabled=true in tents.json wird beim
            # Laden wieder auf False normalisiert.
            item["control_enabled"] = False

        return item

    def load(self):
        with self._lock:
            loaded = {
                "default_tent_id": DEFAULT_TENT_ID,
                "tents": {},
            }

            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, dict):
                        tents = data.get("tents", {})
                        if isinstance(tents, list):
                            tents = {
                                item.get("id"): item
                                for item in tents
                                if isinstance(item, dict) and item.get("id")
                            }

                        if not isinstance(tents, dict):
                            tents = {}

                        normalized = {}
                        for raw_id, raw_tent in tents.items():
                            try:
                                tent = self._normalize_tent(raw_id, raw_tent)
                                normalized[tent["id"]] = tent
                            except ValueError as exc:
                                print(
                                    "⚠️ Ungültiger tents.json-Eintrag übersprungen:",
                                    raw_id,
                                    exc,
                                )

                        loaded = {
                            "default_tent_id": data.get(
                                "default_tent_id",
                                DEFAULT_TENT_ID,
                            ),
                            "tents": normalized,
                        }

                except Exception as exc:
                    print("⚠️ tents.json konnte nicht gelesen werden:", exc)

            self._data = loaded
            self._data.setdefault("tents", {})
            self._data["tents"][DEFAULT_TENT_ID] = self._normalize_tent(
                DEFAULT_TENT_ID,
                self._data["tents"].get(
                    DEFAULT_TENT_ID,
                    self._default_tent(),
                ),
            )

            default_id = self._data.get("default_tent_id")
            if default_id not in self._data["tents"]:
                self._data["default_tent_id"] = DEFAULT_TENT_ID

            return self.snapshot()

    def save(self):
        with self._lock:
            _atomic_write_json(self.path, self._data)

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self._data))

    def list_tents(self):
        with self._lock:
            return [
                dict(tent)
                for tent in self._data.get("tents", {}).values()
            ]

    def get(self, tent_id):
        tent_id = validate_tent_id(tent_id)
        with self._lock:
            tent = self._data.get("tents", {}).get(tent_id)
            return dict(tent) if tent else None

    def default_tent_id(self):
        with self._lock:
            return self._data.get(
                "default_tent_id",
                DEFAULT_TENT_ID,
            )

    def add_tent(
        self,
        tent_id,
        *,
        name=None,
        enabled=True,
        shadow_enabled=False,
        control_enabled=False,
        controller_id=DEFAULT_CONTROLLER_ID,
    ):
        """Legt Zelt-Metadaten an; Hardware-Control bleibt standardmäßig AUS."""

        tent_id = validate_tent_id(tent_id)

        if tent_id == DEFAULT_TENT_ID:
            raise ValueError(f"{DEFAULT_TENT_ID} existiert bereits als Default-Zelt")

        if control_enabled:
            raise ValueError(
                "Zusätzliche Hardware-Regelkreise sind in Phase 3B noch gesperrt"
            )

        with self._lock:
            if tent_id in self._data.setdefault("tents", {}):
                raise ValueError(f"Zelt '{tent_id}' existiert bereits")

            item = self._normalize_tent(
                tent_id,
                {
                    "id": tent_id,
                    "name": name or tent_id,
                    "enabled": enabled,
                    "shadow_enabled": shadow_enabled,
                    "control_enabled": False,
                    "controller_id": controller_id,
                },
            )
            self._data["tents"][tent_id] = item
            self.save()
            return dict(item)

    def update_tent(self, tent_id, *, name=None, enabled=None, shadow_enabled=None):
        """Aktualisiert Stations-Metadaten atomar in einem einzigen Save.

        ``None`` bedeutet bei booleschen Feldern "nicht ändern". Zusätzliche
        Stationen bleiben weiterhin grundsätzlich ohne Hardware-Control.
        """

        tent_id = validate_tent_id(tent_id)

        with self._lock:
            current = self._data.get("tents", {}).get(tent_id)
            if current is None:
                raise KeyError(f"Unbekanntes Zelt '{tent_id}'")

            working = dict(current)

            if name is not None:
                normalized_name = str(name or "").strip()
                if not normalized_name:
                    raise ValueError("name darf nicht leer sein")
                working["name"] = normalized_name

            requested_enabled = working.get("enabled", True) if enabled is None else bool(enabled)
            requested_shadow = working.get("shadow_enabled", False) if shadow_enabled is None else bool(shadow_enabled)

            if tent_id == DEFAULT_TENT_ID:
                if enabled is not None and not requested_enabled:
                    raise ValueError("tent_1 kann nicht deaktiviert werden")
                if shadow_enabled is not None and requested_shadow:
                    raise ValueError("tent_1 ist der produktive Regelkreis und kein Shadow-Zelt")
                working["enabled"] = True
                working["shadow_enabled"] = False
                working["control_enabled"] = True
            else:
                if not requested_enabled and requested_shadow:
                    raise ValueError("Shadow kann für eine deaktivierte Station nicht aktiviert werden")
                working["enabled"] = requested_enabled
                working["shadow_enabled"] = requested_shadow if requested_enabled else False
                working["control_enabled"] = False

            # Erst nach vollständiger Validierung ersetzen und genau einmal speichern.
            self._data["tents"][tent_id] = self._normalize_tent(tent_id, working)
            self.save()
            return dict(self._data["tents"][tent_id])

    def rename_tent(self, tent_id, name):
        tent_id = validate_tent_id(tent_id)
        name = str(name or "").strip()
        if not name:
            raise ValueError("name darf nicht leer sein")

        with self._lock:
            if tent_id not in self._data.get("tents", {}):
                raise KeyError(f"Unbekanntes Zelt '{tent_id}'")
            self._data["tents"][tent_id]["name"] = name
            self.save()
            return dict(self._data["tents"][tent_id])

    def set_shadow_enabled(self, tent_id, enabled):
        """Aktiviert/deaktiviert nur den hardwarelosen Shadow-Regelkreis.

        Der tatsächliche Thread wird erst beim nächsten Backend-Start erzeugt.
        """

        tent_id = validate_tent_id(tent_id)
        if tent_id == DEFAULT_TENT_ID:
            raise ValueError("tent_1 ist der produktive Regelkreis und kein Shadow-Zelt")

        with self._lock:
            if tent_id not in self._data.get("tents", {}):
                raise KeyError(f"Unbekanntes Zelt '{tent_id}'")

            tent = self._data["tents"][tent_id]
            tent["shadow_enabled"] = bool(enabled)

            # Sicherheitsinvariante der Phase 3B.
            tent["control_enabled"] = False

            self.save()
            return dict(tent)

    def set_enabled(self, tent_id, enabled):
        tent_id = validate_tent_id(tent_id)
        if tent_id == DEFAULT_TENT_ID:
            raise ValueError("tent_1 kann nicht deaktiviert werden")

        with self._lock:
            if tent_id not in self._data.get("tents", {}):
                raise KeyError(f"Unbekanntes Zelt '{tent_id}'")

            tent = self._data["tents"][tent_id]
            tent["enabled"] = bool(enabled)
            if not tent["enabled"]:
                tent["shadow_enabled"] = False
            tent["control_enabled"] = False

            self.save()
            return dict(tent)


manager = TentManager()


def init_tents():
    """Initialisiert die Zelt-Metadaten nicht-destruktiv."""
    manager.load()
    manager.save()
    return manager
