#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if new in text:
        print(f'✅ {label}: bereits angewendet')
        return
    if old not in text:
        raise SystemExit(f'❌ {label}: erwarteter Codeblock nicht gefunden in {path}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'✅ {label}')

# Der installierte Stand 3.13.11 ist Voraussetzung.
required = {
    'core/sensor_sources.py': 'ppfd=None',
    'routes/sensors.py': 'assignments["ppfd"]',
    'templates/sensoren.html': 'id="ppfd-source"',
}
for rel, marker in required.items():
    p = ROOT / rel
    if not p.exists() or marker not in p.read_text(encoding='utf-8'):
        raise SystemExit(f'❌ Voraussetzung 3.13.11 fehlt/unvollständig: {rel}')

REPLACEMENTS = [('core/config.py',
  '    "RAMP_DURATION_MIN": 60,\n    "RAMP_ENABLED": 0,\n\n    "SENSOR_ASSIGNMENTS": {',
  '    "RAMP_DURATION_MIN": 60,\n'
  '    "RAMP_ENABLED": 0,\n'
  '\n'
  '    # ================= LICHT · SONNENVERLAUF =================\n'
  '    "LIGHT_SUN_ENABLED": 0,\n'
  '    "LIGHT_SUNRISE_DURATION_MIN": 30,\n'
  '    "LIGHT_SUNSET_DURATION_MIN": 30,\n'
  '    "LIGHT_SUN_MIN_LEVEL": 11,\n'
  '\n'
  '    "SENSOR_ASSIGNMENTS": {',
  'Config: Sonnenverlauf-Defaults'),
 ('core/config_update.py',
  '    "RAMP_DURATION_MIN",\n    "RAMP_ENABLED",\n    "SENSOR_UPDATE_INTERVAL_SEC",',
  '    "RAMP_DURATION_MIN",\n'
  '    "RAMP_ENABLED",\n'
  '    "LIGHT_SUN_ENABLED",\n'
  '    "LIGHT_SUNRISE_DURATION_MIN",\n'
  '    "LIGHT_SUNSET_DURATION_MIN",\n'
  '    "LIGHT_SUN_MIN_LEVEL",\n'
  '    "SENSOR_UPDATE_INTERVAL_SEC",',
  'Config-Update: Sonnenverlauf-Ganzzahlen'),
 ('core/control.py',
  'from core.ramp import get_ramped_target\nfrom core.helpers import minutes_now, in_time_window\n',
  'from core.ramp import get_ramped_target\n'
  'from core.light_sun import calculate_light_sun_state\n'
  'from core.helpers import minutes_now, in_time_window\n',
  'Control: Sonnenverlauf importieren'),
 ('routes/tents.py',
  '        "ramp_target": live.get("ramp_target"),\n\n        # Sensorzustand',
  '        "ramp_target": live.get("ramp_target"),\n'
  '\n'
  '        # Licht · Sonnenverlauf\n'
  '        "light_sun_enabled": bool(cfg.get("LIGHT_SUN_ENABLED", 0)),\n'
  '        "light_sun_active": bool(live.get("light_sun_active")),\n'
  '        "light_sun_phase": live.get("light_sun_phase"),\n'
  '        "light_sun_level": live.get("light_sun_level"),\n'
  '        "light_sun_progress": live.get("light_sun_progress"),\n'
  '\n'
  '        # Sensorzustand',
  'Tent-State: Sonnenverlauf-Status'),
 ('core/control.py',
  'def control_light_profile(runtime=None):\n'
  '    rt = resolve_runtime(runtime)\n'
  '    cfg = rt.config\n'
  '\n'
  '    now_min = minutes_now()\n'
  '    day_start = int(cfg.get("DAY_START_MIN", 360))\n'
  '    night_start = int(cfg.get("NIGHT_START_MIN", 1320))\n'
  '\n'
  '    light_on = in_time_window(now_min, day_start, night_start)\n'
  '    params = get_device_params("light", runtime=rt)\n'
  '    state_name = "env" if light_on else "off"\n'
  '    apply_device_state(\n'
  '        "light",\n'
  '        resolve_control_state(params, state_name),\n'
  '        runtime=rt,\n'
  '    )\n',
  'def control_light_profile(runtime=None):\n'
  '    """Profillicht mit optionalem Sonnenaufgang/Sonnenuntergang."""\n'
  '\n'
  '    rt = resolve_runtime(runtime)\n'
  '    cfg = rt.config\n'
  '    st = rt.state\n'
  '\n'
  '    now_min = minutes_now()\n'
  '    day_start = int(cfg.get("DAY_START_MIN", 360))\n'
  '    night_start = int(cfg.get("NIGHT_START_MIN", 1320))\n'
  '\n'
  '    light_on = in_time_window(now_min, day_start, night_start)\n'
  '    params = get_device_params("light", runtime=rt)\n'
  '\n'
  '    if not light_on:\n'
  '        with rt.state_lock:\n'
  '            st.live_state["light_sun_active"] = False\n'
  '            st.live_state["light_sun_phase"] = "night"\n'
  '            st.live_state["light_sun_level"] = None\n'
  '            st.live_state["light_sun_progress"] = 0.0\n'
  '        apply_device_state(\n'
  '            "light",\n'
  '            resolve_control_state(params, "off"),\n'
  '            runtime=rt,\n'
  '        )\n'
  '        return\n'
  '\n'
  '    env_state = resolve_control_state(params, "env")\n'
  '\n'
  '    if not cfg.get("LIGHT_SUN_ENABLED", 0):\n'
  '        with rt.state_lock:\n'
  '            st.live_state["light_sun_active"] = False\n'
  '            st.live_state["light_sun_phase"] = "disabled"\n'
  '            st.live_state["light_sun_level"] = None\n'
  '            st.live_state["light_sun_progress"] = 0.0\n'
  '        apply_device_state("light", env_state, runtime=rt)\n'
  '        return\n'
  '\n'
  '    controller = dict(env_state.get("controller") or {})\n'
  '    target_level = controller.get("level")\n'
  '\n'
  '    # Kein gespeicherter dimmbarer ENV-Level: altes EIN/AUS-Verhalten behalten.\n'
  '    if target_level is None:\n'
  '        with rt.state_lock:\n'
  '            st.live_state["light_sun_active"] = False\n'
  '            st.live_state["light_sun_phase"] = "no_level_controller"\n'
  '            st.live_state["light_sun_level"] = None\n'
  '            st.live_state["light_sun_progress"] = 0.0\n'
  '        apply_device_state("light", env_state, runtime=rt)\n'
  '        return\n'
  '\n'
  '    sun = calculate_light_sun_state(\n'
  '        now_min=now_min,\n'
  '        day_start=day_start,\n'
  '        night_start=night_start,\n'
  '        sunrise_duration=cfg.get("LIGHT_SUNRISE_DURATION_MIN", 30),\n'
  '        sunset_duration=cfg.get("LIGHT_SUNSET_DURATION_MIN", 30),\n'
  '        min_level=cfg.get("LIGHT_SUN_MIN_LEVEL", 11),\n'
  '        target_level=target_level,\n'
  '    )\n'
  '\n'
  '    if not sun["on"]:\n'
  '        apply_device_state(\n'
  '            "light",\n'
  '            resolve_control_state(params, "off"),\n'
  '            runtime=rt,\n'
  '        )\n'
  '        return\n'
  '\n'
  '    controller["level"] = int(sun["level"])\n'
  '    env_state = dict(env_state)\n'
  '    env_state["controller"] = controller\n'
  '\n'
  '    with rt.state_lock:\n'
  '        st.live_state["light_sun_active"] = True\n'
  '        st.live_state["light_sun_phase"] = sun["phase"]\n'
  '        st.live_state["light_sun_level"] = int(sun["level"])\n'
  '        st.live_state["light_sun_progress"] = sun["progress"]\n'
  '\n'
  '    apply_device_state("light", env_state, runtime=rt)\n',
  'Control: Licht-Sonnenverlauf'),
 ('templates/settings.html',
  '        <div class="card">\n'
  '            <h2>⏱️ Rampe</h2>\n'
  '            <div class="row-inline">\n'
  '                <div class="field">\n'
  '                    <label>Aktiv</label>\n'
  '                    <input type="checkbox" id="RAMP_ENABLED">\n'
  '                </div>\n'
  '                <div class="field">\n'
  '                    <label>Dauer (min)</label>\n'
  '                    <div class="num-control">\n'
  '                        <button type="button" onclick="step(\'RAMP_DURATION_MIN\',-5)">−</button>\n'
  '                        <input type="number" step="10" id="RAMP_DURATION_MIN" class="compact-input">\n'
  '                        <button type="button" onclick="step(\'RAMP_DURATION_MIN\',5)">+</button>\n'
  '                    </div>\n'
  '                </div>\n'
  '            </div>\n'
  '        </div>\n',
  '        <div class="card">\n'
  '            <h2>⏱️ Rampe</h2>\n'
  '            <div class="row-inline">\n'
  '                <div class="field">\n'
  '                    <label>Aktiv</label>\n'
  '                    <input type="checkbox" id="RAMP_ENABLED">\n'
  '                </div>\n'
  '                <div class="field">\n'
  '                    <label>Dauer (min)</label>\n'
  '                    <div class="num-control">\n'
  '                        <button type="button" onclick="step(\'RAMP_DURATION_MIN\',-5)">−</button>\n'
  '                        <input type="number" step="10" id="RAMP_DURATION_MIN" class="compact-input">\n'
  '                        <button type="button" onclick="step(\'RAMP_DURATION_MIN\',5)">+</button>\n'
  '                    </div>\n'
  '                </div>\n'
  '            </div>\n'
  '        </div>\n'
  '\n'
  '        <div class="card">\n'
  '            <h2>☀️ Sonnenaufgang & Sonnenuntergang</h2>\n'
  '\n'
  '            <div class="info">\n'
  '                Funktion für <strong>Beleuchtung im Modus Umgebung</strong>.\n'
  '                Der bereits eingestellte ENV-Lichtlevel bleibt die maximale Tagesleistung.\n'
  '                Power / AUS bleibt weiterhin beim Shelly.\n'
  '            </div>\n'
  '\n'
  '            <div class="row-inline">\n'
  '                <div class="field">\n'
  '                    <label>Aktiv</label>\n'
  '                    <input type="checkbox" id="LIGHT_SUN_ENABLED">\n'
  '                </div>\n'
  '\n'
  '                <div class="field">\n'
  '                    <label>Sonnenaufgang (min)</label>\n'
  '                    <div class="num-control">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUNRISE_DURATION_MIN\',-5)">−</button>\n'
  '                        <input type="number" step="5" id="LIGHT_SUNRISE_DURATION_MIN" class="compact-input">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUNRISE_DURATION_MIN\',5)">+</button>\n'
  '                    </div>\n'
  '                </div>\n'
  '\n'
  '                <div class="field">\n'
  '                    <label>Sonnenuntergang (min)</label>\n'
  '                    <div class="num-control">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUNSET_DURATION_MIN\',-5)">−</button>\n'
  '                        <input type="number" step="5" id="LIGHT_SUNSET_DURATION_MIN" class="compact-input">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUNSET_DURATION_MIN\',5)">+</button>\n'
  '                    </div>\n'
  '                </div>\n'
  '\n'
  '                <div class="field">\n'
  '                    <label>Start-/Endleistung %</label>\n'
  '                    <div class="num-control">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUN_MIN_LEVEL\',-1)">−</button>\n'
  '                        <input type="number" step="1" id="LIGHT_SUN_MIN_LEVEL" class="compact-input">\n'
  '                        <button type="button" onclick="step(\'LIGHT_SUN_MIN_LEVEL\',1)">+</button>\n'
  '                    </div>\n'
  '                </div>\n'
  '            </div>\n'
  '\n'
  '            <div id="light-sun-preview" class="preview"></div>\n'
  '\n'
  '            <div class="info warning">\n'
  '                Tag Start = Beginn Sonnenaufgang. Nacht Start = Ende Sonnenuntergang / Licht AUS.\n'
  '                Bei deaktivierter Funktion arbeitet das Licht exakt wie bisher.\n'
  '            </div>\n'
  '        </div>\n',
  'Profilseite: Sonnenverlauf-Karte'),
 ('templates/settings.html',
  '    "MIN_TEMP","MAX_TEMP","MIN_HUM","MAX_HUM",\n    "RAMP_DURATION_MIN"\n];',
  '    "MIN_TEMP","MAX_TEMP","MIN_HUM","MAX_HUM",\n'
  '    "RAMP_DURATION_MIN",\n'
  '    "LIGHT_SUNRISE_DURATION_MIN","LIGHT_SUNSET_DURATION_MIN",\n'
  '    "LIGHT_SUN_MIN_LEVEL"\n'
  '];',
  'Profilseite: Sonnenfelder laden'),
 ('templates/settings.html',
  '    el("RAMP_DURATION_MIN").min = 5;\n    el("RAMP_DURATION_MIN").max = 240;\n}',
  '    el("RAMP_DURATION_MIN").min = 5;\n'
  '    el("RAMP_DURATION_MIN").max = 240;\n'
  '\n'
  '    el("LIGHT_SUNRISE_DURATION_MIN").min = 0;\n'
  '    el("LIGHT_SUNRISE_DURATION_MIN").max = 240;\n'
  '    el("LIGHT_SUNSET_DURATION_MIN").min = 0;\n'
  '    el("LIGHT_SUNSET_DURATION_MIN").max = 240;\n'
  '    el("LIGHT_SUN_MIN_LEVEL").min = 11;\n'
  '    el("LIGHT_SUN_MIN_LEVEL").max = 100;\n'
  '}',
  'Profilseite: Grenzen'),
 ('templates/settings.html',
  '    el("RAMP_ENABLED").checked = !!c.RAMP_ENABLED;\n    updateLightingDuration();',
  '    el("RAMP_ENABLED").checked = !!c.RAMP_ENABLED;\n'
  '    el("LIGHT_SUN_ENABLED").checked = !!c.LIGHT_SUN_ENABLED;\n'
  '    updateLightingDuration();',
  'Profilseite: Schalter laden'),
 ('templates/settings.html',
  '        NIGHT_START_MIN:timeToMin(el("NIGHT_START_TIME").value),\n'
  '        RAMP_ENABLED:el("RAMP_ENABLED").checked ? 1 : 0,\n'
  '        RAMP_DURATION_MIN:num("RAMP_DURATION_MIN")\n'
  '    };',
  '        NIGHT_START_MIN:timeToMin(el("NIGHT_START_TIME").value),\n'
  '        RAMP_ENABLED:el("RAMP_ENABLED").checked ? 1 : 0,\n'
  '        RAMP_DURATION_MIN:num("RAMP_DURATION_MIN"),\n'
  '        LIGHT_SUN_ENABLED:el("LIGHT_SUN_ENABLED").checked ? 1 : 0,\n'
  '        LIGHT_SUNRISE_DURATION_MIN:num("LIGHT_SUNRISE_DURATION_MIN"),\n'
  '        LIGHT_SUNSET_DURATION_MIN:num("LIGHT_SUNSET_DURATION_MIN"),\n'
  '        LIGHT_SUN_MIN_LEVEL:num("LIGHT_SUN_MIN_LEVEL")\n'
  '    };',
  'Profilseite: Sonnenverlauf speichern'),
 ('templates/settings.html',
  '    el("hum-preview").innerHTML = `\n'
  '        <strong>Luftfeuchtigkeit</strong><br>\n'
  '        Tag Regelbereich: ${band(num("DAY_HUM"),num("DAY_HUM_TOL"),"%")}<br>\n'
  '        Tag Alarm ab: ≤ ${(num("DAY_HUM")-num("HUM_ALERT_TOL")).toFixed(1)} %\n'
  '        oder ≥ ${(num("DAY_HUM")+num("HUM_ALERT_TOL")).toFixed(1)} %<br>\n'
  '        Nacht Regelbereich: ${band(num("NIGHT_HUM"),num("NIGHT_HUM_TOL"),"%")}<br>\n'
  '        Nacht Alarm ab: ≤ ${(num("NIGHT_HUM")-num("HUM_ALERT_TOL")).toFixed(1)} %\n'
  '        oder ≥ ${(num("NIGHT_HUM")+num("HUM_ALERT_TOL")).toFixed(1)} %<br>\n'
  '        Absolute Alarmgrenze: ${num("MIN_HUM").toFixed(1)} bis ${num("MAX_HUM").toFixed(1)} %\n'
  '    `;\n'
  '}',
  '    el("hum-preview").innerHTML = `\n'
  '        <strong>Luftfeuchtigkeit</strong><br>\n'
  '        Tag Regelbereich: ${band(num("DAY_HUM"),num("DAY_HUM_TOL"),"%")}<br>\n'
  '        Tag Alarm ab: ≤ ${(num("DAY_HUM")-num("HUM_ALERT_TOL")).toFixed(1)} %\n'
  '        oder ≥ ${(num("DAY_HUM")+num("HUM_ALERT_TOL")).toFixed(1)} %<br>\n'
  '        Nacht Regelbereich: ${band(num("NIGHT_HUM"),num("NIGHT_HUM_TOL"),"%")}<br>\n'
  '        Nacht Alarm ab: ≤ ${(num("NIGHT_HUM")-num("HUM_ALERT_TOL")).toFixed(1)} %\n'
  '        oder ≥ ${(num("NIGHT_HUM")+num("HUM_ALERT_TOL")).toFixed(1)} %<br>\n'
  '        Absolute Alarmgrenze: ${num("MIN_HUM").toFixed(1)} bis ${num("MAX_HUM").toFixed(1)} %\n'
  '    `;\n'
  '\n'
  '    const sunBox = el("light-sun-preview");\n'
  '    if(sunBox){\n'
  '        const active = !!el("LIGHT_SUN_ENABLED")?.checked;\n'
  '        const dayStart = el("DAY_START_TIME")?.value || "--:--";\n'
  '        const nightStart = el("NIGHT_START_TIME")?.value || "--:--";\n'
  '        const rise = num("LIGHT_SUNRISE_DURATION_MIN");\n'
  '        const sunset = num("LIGHT_SUNSET_DURATION_MIN");\n'
  '        const minimum = num("LIGHT_SUN_MIN_LEVEL");\n'
  '\n'
  '        sunBox.innerHTML = active\n'
  '            ? `<strong>Sonnenverlauf aktiv</strong><br>\n'
  '               ${dayStart}: EIN bei ${minimum.toFixed(0)} % · Hochdimmen ${rise.toFixed(0)} Min.<br>\n'
  '               Tagesleistung: vorhandener ENV-Lichtlevel<br>\n'
  '               Herunterdimmen ${sunset.toFixed(0)} Min. vor ${nightStart}<br>\n'
  '               ${nightStart}: Licht AUS`\n'
  '            : `<strong>Sonnenverlauf deaktiviert</strong><br>\n'
  '               Bisherige Profil-EIN/AUS-Steuerung bleibt aktiv.`;\n'
  '    }\n'
  '}',
  'Profilseite: Sonnenverlauf-Vorschau'),
 ('templates/settings.html',
  '["DAY_START_TIME","NIGHT_START_TIME"].forEach(id=>{\n'
  '    el(id)?.addEventListener("input",updateLightingDuration);\n'
  '});',
  '["DAY_START_TIME","NIGHT_START_TIME"].forEach(id=>{\n'
  '    el(id)?.addEventListener("input",()=>{\n'
  '        updateLightingDuration();\n'
  '        updatePreview();\n'
  '    });\n'
  '});',
  'Profilseite: Zeitvorschau aktualisieren'),
 ('templates/settings.html',
  'document.querySelectorAll("input").forEach(input=>{\n'
  '    input.addEventListener("change",save);\n'
  '    if(input.type === "number") input.addEventListener("input",updatePreview);\n'
  '});',
  'document.querySelectorAll("input").forEach(input=>{\n'
  '    input.addEventListener("change",save);\n'
  '    if(input.type === "number") input.addEventListener("input",updatePreview);\n'
  '    if(input.id === "LIGHT_SUN_ENABLED") input.addEventListener("input",updatePreview);\n'
  '});',
  'Profilseite: Schaltervorschau')]

for item in REPLACEMENTS:
    replace_once(*item)

print('✅ Growstar 3.14.0 / LIGHT.SUN.1 vollständig angewendet')
