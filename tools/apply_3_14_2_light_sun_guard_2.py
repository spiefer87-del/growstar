#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "templates/settings.html"


def fail(message):
    raise SystemExit("❌ " + message)


def replace_once(text, old, new, label):
    if new in text:
        print(f"✅ {label}: bereits vorhanden")
        return text

    if old not in text:
        fail(f"{label}: erwarteter Anker nicht gefunden")

    print(f"✅ {label}")
    return text.replace(old, new, 1)


def require_file_marker(path, marker, label):
    p = ROOT / path
    if not p.exists():
        fail(f"{label}: Datei fehlt: {path}")

    text = p.read_text(encoding="utf-8")
    if marker not in text:
        fail(f"{label}: Marker fehlt in {path}")

    print(f"✅ {label}")


require_file_marker(
    "core/control.py",
    "calculate_light_sun_state",
    "LIGHT.SUN.1 Runtime ist installiert",
)

require_file_marker(
    "templates/settings.html",
    'id="LIGHT_SUN_ENABLED"',
    "Sonnenverlauf-Schalter ist vorhanden",
)

require_file_marker(
    "templates/settings.html",
    'id="light-sun-card"',
    "Guard-Karte aus 3.14.1 ist vorhanden",
)

require_file_marker(
    "templates/settings.html",
    'id="light-sun-controller-note"',
    "Guard-Hinweisfeld aus 3.14.1 ist vorhanden",
)

require_file_marker(
    "routes/tents.py",
    "def _light_sun_availability(runtime):",
    "Backend-Verfügbarkeitsprüfung aus 3.14.1 ist vorhanden",
)

require_file_marker(
    "routes/tents.py",
    "light_sun_controller_required",
    "Backend blockiert Aktivierung ohne Lichtcontroller",
)

text = SETTINGS.read_text(encoding="utf-8")

css = r"""
.card.feature-unavailable{
    opacity:.52;
    filter:grayscale(.28) saturate(.45);
    border-color:rgba(148,163,184,.12);
}
.card.feature-unavailable .info,
.card.feature-unavailable .preview{
    opacity:.82;
}
.card.feature-unavailable input,
.card.feature-unavailable button{
    cursor:not-allowed !important;
}
.card.feature-unavailable input:disabled,
.card.feature-unavailable button:disabled{
    opacity:.55;
}
"""

if ".card.feature-unavailable{" not in text:
    anchor = ".card h2{"
    if anchor not in text:
        fail("CSS-Reparatur: .card h2-Anker fehlt")

    text = text.replace(anchor, css + "\n" + anchor, 1)
    print("✅ CSS: Sonnenverlauf-Karte wird ausgegraut")
else:
    print("✅ CSS: Sonnenverlauf-Karte wird ausgegraut: bereits vorhanden")

text = replace_once(
    text,
    """const PROFILE_URL = name => `/api/tents/${encodeURIComponent(TENT_ID)}/profile/${encodeURIComponent(name)}`;

const ids = [
""",
    """const PROFILE_URL = name => `/api/tents/${encodeURIComponent(TENT_ID)}/profile/${encodeURIComponent(name)}`;

let lightSunAvailable = false;
let lightSunUnavailableReason = "";

const ids = [
""",
    "JS: Sonnenverlauf-Verfügbarkeitsstatus",
)

availability_fn = r"""function applyLightSunAvailability(payload){
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
        card.classList.toggle(
            "feature-unavailable",
            !lightSunAvailable
        );

        card.querySelectorAll(".num-control button").forEach(button=>{
            button.disabled = !lightSunAvailable;
        });
    }

    fieldIds.forEach(id=>{
        const input = el(id);

        if(input){
            input.disabled = !lightSunAvailable;
        }
    });

    if(note){
        if(lightSunAvailable){
            note.style.display = "none";
            note.textContent = "";
        }else{
            note.style.display = "block";
            note.innerHTML =
                "<strong>Nicht verfügbar:</strong> " +
                lightSunUnavailableReason;
        }
    }

    if(!lightSunAvailable){
        const toggle = el("LIGHT_SUN_ENABLED");

        if(toggle){
            toggle.checked = false;
        }
    }
}


"""

if "function applyLightSunAvailability(payload){" not in text:
    anchor = "async function load(){"

    if anchor not in text:
        fail("JS-Reparatur: load()-Anker fehlt")

    text = text.replace(anchor, availability_fn + anchor, 1)
    print("✅ JS: applyLightSunAvailability eingefügt")
else:
    print("✅ JS: applyLightSunAvailability: bereits vorhanden")

text = replace_once(
    text,
    """    const c = payload.config || payload;

    for(const id of ids){
""",
    """    const c = payload.config || payload;

    applyLightSunAvailability(payload);

    for(const id of ids){
""",
    "JS: Verfügbarkeit beim Laden anwenden",
)

text = replace_once(
    text,
    """    el("LIGHT_SUN_ENABLED").checked = !!c.LIGHT_SUN_ENABLED;
""",
    """    el("LIGHT_SUN_ENABLED").checked =
        lightSunAvailable && !!c.LIGHT_SUN_ENABLED;
""",
    "JS: Aktiv-Schalter bleibt ohne Controller AUS",
)

text = replace_once(
    text,
    """        LIGHT_SUN_ENABLED:el("LIGHT_SUN_ENABLED").checked ? 1 : 0,
""",
    """        LIGHT_SUN_ENABLED:(
            lightSunAvailable &&
            el("LIGHT_SUN_ENABLED").checked
        ) ? 1 : 0,
""",
    "JS: Speichern sendet ohne Controller niemals Aktiv=1",
)

text = replace_once(
    text,
    """    const c = payload.config || body;
    applyLimits(c);
""",
    """    const c = payload.config || body;
    applyLightSunAvailability(payload);
    applyLimits(c);
""",
    "JS: Verfügbarkeit nach Speichern erneut anwenden",
)

text = replace_once(
    text,
    """function step(id,delta){
    const input = el(id);
    if(!input) return;
""",
    """function step(id,delta){
    const input = el(id);
    if(!input) return;

    if(
        !lightSunAvailable &&
        id.startsWith("LIGHT_SUN")
    ){
        return;
    }
""",
    "JS: Plus/Minus ohne Controller blockieren",
)

SETTINGS.write_text(text, encoding="utf-8")

print("✅ Growstar 3.14.2 / LIGHT.SUN.GUARD.2 vollständig angewendet")
