#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if new in text:
        print(f"✅ {label}: bereits angewendet")
        return
    if old not in text:
        raise SystemExit(f"❌ {label}: erwarteter Codeblock nicht gefunden in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"✅ {label}")

required = {
    "core/control.py": "calculate_light_sun_state",
    "core/config.py": "LIGHT_SUN_ENABLED",
    "templates/settings.html": 'id="LIGHT_SUN_ENABLED"',
}
for rel, marker in required.items():
    p = ROOT / rel
    if not p.exists() or marker not in p.read_text(encoding="utf-8"):
        raise SystemExit(f"❌ Voraussetzung 3.14.0 fehlt/unvollständig: {rel}")

replace_once(
    "routes/tents.py",
    """def _config_payload(runtime):
    return {
""",
    """def _light_sun_availability(runtime):
    assignment = controller_assignment_for_config(runtime.config, "light")

    if not isinstance(assignment, dict):
        return {
            "available": False,
            "reason": (
                "Sonnenaufgang/Sonnenuntergang benötigt einen zugewiesenen "
                "Licht-Controller mit Dimmfunktion. Bitte unter Grow Control "
                "→ Controller-Funktionen zuerst einen Controller für "
                "Beleuchtung zuweisen."
            ),
            "assignment": None,
        }

    target_id = str(assignment.get("target_id") or "").strip()
    provider = str(assignment.get("provider") or "").strip()

    if not target_id:
        return {
            "available": False,
            "reason": (
                "Die Beleuchtung besitzt keine vollständige "
                "Controller-Zuweisung. Bitte die Controller-Zuordnung "
                "erneut speichern."
            ),
            "assignment": None,
        }

    return {
        "available": True,
        "reason": None,
        "assignment": {
            "provider": provider,
            "target_id": target_id,
        },
    }


def _config_payload(runtime):
    sun = _light_sun_availability(runtime)

    return {
""",
    "Config-API erhält Lichtcontroller-Verfügbarkeitsprüfung",
)

replace_once(
    "routes/tents.py",
    """        "profiles": sorted((PROFILES.get("profiles") or {}).keys()),
        "config": config_snapshot(runtime),
    }
""",
    """        "profiles": sorted((PROFILES.get("profiles") or {}).keys()),
        "light_sun_available": bool(sun["available"]),
        "light_sun_unavailable_reason": sun["reason"],
        "light_sun_controller_assignment": sun["assignment"],
        "config": config_snapshot(runtime),
    }
""",
    "Config-API liefert Sonnenverlauf-Verfügbarkeit",
)

replace_once(
    "routes/tents.py",
    """        data = request.get_json(silent=True) or {}
        try:
            _validate_station_config_patch(data)
            result = apply_config_patch(data, runtime=runtime)
""",
    """        data = request.get_json(silent=True) or {}

        if bool(data.get("LIGHT_SUN_ENABLED")):
            sun = _light_sun_availability(runtime)
            if not sun["available"]:
                return jsonify(
                    success=False,
                    error="light_sun_controller_required",
                    message=sun["reason"],
                ), 409

        try:
            _validate_station_config_patch(data)
            result = apply_config_patch(data, runtime=runtime)
""",
    "Config-POST blockiert Sonnenverlauf ohne Lichtcontroller",
)

replace_once(
    "core/control.py",
    """    env_state = resolve_control_state(params, "env")

    if not cfg.get("LIGHT_SUN_ENABLED", 0):
""",
    """    env_state = resolve_control_state(params, "env")

    from core.capability_routing import controller_assignment_for_config
    light_controller_assignment = controller_assignment_for_config(
        cfg,
        "light",
    )

    if (
        cfg.get("LIGHT_SUN_ENABLED", 0)
        and not isinstance(light_controller_assignment, dict)
    ):
        with rt.state_lock:
            st.live_state["light_sun_active"] = False
            st.live_state["light_sun_phase"] = "controller_required"
            st.live_state["light_sun_level"] = None
            st.live_state["light_sun_progress"] = 0.0

        apply_device_state("light", env_state, runtime=rt)
        return

    if not cfg.get("LIGHT_SUN_ENABLED", 0):
""",
    "Runtime fällt ohne Lichtcontroller auf normales ENV-Licht zurück",
)

replace_once(
    "templates/settings.html",
    """        <div class="card">
            <h2>☀️ Sonnenaufgang & Sonnenuntergang</h2>
""",
    """        <div class="card" id="light-sun-card">
            <h2>☀️ Sonnenaufgang & Sonnenuntergang</h2>
""",
    "Profilseite markiert Sonnenverlauf-Karte",
)

replace_once(
    "templates/settings.html",
    """            <div id="light-sun-preview" class="preview"></div>

            <div class="info warning">
""",
    """            <div id="light-sun-preview" class="preview"></div>

            <div id="light-sun-controller-note" class="info warning" style="display:none;"></div>

            <div class="info warning">
""",
    "Profilseite erhält Begründung bei fehlendem Controller",
)

replace_once(
    "templates/settings.html",
    """.card{
    background:var(--card);
    border:1px solid var(--border);
    border-radius:18px;
    padding:18px;
}
""",
    """.card{
    background:var(--card);
    border:1px solid var(--border);
    border-radius:18px;
    padding:18px;
}
.card.feature-unavailable{
    opacity:.58;
    filter:saturate(.45);
}
.card.feature-unavailable input,
.card.feature-unavailable button{
    cursor:not-allowed;
}
""",
    "Profilseite graut nicht verfügbare Feature-Karte aus",
)

replace_once(
    "templates/settings.html",
    """const PROFILE_URL = name => `/api/tents/${encodeURIComponent(TENT_ID)}/profile/${encodeURIComponent(name)}`;

const ids = [
""",
    """const PROFILE_URL = name => `/api/tents/${encodeURIComponent(TENT_ID)}/profile/${encodeURIComponent(name)}`;

let lightSunAvailable = false;
let lightSunUnavailableReason = "";

const ids = [
""",
    "Profilseite hält Sonnenverlauf-Verfügbarkeitsstatus",
)

replace_once(
    "templates/settings.html",
    """async function load(){
""",
    """function applyLightSunAvailability(payload){
    lightSunAvailable = !!payload.light_sun_available;
    lightSunUnavailableReason =
        payload.light_sun_unavailable_reason ||
        "Kein Licht-Controller zugewiesen.";

    const card = el("light-sun-card");
    const note = el("light-sun-controller-note");
    const fieldIds = [
        "LIGHT_SUN_ENABLED",
        "LIGHT_SUNRISE_DURATION_MIN",
        "LIGHT_SUNSET_DURATION_MIN",
        "LIGHT_SUN_MIN_LEVEL"
    ];

    if(card){
        card.classList.toggle("feature-unavailable", !lightSunAvailable);
        card.querySelectorAll(".num-control button").forEach(button=>{
            button.disabled = !lightSunAvailable;
        });
    }

    fieldIds.forEach(id=>{
        const input = el(id);
        if(input) input.disabled = !lightSunAvailable;
    });

    if(note){
        if(lightSunAvailable){
            note.style.display = "none";
            note.textContent = "";
        }else{
            note.style.display = "block";
            note.innerHTML =
                `<strong>Nicht verfügbar:</strong> ${lightSunUnavailableReason}`;
        }
    }

    if(!lightSunAvailable && el("LIGHT_SUN_ENABLED")){
        el("LIGHT_SUN_ENABLED").checked = false;
    }
}


async function load(){
""",
    "Profilseite kann Sonnenverlauf deaktivieren und ausgrauen",
)

replace_once(
    "templates/settings.html",
    """    const c = payload.config || payload;

    for(const id of ids){
""",
    """    const c = payload.config || payload;

    applyLightSunAvailability(payload);

    for(const id of ids){
""",
    "Profilseite prüft Verfügbarkeit beim Laden",
)

replace_once(
    "templates/settings.html",
    """    el("LIGHT_SUN_ENABLED").checked = !!c.LIGHT_SUN_ENABLED;
""",
    """    el("LIGHT_SUN_ENABLED").checked =
        lightSunAvailable && !!c.LIGHT_SUN_ENABLED;
""",
    "Profilseite lässt Schalter ohne Controller AUS",
)

replace_once(
    "templates/settings.html",
    """        LIGHT_SUN_ENABLED:el("LIGHT_SUN_ENABLED").checked ? 1 : 0,
""",
    """        LIGHT_SUN_ENABLED:(
            lightSunAvailable &&
            el("LIGHT_SUN_ENABLED").checked
        ) ? 1 : 0,
""",
    "Profilseite sendet ohne Controller niemals Aktiv=1",
)

replace_once(
    "templates/settings.html",
    """    const c = payload.config || body;
    applyLimits(c);
""",
    """    const c = payload.config || body;
    applyLightSunAvailability(payload);
    applyLimits(c);
""",
    "Profilseite übernimmt Verfügbarkeit nach Speichern",
)

replace_once(
    "templates/settings.html",
    """function step(id,delta){
    const input = el(id);
    if(!input) return;
""",
    """function step(id,delta){
    const input = el(id);
    if(!input) return;

    if(!lightSunAvailable && id.startsWith("LIGHT_SUN")){
        return;
    }
""",
    "Profilseite blockiert Sonnenparameter-Schritte ohne Controller",
)

print("✅ Growstar 3.14.1 / LIGHT.SUN.GUARD.1 vollständig angewendet")
