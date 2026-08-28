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

# Build dependency guard: 3.13.10 / PPFD.1 must already be installed.
required = {
    'core/sensor_sources.py': 'ppfd=None',
    'services/spiderfarmer.py': 'ppfd=ppfd',
    'routes/tents.py': 'def _assigned_spiderfarmer_ppfd(runtime):',
    'templates/grow_control.html': 'µmol/m²/s',
}
for rel, marker in required.items():
    text = (ROOT / rel).read_text(encoding='utf-8')
    if marker not in text:
        raise SystemExit(f'❌ 3.13.10 / PPFD.1 fehlt oder ist unvollständig: {rel}')

REPLACEMENTS = [('routes/sensors.py',
  'def _sensor_options():\n'
  '    """Controller-weite Quellen; Zuweisung erfolgt erst pro Runtime."""\n'
  '    sources = _source_map()\n'
  '    temperature = []\n'
  '    humidity = []\n',
  'def _sensor_options():\n'
  '    """Controller-weite Quellen; Zuweisung erfolgt erst pro Runtime."""\n'
  '    sources = _source_map()\n'
  '    temperature = []\n'
  '    humidity = []\n'
  '    ppfd = []\n',
  'Sensoroptionen erhalten PPFD-Liste'),
 ('routes/sensors.py',
  '        if _supports(source, "humidity"):\n'
  '            humidity.append({\n'
  '                "source_id": source_id,\n'
  '                "field": "humidity",\n'
  '                "label": label,\n'
  '                "value": source.get("humidity"),\n'
  '                "type": source.get("type"),\n'
  '            })\n'
  '\n'
  '    return {\n'
  '        "temperature": temperature,\n'
  '        "humidity": humidity,\n'
  '    }\n',
  '        if _supports(source, "humidity"):\n'
  '            humidity.append({\n'
  '                "source_id": source_id,\n'
  '                "field": "humidity",\n'
  '                "label": label,\n'
  '                "value": source.get("humidity"),\n'
  '                "type": source.get("type"),\n'
  '            })\n'
  '\n'
  '        if _supports(source, "ppfd"):\n'
  '            ppfd.append({\n'
  '                "source_id": source_id,\n'
  '                "field": "ppfd",\n'
  '                "label": label,\n'
  '                "value": source.get("ppfd"),\n'
  '                "type": source.get("type"),\n'
  '            })\n'
  '\n'
  '    return {\n'
  '        "temperature": temperature,\n'
  '        "humidity": humidity,\n'
  '        "ppfd": ppfd,\n'
  '    }\n',
  'Sensoroptionen bieten PPFD-Quellen an'),
 ('routes/sensors.py',
  '        item["fields"] = [\n'
  '            field\n'
  '            for field in ("temperature", "humidity")\n'
  '            if _supports(source, field)\n'
  '        ]\n',
  '        item["fields"] = [\n'
  '            field\n'
  '            for field in ("temperature", "humidity", "ppfd")\n'
  '            if _supports(source, field)\n'
  '        ]\n',
  'Sensorquellen-Payload weist PPFD aus'),
 ('routes/sensors.py',
  '    if not field:\n        field = "temperature" if sensor_name == "temperature" else "humidity"\n',
  '    if not field:\n'
  '        field = {\n'
  '            "temperature": "temperature",\n'
  '            "humidity": "humidity",\n'
  '            "ppfd": "ppfd",\n'
  '        }.get(sensor_name)\n'
  '\n'
  '    if field not in {"temperature", "humidity", "ppfd"}:\n'
  '        raise ValueError(f"Ungültiges Sensorfeld für {sensor_name}: {field}")\n',
  'Sensorzuweisung validiert PPFD-Feld'),
 ('routes/sensors.py',
  '    if "humidity" in data:\n'
  '        assignments["humidity"] = _normalize_assignment(\n'
  '            "humidity",\n'
  '            data["humidity"],\n'
  '        )\n'
  '\n'
  '    offsets = data.get("offsets", {})\n',
  '    if "humidity" in data:\n'
  '        assignments["humidity"] = _normalize_assignment(\n'
  '            "humidity",\n'
  '            data["humidity"],\n'
  '        )\n'
  '\n'
  '    if "ppfd" in data:\n'
  '        assignments["ppfd"] = _normalize_assignment(\n'
  '            "ppfd",\n'
  '            data["ppfd"],\n'
  '        )\n'
  '\n'
  '    offsets = data.get("offsets", {})\n',
  'PPFD-Zuweisung wird gespeichert'),
 ('routes/sensors.py',
  '    if "temperature" in data or "humidity" in data:\n'
  '        runtime.config["SENSOR_ASSIGNMENTS"] = assignments\n',
  '    if "temperature" in data or "humidity" in data or "ppfd" in data:\n'
  '        runtime.config["SENSOR_ASSIGNMENTS"] = assignments\n',
  'PPFD-Änderung persistiert SENSOR_ASSIGNMENTS'),
 ('routes/tents.py',
  '    source_ids = []\n'
  '    for sensor_name in ("temperature", "humidity"):\n'
  '        assignment = assignments.get(sensor_name) or {}\n'
  '        source_id = str(assignment.get("source_id") or "").strip()\n'
  '        if source_id.startswith("spiderfarmer:") and source_id not in source_ids:\n'
  '            source_ids.append(source_id)\n',
  '    source_ids = []\n'
  '\n'
  '    # PPFD.2: explicit station assignment has priority.\n'
  '    ppfd_assignment = assignments.get("ppfd") or {}\n'
  '    ppfd_source_id = str(ppfd_assignment.get("source_id") or "").strip()\n'
  '    if ppfd_source_id:\n'
  '        source_ids.append(ppfd_source_id)\n'
  '\n'
  '    # Migration fallback for stations configured before PPFD.2.\n'
  '    for sensor_name in ("temperature", "humidity"):\n'
  '        assignment = assignments.get(sensor_name) or {}\n'
  '        source_id = str(assignment.get("source_id") or "").strip()\n'
  '        if source_id.startswith("spiderfarmer:") and source_id not in source_ids:\n'
  '            source_ids.append(source_id)\n',
  'Dashboard priorisiert explizite PPFD-Zuweisung'),
 ('templates/sensoren.html',
  '        <div\n'
  '            class="saved"\n'
  '            id="saved_hum">\n'
  '            ✓ gespeichert\n'
  '        </div>\n'
  '\n'
  '    </div>\n'
  '\n'
  '</div>\n',
  '        <div\n'
  '            class="saved"\n'
  '            id="saved_hum">\n'
  '            ✓ gespeichert\n'
  '        </div>\n'
  '\n'
  '    </div>\n'
  '\n'
  '    <div class="card">\n'
  '\n'
  '        <h2>Helligkeit / PPFD</h2>\n'
  '\n'
  '        <div class="value">\n'
  '            RAW:\n'
  '            <span id="ppfd_raw">--</span>\n'
  '            µmol/m²/s\n'
  '        </div>\n'
  '\n'
  '        <div class="sub">\n'
  '            Aktuelle Quelle:\n'
  '            <strong id="ppfd_source_label">\n'
  '                --\n'
  '            </strong>\n'
  '        </div>\n'
  '\n'
  '        <label class="form-label">\n'
  '            Sensor für Helligkeit / PPFD\n'
  '        </label>\n'
  '\n'
  '        <select\n'
  '            id="ppfd-source"\n'
  '            class="form-control">\n'
  '        </select>\n'
  '\n'
  '        <div class="sub" style="margin-top:12px;">\n'
  '            Die Zuweisung wird bereits stationsbezogen gespeichert.\n'
  '            Eine automatische Lichtregelung verwendet diesen Wert noch nicht.\n'
  '        </div>\n'
  '\n'
  '    </div>\n'
  '\n'
  '</div>\n',
  'Sensorseite erhält PPFD-Karte'),
 ('templates/sensoren.html',
  'let sensorOptions = {\n    temperature: [],\n    humidity: []\n};\n',
  'let sensorOptions = {\n    temperature: [],\n    humidity: [],\n    ppfd: []\n};\n',
  'Sensor-UI kennt PPFD-Optionen'),
 ('templates/sensoren.html',
  '                (\n'
  '                    sensorName === "temperature"\n'
  '                    ? " °C"\n'
  '                    : " %"\n'
  '                ) +\n',
  '                (\n'
  '                    sensorName === "temperature"\n'
  '                    ? " °C"\n'
  '                    : (\n'
  '                        sensorName === "humidity"\n'
  '                        ? " %"\n'
  '                        : " µmol/m²/s"\n'
  '                    )\n'
  '                ) +\n',
  'PPFD-Dropdown zeigt korrekte Einheit'),
 ('templates/sensoren.html',
  '    const hum =\n'
  '        assignments.humidity || {};\n'
  '\n'
  '    document.getElementById("temp_source_label").textContent =\n',
  '    const hum =\n'
  '        assignments.humidity || {};\n'
  '\n'
  '    const ppfd =\n'
  '        assignments.ppfd || {};\n'
  '\n'
  '    document.getElementById("temp_source_label").textContent =\n',
  'Sensorlabels lesen PPFD-Zuweisung'),
 ('templates/sensoren.html',
  '    document.getElementById("hum_source_label").textContent =\n'
  '        hum.label ||\n'
  '        hum.source_id ||\n'
  '        "--";\n'
  '\n'
  '}\n',
  '    document.getElementById("hum_source_label").textContent =\n'
  '        hum.label ||\n'
  '        hum.source_id ||\n'
  '        "--";\n'
  '\n'
  '    document.getElementById("ppfd_source_label").textContent =\n'
  '        ppfd.label ||\n'
  '        ppfd.source_id ||\n'
  '        "--";\n'
  '\n'
  '}\n',
  'PPFD-Quelle wird angezeigt'),
 ('templates/sensoren.html',
  '                    · Batterie:\n'
  '                    ${source.battery !== undefined && source.battery !== null ? source.battery + " %" : "--"}\n'
  '                    · RSSI:\n',
  '                    · PPFD:\n'
  '                    ${source.ppfd !== undefined && source.ppfd !== null ? source.ppfd + " µmol/m²/s" : "--"}\n'
  '                    · Batterie:\n'
  '                    ${source.battery !== undefined && source.battery !== null ? source.battery + " %" : "--"}\n'
  '                    · RSSI:\n',
  'Quellenliste zeigt PPFD'),
 ('templates/sensoren.html',
  '        document.getElementById("hum_raw").textContent = fmt(s.hum_raw);\n'
  '        document.getElementById("hum_corr").textContent = fmt(s.hum);\n'
  '\n'
  '    }finally{\n',
  '        document.getElementById("hum_raw").textContent = fmt(s.hum_raw);\n'
  '        document.getElementById("hum_corr").textContent = fmt(s.hum);\n'
  '        document.getElementById("ppfd_raw").textContent =\n'
  '            s.light_ppfd === null || s.light_ppfd === undefined\n'
  '                ? "--"\n'
  '                : Math.round(Number(s.light_ppfd));\n'
  '\n'
  '    }finally{\n',
  'Sensorseite aktualisiert PPFD-Livewert'),
 ('templates/sensoren.html',
  '    sensorOptions =\n'
  '        data.options || {\n'
  '            temperature: [],\n'
  '            humidity: []\n'
  '        };\n',
  '    sensorOptions =\n'
  '        data.options || {\n'
  '            temperature: [],\n'
  '            humidity: [],\n'
  '            ppfd: []\n'
  '        };\n',
  'Sensor-UI übernimmt PPFD-Optionen'),
 ('templates/sensoren.html',
  '    renderSelect(\n        "humidity",\n        "humidity-source"\n    );\n\n    renderSourceLabels();\n',
  '    renderSelect(\n'
  '        "humidity",\n'
  '        "humidity-source"\n'
  '    );\n'
  '\n'
  '    renderSelect(\n'
  '        "ppfd",\n'
  '        "ppfd-source"\n'
  '    );\n'
  '\n'
  '    renderSourceLabels();\n',
  'PPFD-Dropdown wird gerendert'),
 ('templates/sensoren.html',
  '    const tempSelect =\n'
  '        document.getElementById(\n'
  '            "temperature-source"\n'
  '        );\n'
  '\n'
  '    const humSelect =\n',
  '    const ppfdOption =\n'
  '        parseOptionValue(\n'
  '            document.getElementById(\n'
  '                "ppfd-source"\n'
  '            ).value\n'
  '        );\n'
  '\n'
  '    const tempSelect =\n'
  '        document.getElementById(\n'
  '            "temperature-source"\n'
  '        );\n'
  '\n'
  '    const humSelect =\n',
  'Speichern liest PPFD-Auswahl'),
 ('templates/sensoren.html',
  '    const humSelect =\n'
  '        document.getElementById(\n'
  '            "humidity-source"\n'
  '        );\n'
  '\n'
  '    tempOption.label =\n',
  '    const humSelect =\n'
  '        document.getElementById(\n'
  '            "humidity-source"\n'
  '        );\n'
  '\n'
  '    const ppfdSelect =\n'
  '        document.getElementById(\n'
  '            "ppfd-source"\n'
  '        );\n'
  '\n'
  '    tempOption.label =\n',
  'Speichern kennt PPFD-Select'),
 ('templates/sensoren.html',
  '    humOption.label =\n'
  '        humSelect.selectedOptions[0]?.textContent\n'
  '        ?.replace(/\\s\\(.+\\)$/, "") ||\n'
  '        humOption.source_id;\n'
  '\n'
  '    const saveButton =\n',
  '    humOption.label =\n'
  '        humSelect.selectedOptions[0]?.textContent\n'
  '        ?.replace(/\\s\\(.+\\)$/, "") ||\n'
  '        humOption.source_id;\n'
  '\n'
  '    ppfdOption.label =\n'
  '        ppfdSelect.selectedOptions[0]?.textContent\n'
  '        ?.replace(/\\s\\(.+\\)$/, "") ||\n'
  '        ppfdOption.source_id;\n'
  '\n'
  '    const saveButton =\n',
  'PPFD-Label wird gespeichert'),
 ('templates/sensoren.html',
  '                body:JSON.stringify({\n'
  '                    temperature: tempOption,\n'
  '                    humidity: humOption\n'
  '                })\n',
  '                body:JSON.stringify({\n'
  '                    temperature: tempOption,\n'
  '                    humidity: humOption,\n'
  '                    ppfd: ppfdOption\n'
  '                })\n',
  'Sensor-POST enthält PPFD-Zuweisung'),
 ('templates/sensoren.html',
  'document.getElementById("humidity-source")\n'
  '    .addEventListener(\n'
  '        "change",\n'
  '        ()=>{\n'
  '            assignmentDirty = true;\n'
  '        }\n'
  '    );\n'
  '\n'
  '\n'
  '["TEMP_OFFSET", "HUM_OFFSET"].forEach(\n',
  'document.getElementById("humidity-source")\n'
  '    .addEventListener(\n'
  '        "change",\n'
  '        ()=>{\n'
  '            assignmentDirty = true;\n'
  '        }\n'
  '    );\n'
  '\n'
  'document.getElementById("ppfd-source")\n'
  '    .addEventListener(\n'
  '        "change",\n'
  '        ()=>{\n'
  '            assignmentDirty = true;\n'
  '        }\n'
  '    );\n'
  '\n'
  '\n'
  '["TEMP_OFFSET", "HUM_OFFSET"].forEach(\n',
  'PPFD-Auswahl markiert Formular als geändert'),
 ('routes/hardware.py',
  'from core.mqtt_sensor_devices import list_mqtt_sensor_devices\n'
  'from core.hardware_assignments import hardware_snapshot\n',
  'from core.mqtt_sensor_devices import list_mqtt_sensor_devices\n'
  'from core.sensor_sources import list_sensor_sources\n'
  'from core.hardware_assignments import hardware_snapshot\n',
  'Hardware-API kann zentrale Sensorquellen lesen'),
 ('routes/hardware.py',
  'def register(app):\n',
  'def _spiderfarmer_sensor_views():\n'
  '    """Read-only Spider Farmer environment sources for the hardware overview."""\n'
  '\n'
  '    result = []\n'
  '\n'
  '    for source in list_sensor_sources():\n'
  '        if str(source.get("type") or "") != "spiderfarmer":\n'
  '            continue\n'
  '\n'
  '        source_id = str(source.get("id") or "")\n'
  '        controller_id = ""\n'
  '        if source_id.startswith("spiderfarmer:"):\n'
  '            controller_id = source_id.split(":", 2)[1] if ":" in source_id else ""\n'
  '\n'
  '        result.append({\n'
  '            "id": source_id,\n'
  '            "source_id": source_id,\n'
  '            "name": source.get("label") or source_id,\n'
  '            "model": "Spider Farmer GGS Sensor",\n'
  '            "manufacturer": "Spider Farmer",\n'
  '            "controller_id": controller_id,\n'
  '            "online": bool(source.get("online", True)),\n'
  '            "temperature": source.get("temperature"),\n'
  '            "humidity": source.get("humidity"),\n'
  '            "ppfd": source.get("ppfd"),\n'
  '            "last_seen": source.get("last_seen"),\n'
  '            "capabilities": [\n'
  '                field\n'
  '                for field in ("temperature", "humidity", "ppfd")\n'
  '                if source.get(field) is not None\n'
  '            ],\n'
  '        })\n'
  '\n'
  '    result.sort(key=lambda item: str(item.get("name") or item.get("id") or ""))\n'
  '    return result\n'
  '\n'
  '\n'
  'def register(app):\n',
  'Hardware-API erzeugt Spider-Farmer-Sensoransicht'),
 ('routes/hardware.py',
  '            "mqtt_devices": list_mqtt_sensor_devices(),\n\n        })\n',
  '            "mqtt_devices": list_mqtt_sensor_devices(),\n'
  '\n'
  '            # Spider-Farmer-Umgebungssensoren erscheinen zusätzlich in der\n'
  '            # zentralen Hardwareübersicht. Read-only; keine Herstellerseite nötig.\n'
  '            "spiderfarmer_sensors": _spiderfarmer_sensor_views(),\n'
  '\n'
  '        })\n',
  'Hardware-API liefert Spider-Farmer-Sensoren'),
 ('templates/devices.html',
  '<h3>MQTT Sensorcontroller</h3>\n\n<div\nclass="grid"\nid="mqtt-device-grid">\n\n</div>\n\n\n<h3>Aktoren</h3>\n',
  '<h3>MQTT Sensorcontroller</h3>\n'
  '\n'
  '<div\n'
  'class="grid"\n'
  'id="mqtt-device-grid">\n'
  '\n'
  '</div>\n'
  '\n'
  '\n'
  '<h3>Spider Farmer Sensoren</h3>\n'
  '\n'
  '<div\n'
  'class="grid"\n'
  'id="spiderfarmer-sensor-grid">\n'
  '\n'
  '</div>\n'
  '\n'
  '\n'
  '<h3>Aktoren</h3>\n',
  'Hardwareseite erhält Spider-Farmer-Sensorbereich'),
 ('templates/devices.html',
  '        renderMqttDevices(\n            data.mqtt_devices || []\n        );\n\n        renderActuators(\n',
  '        renderMqttDevices(\n'
  '            data.mqtt_devices || []\n'
  '        );\n'
  '\n'
  '        renderSpiderFarmerSensors(\n'
  '            data.spiderfarmer_sensors || []\n'
  '        );\n'
  '\n'
  '        renderActuators(\n',
  'Hardware-Refresh rendert Spider-Farmer-Sensoren'),
 ('templates/devices.html',
  'function renderActuators(actuators){\n',
  'function renderSpiderFarmerSensors(devices){\n'
  '\n'
  '    const grid =\n'
  '        document.getElementById("spiderfarmer-sensor-grid");\n'
  '\n'
  '    grid.innerHTML = "";\n'
  '\n'
  '    if(devices.length === 0){\n'
  '\n'
  '        grid.innerHTML = `\n'
  '            <div class="card">\n'
  '                <h2>Noch keine Spider Farmer Sensoren</h2>\n'
  '                <div class="sub">\n'
  '                    GGS-Sensoren erscheinen hier automatisch, sobald Growstar\n'
  '                    einen Environment-Readback empfangen hat.\n'
  '                </div>\n'
  '            </div>\n'
  '        `;\n'
  '\n'
  '        return;\n'
  '\n'
  '    }\n'
  '\n'
  '    devices.forEach(device=>{\n'
  '\n'
  '        const fields = Array.isArray(device.capabilities)\n'
  '            ? device.capabilities.join(" · ")\n'
  '            : "";\n'
  '\n'
  '        const card = document.createElement("a");\n'
  '        card.href = "/grow-control/sensors";\n'
  '        card.className = "card-link";\n'
  '\n'
  '        card.innerHTML = `\n'
  '            <div class="card">\n'
  '                <h2>🌡️ ${escapeHtml(device.name || device.id)}</h2>\n'
  '                <div class="sub">${escapeHtml(device.model || "Spider Farmer Sensor")}</div>\n'
  '                <div class="badge ${device.online ? "online":"offline"}">\n'
  '                    ${device.online ? "Online":"Offline"}\n'
  '                </div>\n'
  '                <div class="device-meta">\n'
  '                    <div class="sub">Controller ${escapeHtml(device.controller_id || "--")}</div>\n'
  '                    <div class="sub">Quelle ${escapeHtml(device.source_id || "--")}</div>\n'
  '                    <div class="sub">\n'
  '                        Temperatur ${device.temperature ?? "--"} °C ·\n'
  '                        Feuchte ${device.humidity ?? "--"} %\n'
  '                    </div>\n'
  '                    <div class="sub">\n'
  '                        PPFD ${device.ppfd ?? "--"} µmol/m²/s\n'
  '                    </div>\n'
  '                    ${fields ? `<div class="sub">Sensoren ${escapeHtml(fields)}</div>` : ""}\n'
  '                    <div class="sub">Antippen zum Zuordnen →</div>\n'
  '                </div>\n'
  '            </div>\n'
  '        `;\n'
  '\n'
  '        grid.appendChild(card);\n'
  '\n'
  '    });\n'
  '\n'
  '}\n'
  '\n'
  '\n'
  'function renderActuators(actuators){\n',
  'Hardwareseite rendert Spider-Farmer-Sensorkarten')]

for args in REPLACEMENTS:
    replace_once(*args)

print('✅ Growstar 3.13.11 / SENSOR.PPFD.2 Patch vollständig angewendet')
