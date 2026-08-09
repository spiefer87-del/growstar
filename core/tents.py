import json
import os
import threading


TENTS_FILE = "tents.json"

DEFAULT_TENT_ID = "tent_1"
DEFAULT_TENT_NAME = "Zelt 1"
DEFAULT_CONTROLLER_ID = "local"


class TentManager:
    """Verwaltet die Zelt-Metadaten.

    In Phase 1 wird nur das bestehende Growstar-System als ``tent_1``
    registriert. State, Config und Regelung bleiben zunächst unverändert.
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
            "controller_id": DEFAULT_CONTROLLER_ID,
        }

    def load(self):
        with self._lock:
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

                        self._data = {
                            "default_tent_id": data.get(
                                "default_tent_id",
                                DEFAULT_TENT_ID,
                            ),
                            "tents": tents,
                        }

                except Exception as exc:
                    print("⚠️ tents.json konnte nicht gelesen werden:", exc)

            self._data.setdefault("tents", {})
            self._data["tents"].setdefault(
                DEFAULT_TENT_ID,
                self._default_tent(),
            )

            default_id = self._data.get("default_tent_id")
            if default_id not in self._data["tents"]:
                self._data["default_tent_id"] = DEFAULT_TENT_ID

            return self.snapshot()

    def save(self):
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(
                    self._data,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

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
        with self._lock:
            tent = self._data.get("tents", {}).get(tent_id)
            return dict(tent) if tent else None

    def default_tent_id(self):
        with self._lock:
            return self._data.get(
                "default_tent_id",
                DEFAULT_TENT_ID,
            )


manager = TentManager()


def init_tents():
    """Initialisiert die Zelt-Metadaten nicht-destruktiv."""
    manager.load()
    manager.save()
    return manager
