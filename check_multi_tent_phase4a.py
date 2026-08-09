from pathlib import Path
import importlib.util

ROOT = Path(__file__).parent
main_dashboard = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
grow_hub = (ROOT / "templates" / "grow_control_dashboard.html").read_text(encoding="utf-8")
routes = (ROOT / "routes" / "dashboard.py").read_text(encoding="utf-8")

checks = {
    "Haupt-Dashboard enthält keine Stationsübersicht": 'id="tent-overview-grid"' not in main_dashboard,
    "Haupt-Dashboard pollt /api/tents nicht": 'fetch("/api/tents"' not in main_dashboard,
    "Haupt-Dashboard behält Grow-Control-Modul": "grow_control_dashboard" in main_dashboard,
    "Grow-Control-Hub enthält Stationsübersicht": 'id="tent-overview-grid"' in grow_hub,
    "Grow-Control-Hub liest /api/tents": 'fetch("/api/tents"' in grow_hub,
    "Grow-Control-Hub verlinkt Stationen generisch": "buildTentUrl(tent.id)" in grow_hub,
    "Grow-Control-Hub enthält Setup": "Setup" in grow_hub,
    "Grow-Control-Hub enthält Sensoren": "Sensoren" in grow_hub,
    "Grow-Control-Hub enthält Watchdog": "Watchdog" in grow_hub,
    "Grow-Control-Hub enthält Hardware": "Hardware" in grow_hub,
    "Grow-Control-Hub enthält Energie": "Energie" in grow_hub,
    "/grow-control rendert Hub": 'render_template("grow_control_dashboard.html")' in routes,
    "/grow-control/live bleibt kompatibler Alias": '@app.route("/grow-control/live")' in routes,
}

spec = importlib.util.spec_from_file_location("phase4a_policy", ROOT / "auth" / "policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
for path in ("/grow-control", "/grow-control/live", "/grow-control/tents/tent_3"):
    req = policy.permission_requirement(path, "GET")
    checks[f"{path} benötigt grow.view"] = (
        req is not None and req.permissions == ("grow.view",) and req.mode == "all"
    )

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("✅" if ok else "❌"), name)
if failed:
    raise SystemExit("Phase 4A Hub fehlgeschlagen: " + ", ".join(failed))
print("✅ Phase 4A Grow-Control-Hub vollständig")
