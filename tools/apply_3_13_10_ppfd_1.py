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

REPLACEMENTS = [('core/sensor_sources.py',
  'def update_sensor_source(\n'
  '    source_id,\n'
  '    label=None,\n'
  '    source_type=None,\n'
  '    temperature=None,\n'
  '    humidity=None,\n'
  '    battery=None,\n'
  '    rssi=None,\n'
  '    raw=None,\n'
  '):',
  'def update_sensor_source(\n'
  '    source_id,\n'
  '    label=None,\n'
  '    source_type=None,\n'
  '    temperature=None,\n'
  '    humidity=None,\n'
  '    ppfd=None,\n'
  '    battery=None,\n'
  '    rssi=None,\n'
  '    raw=None,\n'
  '):',
  'Sensorquelle akzeptiert PPFD'),
 ('core/sensor_sources.py',
  '        if humidity is not None:\n'
  '            source["humidity"] = float(humidity)\n'
  '\n'
  '        if battery is not None:',
  '        if humidity is not None:\n'
  '            source["humidity"] = float(humidity)\n'
  '\n'
  '        if ppfd is not None:\n'
  '            source["ppfd"] = float(ppfd)\n'
  '\n'
  '        if battery is not None:',
  'Sensorquelle speichert PPFD'),
 ('services/spiderfarmer.py',
  '        humidity = sensor.get(\n'
  '            "humidity_percent"\n'
  '        )\n'
  '\n'
  '        if (\n'
  '            temperature is None\n'
  '            and humidity is None\n'
  '        ):',
  '        humidity = sensor.get(\n'
  '            "humidity_percent"\n'
  '        )\n'
  '\n'
  '        ppfd = sensor.get(\n'
  '            "ppfd"\n'
  '        )\n'
  '\n'
  '        if (\n'
  '            temperature is None\n'
  '            and humidity is None\n'
  '            and ppfd is None\n'
  '        ):',
  'Spider-Farmer Sync liest PPFD'),
 ('services/spiderfarmer.py',
  '            source_type="spiderfarmer",\n'
  '            temperature=temperature,\n'
  '            humidity=humidity,\n'
  '            raw=raw,\n'
  '        )',
  '            source_type="spiderfarmer",\n'
  '            temperature=temperature,\n'
  '            humidity=humidity,\n'
  '            ppfd=ppfd,\n'
  '            raw=raw,\n'
  '        )',
  'Spider-Farmer Sync publiziert PPFD'),
 ('services/spiderfarmer.py',
  '            "humidity": (\n'
  '                source.get("humidity")\n'
  '                if source\n'
  '                else humidity\n'
  '            ),\n'
  '            "bridge_last_seen": last_seen,',
  '            "humidity": (\n'
  '                source.get("humidity")\n'
  '                if source\n'
  '                else humidity\n'
  '            ),\n'
  '            "ppfd": (\n'
  '                source.get("ppfd")\n'
  '                if source\n'
  '                else ppfd\n'
  '            ),\n'
  '            "bridge_last_seen": last_seen,',
  'Spider-Farmer Sync meldet PPFD diagnostisch'),
 ('routes/tents.py',
  'from services.spiderfarmer import device as spiderfarmer_device\n',
  'from services.spiderfarmer import device as spiderfarmer_device\n'
  'from core.sensor_sources import get_sensor_source\n',
  'Tent-API kann Sensorquellen lesen'),
 ('routes/tents.py',
  'def _age(last_seen):\n'
  '    if not last_seen:\n'
  '        return None\n'
  '    return max(0, int(time.time() - last_seen))\n'
  '\n'
  '\n',
  'def _age(last_seen):\n'
  '    if not last_seen:\n'
  '        return None\n'
  '    return max(0, int(time.time() - last_seen))\n'
  '\n'
  '\n'
  'def _assigned_spiderfarmer_ppfd(runtime):\n'
  '    """Return PPFD from this station\'s assigned Spider Farmer environment source.\n'
  '\n'
  '    PPFD.1 deliberately reuses the existing temperature/humidity sensor\n'
  '    assignment as the station binding. No control logic is changed.\n'
  '    """\n'
  '\n'
  '    assignments = runtime.config.get("SENSOR_ASSIGNMENTS", {})\n'
  '    if not isinstance(assignments, dict):\n'
  '        return None, None\n'
  '\n'
  '    source_ids = []\n'
  '    for sensor_name in ("temperature", "humidity"):\n'
  '        assignment = assignments.get(sensor_name) or {}\n'
  '        source_id = str(assignment.get("source_id") or "").strip()\n'
  '        if source_id.startswith("spiderfarmer:") and source_id not in source_ids:\n'
  '            source_ids.append(source_id)\n'
  '\n'
  '    for source_id in source_ids:\n'
  '        source = get_sensor_source(source_id)\n'
  '        if not isinstance(source, dict):\n'
  '            continue\n'
  '\n'
  '        value = source.get("ppfd")\n'
  '        if value is None:\n'
  '            continue\n'
  '\n'
  '        try:\n'
  '            ppfd = float(value)\n'
  '        except (TypeError, ValueError):\n'
  '            continue\n'
  '\n'
  '        return ppfd, {\n'
  '            "source_id": source_id,\n'
  '            "label": source.get("label") or source_id,\n'
  '            "last_seen": source.get("last_seen"),\n'
  '        }\n'
  '\n'
  '    return None, None\n'
  '\n'
  '\n',
  'Tent-API erhält stationsbezogene PPFD-Auflösung'),
 ('routes/tents.py',
  '    safety = get_runtime_safety_snapshot(runtime)\n\n    devices = {}',
  '    safety = get_runtime_safety_snapshot(runtime)\n'
  '    light_ppfd, light_ppfd_source = _assigned_spiderfarmer_ppfd(runtime)\n'
  '\n'
  '    devices = {}',
  'State-Snapshot liest PPFD'),
 ('routes/tents.py',
  '        "vpd": live.get("vpd"),\n        "temp_target": live.get("temp_target"),',
  '        "vpd": live.get("vpd"),\n'
  '        "light_ppfd": light_ppfd,\n'
  '        "light_ppfd_source": light_ppfd_source,\n'
  '        "temp_target": live.get("temp_target"),',
  'State-API veröffentlicht light_ppfd'),
 ('templates/grow_control.html',
  '    <a href="/light-level" class="card-link pending-detail-link" id="light-level-link">\n'
  '        <div class="card env" id="light-level-card"><h2>Helligkeit</h2><div class="value"><span '
  'id="light-level">---</span> lx</div><div class="sub">Sensor</div></div>\n'
  '    </a>',
  '    <a href="/light-level" class="card-link pending-detail-link" id="light-level-link">\n'
  '        <div class="card env" id="light-level-card"><h2>Helligkeit</h2><div class="value"><span '
  'id="light-level">---</span> µmol/m²/s</div><div class="sub" id="light-level-source">PPFD · '
  'Sensor</div></div>\n'
  '    </a>',
  'Dashboard-Kachel verwendet PPFD-Einheit'),
 ('templates/grow_control.html',
  '            safeText("hum-soll", formatNumber(state.hum_target, 1));\n'
  '            safeText("vpd", formatNumber(state.vpd, 2));\n'
  '\n'
  '            const ramp = document.getElementById("temp-ramp");',
  '            safeText("hum-soll", formatNumber(state.hum_target, 1));\n'
  '            safeText("vpd", formatNumber(state.vpd, 2));\n'
  '            safeText("light-level", Number.isFinite(Number(state.light_ppfd))\n'
  '                ? String(Math.round(Number(state.light_ppfd)))\n'
  '                : "---");\n'
  '\n'
  '            const ppfdSource = document.getElementById("light-level-source");\n'
  '            if (ppfdSource) {\n'
  '                const sourceLabel = state.light_ppfd_source?.label;\n'
  '                ppfdSource.textContent = sourceLabel\n'
  '                    ? `PPFD · ${sourceLabel}`\n'
  '                    : "PPFD · Sensor";\n'
  '            }\n'
  '\n'
  '            const ramp = document.getElementById("temp-ramp");',
  'Dashboard aktualisiert PPFD live')]

for args in REPLACEMENTS:
    replace_once(*args)

print('✅ Growstar 3.13.10 / PPFD.1 Patch vollständig angewendet')
