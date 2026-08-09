from pathlib import Path
import ast
import importlib.util
import tempfile
from jinja2 import Environment

ROOT = Path(__file__).parent
hub = (ROOT / "templates" / "grow_control_dashboard.html").read_text(encoding="utf-8")
live = (ROOT / "templates" / "grow_control.html").read_text(encoding="utf-8")
routes = (ROOT / "routes" / "dashboard.py").read_text(encoding="utf-8")
tentctl = (ROOT / "tentctl.py").read_text(encoding="utf-8")
app_source = (ROOT / "app.py").read_text(encoding="utf-8")
runtime_source = (ROOT / "core" / "runtime.py").read_text(encoding="utf-8")

ast.parse(routes)
ast.parse(tentctl)
Environment().parse(hub)
Environment().parse(live)

checks = {
    "Generische Stationsroute vorhanden": '@app.route("/grow-control/tents/<tent_id>")' in routes,
    "Legacy /grow-control/live leitet auf Default-Station": "redirect(" in routes and "grow_control_tent" in routes,
    "Stations-ID wird validiert": "validate_tent_id" in routes,
    "Unbekannte Station liefert 404": "abort(404)" in routes,
    "Hub rendert beliebig viele API-Einträge": "tents.forEach" in hub and "renderTent(tent)" in hub,
    "Jede Runtime nutzt dieselbe Detailroute": "open.href = buildTentUrl(tent.id)" in hub,
    "Hub enthält keine tent_2-Sonderlogik": "tent_2" not in hub,
    "Detailansicht enthält keine tent_2-Sonderlogik": "tent_2" not in live,
    "Keine Controller-Auswahl im Hub": "controller_id" not in hub and "Controller ·" not in hub,
    "Keine Controller-Auswahl in Detailansicht": "controller-id" not in live,
    "CLI führt keine Remote-Controller-Ebene ein": '"--controller"' not in tentctl and "set_controller_id" not in tentctl,
    "Live-Ansicht liest stationsbezogenen State": "/api/tents/${encodeURIComponent(TENT_ID)}/state" in live,
    "Live-Ansicht liest stationsbezogene Config": "/api/tents/${encodeURIComponent(TENT_ID)}/config" in live,
    "Globale State-API wird nicht gepollt": 'fetch("/api/state")' not in live,
    "Globale Config-API wird nicht gepollt": 'fetch("/api/config")' not in live,
    "Shadow-Sollzustände werden angezeigt": "shadow_desired" in live and "SHADOW EIN" in live,
    "Nicht-Default-Detaillinks bleiben sicher gesperrt": "lockLegacyDetailLinks" in live,
    "Stationswechsler ist API-dynamisch": 'id="tent-switcher"' in live and "tents.forEach" in live,
    "Polling bleibt bei 2 Sekunden": "setInterval(loadState, 2000)" in live,
    "Backend startet zusätzliche Runtimes generisch": "for extra_runtime in list_runtimes()" in app_source,
    "Backend enthält keine tent_2-Startsonderlogik": "tent_2" not in app_source,
    "Runtime-Registry lädt alle registrierten Zelte": "for tent in tent_manager.list_tents()" in runtime_source,
}

spec = importlib.util.spec_from_file_location("phase4b_tents", ROOT / "core" / "tents.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as tmp:
    manager = mod.TentManager(str(Path(tmp) / "tents.json"))
    manager.load()
    third = manager.add_tent("tent_3", name="Zelt 3")
    fourth = manager.add_tent("veg", name="Vegetation")
    fifth = manager.add_tent("mother_1", name="Mutterpflanzen")
    snapshot = manager.snapshot()
    checks["Drittes Zelt lässt sich generisch registrieren"] = third["id"] == "tent_3"
    checks["Frei benannte Station lässt sich registrieren"] = fourth["id"] == "veg"
    checks["Weitere Station lässt sich ohne Sondercode registrieren"] = fifth["id"] == "mother_1"
    checks["Alle Stationen bleiben auf demselben lokalen Raspberry"] = all(
        item.get("controller_id") == mod.DEFAULT_CONTROLLER_ID
        for item in snapshot["tents"].values()
    )
    checks["Zusätzliche Stationen bleiben hardwaregesperrt"] = all(
        item["id"] == mod.DEFAULT_TENT_ID or not item.get("control_enabled", False)
        for item in snapshot["tents"].values()
    )

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("✅" if ok else "❌"), name)
if failed:
    raise SystemExit("Phase 4B lokale Multi-Station fehlgeschlagen: " + ", ".join(failed))
print("✅ Phase 4B: beliebig viele lokale Grow-Stationen auf einem Raspberry vorbereitet")
