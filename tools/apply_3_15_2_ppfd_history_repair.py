#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fail(message):
    raise SystemExit("❌ " + message)

def patch_once(path, old, new, label):
    p = ROOT / path
    if not p.exists():
        fail(f"{label}: Datei fehlt: {path}")
    text = p.read_text(encoding="utf-8")
    if new in text:
        print(f"✅ {label}: bereits vorhanden")
        return
    if old not in text:
        fail(f"{label}: erwarteter Codeblock fehlt in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("✅", label)

required = {
    "core/sensor_sources.py": "ppfd=None",
    "services/spiderfarmer.py": "ppfd=ppfd",
    "routes/tents.py": "def _assigned_spiderfarmer_ppfd(runtime):",
    "threads/main.py": "ppfd=ppfd_val",
    "db.py": 'ADD COLUMN ppfd REAL',
    "routes/diagrams.py": 'data_type == "ppfd"',
    "routes/dashboard.py": 'def grow_control_tent_ppfd',
    "templates/environment_history.html": 'data-metric="ppfd"',
}
for rel, marker in required.items():
    p = ROOT / rel
    if not p.exists() or marker not in p.read_text(encoding="utf-8"):
        fail(f"Voraussetzung fehlt oder ist unvollständig: {rel} / {marker}")
print("✅ Voraussetzungen erkannt")

patch_once(
    "core/sensor_sources.py",
    '''    if not field:
        if sensor_name == "temperature":
            field = "temperature"
        elif sensor_name == "humidity":
            field = "humidity"
''',
    '''    if not field:
        if sensor_name == "temperature":
            field = "temperature"
        elif sensor_name == "humidity":
            field = "humidity"
        elif sensor_name == "ppfd":
            field = "ppfd"
''',
    "PPFD-Feld erhält sicheren Default",
)

patch_once(
    "core/sensor_sources.py",
    '''    hum_raw, hum_source, hum_assignment = _read_assigned_value(
        "humidity",
        runtime=rt,
    )

    now = time.time()
    temp_last_seen = _source_last_seen(temp_source)
    hum_last_seen = _source_last_seen(hum_source)
    temp_fresh = temp_raw is not None and _source_is_fresh(temp_source, now)
    hum_fresh = hum_raw is not None and _source_is_fresh(hum_source, now)
''',
    '''    hum_raw, hum_source, hum_assignment = _read_assigned_value(
        "humidity",
        runtime=rt,
    )
    ppfd_raw, ppfd_source, ppfd_assignment = _read_assigned_value(
        "ppfd",
        runtime=rt,
    )

    if ppfd_raw is None:
        assignments = cfg.get("SENSOR_ASSIGNMENTS", {})
        for sensor_name in ("temperature", "humidity"):
            assignment = (assignments or {}).get(sensor_name) or {}
            source_id = str(assignment.get("source_id") or "").strip()
            if not source_id.startswith("spiderfarmer:"):
                continue
            candidate = get_sensor_source(source_id)
            if not isinstance(candidate, dict) or candidate.get("ppfd") is None:
                continue
            try:
                ppfd_raw = float(candidate.get("ppfd"))
            except (TypeError, ValueError):
                continue
            ppfd_source = candidate
            ppfd_assignment = {
                "source_id": source_id,
                "field": "ppfd",
                "label": candidate.get("label") or source_id,
            }
            break

    now = time.time()
    temp_last_seen = _source_last_seen(temp_source)
    hum_last_seen = _source_last_seen(hum_source)
    ppfd_last_seen = _source_last_seen(ppfd_source)
    temp_fresh = temp_raw is not None and _source_is_fresh(temp_source, now)
    hum_fresh = hum_raw is not None and _source_is_fresh(hum_source, now)
    ppfd_fresh = ppfd_raw is not None and _source_is_fresh(ppfd_source, now)
''',
    "Stationszuweisung liest PPFD",
)

patch_once(
    "core/sensor_sources.py",
    '''        if hum_fresh:
            hum_offset = float(cfg.get("HUM_OFFSET", 0.0))
            hum = hum_raw + hum_offset

            st.live_state["hum_raw"] = hum_raw
            st.live_state["hum"] = hum

            st.last_hum_raw = hum_raw
            st.last_hum = hum
            st.hum_stale = False

            st.live_state["hum_source"] = (
                hum_assignment.get("label")
                or (hum_source or {}).get("label")
                or hum_assignment.get("source_id")
            )

            changed = True

        st.live_state["vpd"] = _calculate_vpd(
''',
    '''        if hum_fresh:
            hum_offset = float(cfg.get("HUM_OFFSET", 0.0))
            hum = hum_raw + hum_offset

            st.live_state["hum_raw"] = hum_raw
            st.live_state["hum"] = hum

            st.last_hum_raw = hum_raw
            st.last_hum = hum
            st.hum_stale = False

            st.live_state["hum_source"] = (
                hum_assignment.get("label")
                or (hum_source or {}).get("label")
                or hum_assignment.get("source_id")
            )

            changed = True

        if ppfd_fresh:
            st.live_state["light_ppfd"] = ppfd_raw
            st.live_state["light_ppfd_source"] = {
                "source_id": ppfd_assignment.get("source_id"),
                "label": (
                    ppfd_assignment.get("label")
                    or (ppfd_source or {}).get("label")
                    or ppfd_assignment.get("source_id")
                ),
                "last_seen": ppfd_last_seen,
            }
            changed = True
        else:
            st.live_state.pop("light_ppfd", None)
            st.live_state.pop("light_ppfd_source", None)

        st.live_state["vpd"] = _calculate_vpd(
''',
    "Frisches PPFD wird in den Tent-Live-State projiziert",
)

patch_once(
    "routes/tents.py",
    '''    safety = get_runtime_safety_snapshot(runtime)
    light_ppfd, light_ppfd_source = _assigned_spiderfarmer_ppfd(runtime)

    devices = {}
''',
    '''    safety = get_runtime_safety_snapshot(runtime)

    light_ppfd = live.get("light_ppfd")
    light_ppfd_source = live.get("light_ppfd_source")
    if light_ppfd is None:
        light_ppfd, light_ppfd_source = _assigned_spiderfarmer_ppfd(runtime)

    devices = {}
''',
    "Tent-State bevorzugt Runtime-PPFD",
)

grow = ROOT / "templates/grow_control.html"
html = grow.read_text(encoding="utf-8")

old_card = '''<div class="card-link ppfd-card-shell" id="light-level-link">
        <div class="card env" id="light-level-card">
            <h2>Helligkeit</h2>
            <div class="value ppfd-value"><span id="light-level">---</span></div>
            <div class="sub ppfd-unit">µmol/m²/s</div>
        </div>
    </div>'''
new_card = '''<a href="{{ url_for('grow_control_tent_ppfd', tent_id=tent_id) }}" class="card-link ppfd-card-shell" id="light-level-link">
        <div class="card env" id="light-level-card">
            <h2>Helligkeit</h2>
            <div class="value ppfd-value"><span id="light-level">---</span></div>
            <div class="sub ppfd-unit">µmol/m²/s</div>
        </div>
    </a>'''

if new_card not in html:
    if old_card not in html:
        fail("Dashboard: erwartete Helligkeitskachel nicht gefunden")
    html = html.replace(old_card, new_card, 1)
    print("✅ Helligkeits-Kachel sicher klickbar gemacht")

old_js = '''            safeText("hum-soll", formatNumber(state.hum_target, 1));
            safeText("vpd", formatNumber(state.vpd, 2));

            const ramp = document.getElementById("temp-ramp");'''
new_js = '''            safeText("hum-soll", formatNumber(state.hum_target, 1));
            safeText("vpd", formatNumber(state.vpd, 2));
            safeText(
                "light-level",
                Number.isFinite(Number(state.light_ppfd))
                    ? String(Math.round(Number(state.light_ppfd)))
                    : "---"
            );

            const ramp = document.getElementById("temp-ramp");'''

if new_js not in html:
    if old_js not in html:
        fail("Dashboard: Live-State-Anker für PPFD fehlt")
    html = html.replace(old_js, new_js, 1)
    print("✅ Dashboard aktualisiert Helligkeitswert live")

for marker in (
    'id="device-grid"',
    'id="heating-card"',
    'id="fan-card"',
    'id="light-card"',
    'id="vent-card"',
    'id="dehumidifier-card"',
    'function collectCards()',
    'function renderDashboard()',
):
    if marker not in html:
        fail(f"Dashboard-Strukturguard fehlgeschlagen: {marker}")

grow.write_text(html, encoding="utf-8")
print("✅ Geräte-Dashboard vollständig erhalten")

patch_once(
    "templates/environment_history.html",
    '''.toolbar{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}.range-bar,.chart-actions{display:flex;gap:7px;flex-wrap:wrap}.pill{border:1px solid var(--border);padding:8px 12px;border-radius:999px;background:var(--card2);color:var(--text);cursor:pointer;font-size:.84rem;font-weight:700}.pill.active{background:var(--accent);border-color:var(--accent);color:#022c22}.pill:disabled{display:none}''',
    '''.toolbar{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}.range-bar,.chart-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center}.pill{border:1px solid var(--border);padding:8px 12px;border-radius:999px;background:var(--card2);color:var(--text);cursor:pointer;font-size:.84rem;font-weight:700}.pill.active{background:var(--accent);border-color:var(--accent);color:#022c22}.pill:disabled{display:none}.station-select{min-height:36px;max-width:210px;border:1px solid var(--border);border-radius:999px;background:var(--card2);color:var(--text);padding:7px 34px 7px 12px;font-size:.84rem;font-weight:700;cursor:pointer;outline:none}''',
    "Diagramm-Stationsauswahl Styling",
)

patch_once(
    "templates/environment_history.html",
    '''</div><div class="chart-actions"><button id="toggle-target" class="pill" onclick="toggleTarget()">Sollwert ausblenden</button></div></div>''',
    '''</div><div class="chart-actions"><select id="station-select" class="station-select" aria-label="Station wechseln" onchange="changeStation(this.value)"><option value="{{ tent_id }}">{{ tent_name }}</option></select><button id="toggle-target" class="pill" onclick="toggleTarget()">Sollwert ausblenden</button></div></div>''',
    "Stationsauswahl neben Sollwert-Schalter",
)

patch_once(
    "templates/environment_history.html",
    '''function metricUrl(m){const b=`/grow-control/tents/${encodeURIComponent(TENT_ID)}`;return m==="temp"?`${b}/temperature`:m==="hum"?`${b}/humidity`:m==="vpd"?`${b}/vpd`:`${b}/ppfd`}
function selectMetric(m){if(!METRICS[m]||m===metric)return;metric=m;updateTabs();updateHeader();history.replaceState(null,"",metricUrl(metric));load()}''',
    '''function metricUrlForTent(tentId,m){const b=`/grow-control/tents/${encodeURIComponent(tentId)}`;return m==="temp"?`${b}/temperature`:m==="hum"?`${b}/humidity`:m==="vpd"?`${b}/vpd`:`${b}/ppfd`}
function metricUrl(m){return metricUrlForTent(TENT_ID,m)}
function selectMetric(m){if(!METRICS[m]||m===metric)return;metric=m;updateTabs();updateHeader();history.replaceState(null,"",metricUrl(metric));load()}
function changeStation(tentId){if(!tentId||tentId===TENT_ID)return;window.location.href=metricUrlForTent(tentId,metric)}
async function loadStations(){const select=byId("station-select");if(!select)return;try{const res=await fetch("/api/tents",{cache:"no-store"});if(!res.ok)throw new Error(`HTTP ${res.status}`);const payload=await res.json();const tents=Array.isArray(payload.tents)?payload.tents:[];if(!tents.length)return;select.innerHTML="";tents.forEach(tent=>{if(!tent||!tent.id)return;const option=document.createElement("option");option.value=tent.id;option.textContent=tent.name||tent.id;option.selected=tent.id===TENT_ID;option.disabled=tent.runtime_loaded===false;select.appendChild(option)})}catch(error){console.warn("Stationsliste konnte nicht geladen werden",error)}}''',
    "Diagramm-Stationswechsel Logik",
)

patch_once(
    "templates/environment_history.html",
    '''updateTabs();updateHeader();load();setInterval(load,60000);''',
    '''updateTabs();updateHeader();loadStations();load();setInterval(load,60000);''',
    "Diagramm lädt Stationsliste",
)

print("✅ Growstar 3.15.2 / PPFD.HISTORY.REPAIR vollständig angewendet")
