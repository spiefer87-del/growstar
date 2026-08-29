#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def fail(msg):
    raise SystemExit("❌ " + msg)

def replace_once(path, old, new, label):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if new in text:
        print(f"✅ {label}: bereits vorhanden")
        return
    if old not in text:
        fail(f"{label}: erwarteter Codeblock fehlt in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("✅", label)

for path, marker, label in (
    ("routes/tents.py", '"light_ppfd"', "PPFD-State vorhanden"),
    ("templates/grow_control.html", 'id="light-level-card"', "Helligkeits-Kachel vorhanden"),
):
    p = ROOT / path
    if not p.exists() or marker not in p.read_text(encoding="utf-8"):
        fail(f"{label}: Voraussetzung fehlt")
    print("✅", label)

REPLACEMENTS = [('db.py',
  '    if "vpd" not in existing_cols:\n'
  '        c.execute("ALTER TABLE temp_history ADD COLUMN vpd REAL")\n'
  '\n'
  '    c.execute(\n',
  '    if "vpd" not in existing_cols:\n'
  '        c.execute("ALTER TABLE temp_history ADD COLUMN vpd REAL")\n'
  '\n'
  '    if "ppfd" not in existing_cols:\n'
  '        c.execute("ALTER TABLE temp_history ADD COLUMN ppfd REAL")\n'
  '\n'
  '    c.execute(\n',
  'DB-Migration ergänzt PPFD'),
 ('db.py',
  '    vpd=None,\n    tent_id=DEFAULT_TENT_ID,\n):\n',
  '    vpd=None,\n    ppfd=None,\n    tent_id=DEFAULT_TENT_ID,\n):\n',
  'insert_measurement akzeptiert PPFD'),
 ('db.py',
  '            hum_target,\n            vpd\n        )\n        VALUES (?, ?, ?, ?, ?, ?, ?)\n',
  '            hum_target,\n'
  '            vpd,\n'
  '            ppfd\n'
  '        )\n'
  '        VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n',
  'DB-Insert schreibt PPFD-Spalte'),
 ('db.py',
  '            hum,\n            hum_target,\n            vpd\n        )\n',
  '            hum,\n            hum_target,\n            vpd,\n            ppfd\n        )\n',
  'DB-Insert bindet PPFD-Wert'),
 ('threads/main.py',
  '    with rt.state_lock:\n'
  '        temp_val = st.live_state.get("temp")\n'
  '        hum_val = st.live_state.get("hum")\n',
  '    with rt.state_lock:\n'
  '        temp_val = st.live_state.get("temp")\n'
  '        hum_val = st.live_state.get("hum")\n'
  '        ppfd_val = st.live_state.get("light_ppfd")\n',
  'Regelzyklus liest PPFD-Livewert'),
 ('threads/main.py',
  '        if temp_val is not None and hum_val is not None:\n'
  '            vpd = calculate_vpd(temp_val, hum_val)\n'
  '\n'
  '            with rt.state_lock:\n'
  '                st.live_state["vpd"] = vpd\n'
  '\n'
  '            try:\n'
  '                insert_measurement(\n'
  '                    temp=temp_val,\n'
  '                    temp_target=temp_target,\n'
  '                    hum=hum_val,\n'
  '                    hum_target=hum_target,\n'
  '                    vpd=vpd,\n'
  '                    tent_id=rt.tent_id,\n'
  '                )\n'
  '            except Exception as exc:\n'
  '                print(\n'
  '                    f"❌ [{rt.tent_id}] DB insert_measurement Fehler:",\n'
  '                    exc,\n'
  '                )\n',
  '        vpd = None\n'
  '        if temp_val is not None and hum_val is not None:\n'
  '            vpd = calculate_vpd(temp_val, hum_val)\n'
  '\n'
  '            with rt.state_lock:\n'
  '                st.live_state["vpd"] = vpd\n'
  '\n'
  '        if any(value is not None for value in (temp_val, hum_val, ppfd_val)):\n'
  '            try:\n'
  '                insert_measurement(\n'
  '                    temp=temp_val,\n'
  '                    temp_target=temp_target,\n'
  '                    hum=hum_val,\n'
  '                    hum_target=hum_target,\n'
  '                    vpd=vpd,\n'
  '                    ppfd=ppfd_val,\n'
  '                    tent_id=rt.tent_id,\n'
  '                )\n'
  '            except Exception as exc:\n'
  '                print(\n'
  '                    f"❌ [{rt.tent_id}] DB insert_measurement Fehler:",\n'
  '                    exc,\n'
  '                )\n',
  'Historie speichert PPFD unabhängig von Temp/Hum'),
 ('routes/diagrams.py',
  '        if data_type == "vpd":\n'
  '            c.execute(\n'
  '                """\n'
  '                SELECT ts, vpd\n'
  '                FROM temp_history\n'
  '                WHERE tent_id = ? AND ts >= ?\n'
  '                ORDER BY ts ASC\n'
  '                """,\n'
  '                (tent_id, since),\n'
  '            )\n'
  '            return [\n'
  '                {"ts": r[0], "vpd": r[1]}\n'
  '                for r in c.fetchall()\n'
  '                if r[1] is not None\n'
  '            ]\n'
  '\n'
  '        return []\n',
  '        if data_type == "vpd":\n'
  '            c.execute(\n'
  '                """\n'
  '                SELECT ts, vpd\n'
  '                FROM temp_history\n'
  '                WHERE tent_id = ? AND ts >= ?\n'
  '                ORDER BY ts ASC\n'
  '                """,\n'
  '                (tent_id, since),\n'
  '            )\n'
  '            return [\n'
  '                {"ts": r[0], "vpd": r[1]}\n'
  '                for r in c.fetchall()\n'
  '                if r[1] is not None\n'
  '            ]\n'
  '\n'
  '        if data_type == "ppfd":\n'
  '            c.execute(\n'
  '                """\n'
  '                SELECT ts, ppfd\n'
  '                FROM temp_history\n'
  '                WHERE tent_id = ? AND ts >= ?\n'
  '                ORDER BY ts ASC\n'
  '                """,\n'
  '                (tent_id, since),\n'
  '            )\n'
  '            return [\n'
  '                {"ts": r[0], "ppfd": r[1]}\n'
  '                for r in c.fetchall()\n'
  '                if r[1] is not None\n'
  '            ]\n'
  '\n'
  '        return []\n',
  'History-API liefert PPFD'),
 ('routes/dashboard.py',
  '    @app.route("/grow-control/tents/<tent_id>/temperature")\n'
  '    def grow_control_tent_temperature(tent_id):\n'
  '        return render_template(\n'
  '            "temperature.html",\n'
  '            **_tent_page_context(tent_id),\n'
  '        )\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/humidity")\n'
  '    def grow_control_tent_humidity(tent_id):\n'
  '        return render_template(\n'
  '            "humidity.html",\n'
  '            **_tent_page_context(tent_id),\n'
  '        )\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/vpd")\n'
  '    def grow_control_tent_vpd(tent_id):\n'
  '        return render_template(\n'
  '            "vpd.html",\n'
  '            **_tent_page_context(tent_id),\n'
  '        )\n',
  '    def _environment_history_page(tent_id, metric):\n'
  '        context = _tent_page_context(tent_id)\n'
  '        meta = {\n'
  '            "temp": ("Temperatur", "🌡️"),\n'
  '            "hum": ("Luftfeuchtigkeit", "💧"),\n'
  '            "vpd": ("VPD", "🌱"),\n'
  '            "ppfd": ("Helligkeit", "☀️"),\n'
  '        }\n'
  '        title, icon = meta[metric]\n'
  '        return render_template(\n'
  '            "environment_history.html",\n'
  '            initial_metric=metric,\n'
  '            metric_title=title,\n'
  '            metric_icon=icon,\n'
  '            **context,\n'
  '        )\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/temperature")\n'
  '    def grow_control_tent_temperature(tent_id):\n'
  '        return _environment_history_page(tent_id, "temp")\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/humidity")\n'
  '    def grow_control_tent_humidity(tent_id):\n'
  '        return _environment_history_page(tent_id, "hum")\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/vpd")\n'
  '    def grow_control_tent_vpd(tent_id):\n'
  '        return _environment_history_page(tent_id, "vpd")\n'
  '\n'
  '    @app.route("/grow-control/tents/<tent_id>/ppfd")\n'
  '    def grow_control_tent_ppfd(tent_id):\n'
  '        return _environment_history_page(tent_id, "ppfd")\n',
  'Dashboard-Routen verwenden gemeinsame Verlaufsseite'),
 ('routes/dashboard.py',
  '    @app.route("/vpd")\n'
  '    def vpd_page():\n'
  '        return redirect(_default_tent_url("grow_control_tent_vpd"), code=302)\n',
  '    @app.route("/vpd")\n'
  '    def vpd_page():\n'
  '        return redirect(_default_tent_url("grow_control_tent_vpd"), code=302)\n'
  '\n'
  '    @app.route("/light-level")\n'
  '    def light_level_page():\n'
  '        return redirect(_default_tent_url("grow_control_tent_ppfd"), code=302)\n',
  'Legacy-Helligkeits-URL führt zum PPFD-Diagramm')]

for item in REPLACEMENTS:
    replace_once(*item)

p = ROOT / "templates/grow_control.html"
html = p.read_text(encoding="utf-8")
pattern = re.compile(
    r'<(?:a|div)\b[^>]*\bid=["\']light-level-link["\'][^>]*>.*?</(?:a|div)>',
    re.IGNORECASE | re.DOTALL,
)
matches = list(pattern.finditer(html))
if len(matches) != 1:
    fail(f"Helligkeits-Kachel nicht eindeutig ersetzbar (Treffer {len(matches)})")

new_card = """<a href="{{ url_for('grow_control_tent_ppfd', tent_id=tent_id) }}" class="card-link ppfd-card-shell" id="light-level-link">
        <div class="card env" id="light-level-card">
            <h2>Helligkeit</h2>
            <div class="value ppfd-value"><span id="light-level">---</span></div>
            <div class="sub ppfd-unit">µmol/m²/s</div>
        </div>
    </a>"""

m = matches[0]
html = html[:m.start()] + new_card + html[m.end():]

if ".ppfd-unit{" not in html:
    anchor = ".sub { margin-top: 6px; font-size: .8rem; color: var(--muted); }"
    if anchor in html:
        html = html.replace(anchor, anchor + """
.ppfd-card-shell{color:inherit;text-decoration:none}
.ppfd-value{line-height:1.02}
.ppfd-unit{margin-top:4px;font-size:.72rem;font-weight:600;letter-spacing:.01em;color:var(--muted)}
""", 1)

p.write_text(html, encoding="utf-8")
print("✅ Helligkeits-Kachel verlinkt auf PPFD-Diagramm")
print("✅ Growstar 3.15.0 / ENV.CHARTS.1 vollständig angewendet")
