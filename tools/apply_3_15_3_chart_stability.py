#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def fail(msg):
    raise SystemExit("❌ " + msg)

def replace_once(path, old, new, label):
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

page = ROOT / "templates/environment_history.html"
if not page.exists():
    fail("templates/environment_history.html fehlt")

text = page.read_text(encoding="utf-8")
for marker in (
    'data-metric="temp"',
    'data-metric="hum"',
    'data-metric="vpd"',
    'data-metric="ppfd"',
    'id="station-select"',
):
    if marker not in text:
        fail(f"Diagramm-Voraussetzung fehlt: {marker}")
print("✅ ENV.CHARTS + Stationswechsel erkannt")

old_scale = '''function xScale(){const now=Date.now(),min=now-RANGES[currentRange].seconds*1000;if(currentRange==="1h")return{type:"linear",min,max:now,ticks:{color:"#94a3b8",maxTicksLimit:7,callback:v=>new Date(v).toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit"})}};if(currentRange==="7d")return{type:"time",min,max:now,time:{unit:"day",displayFormats:{day:"dd.MM"}},ticks:{color:"#94a3b8",maxTicksLimit:7}};return{type:"time",min,max:now,time:{unit:"hour"},ticks:{color:"#94a3b8",maxTicksLimit:8,callback:v=>new Date(v).toLocaleTimeString("de-DE",{hour:"2-digit"})}}}'''

new_scale = '''function xScale(){const now=Date.now(),min=now-RANGES[currentRange].seconds*1000;const unit=currentRange==="1h"?"minute":currentRange==="7d"?"day":"hour";const maxTicks=currentRange==="1h"?7:currentRange==="7d"?7:8;return{type:"time",min,max:now,time:{unit,displayFormats:{minute:"HH:mm",hour:"HH:mm",day:"dd.MM"}},ticks:{color:"#94a3b8",maxTicksLimit:maxTicks}}}'''

if new_scale not in text:
    if old_scale not in text:
        fail("Alte xScale()-Funktion nicht gefunden")
    text = text.replace(old_scale, new_scale, 1)
    print("✅ 1h/6h/24h/7d verwenden jetzt einheitlich die Time-Scale")
else:
    print("✅ Time-Scale bereits stabilisiert")

old_load = '''async function load(){const c=METRICS[metric],url=`/api/tents/${encodeURIComponent(TENT_ID)}/history?range=${currentRange}&type=${metric}`;try{const res=await fetch(url,{cache:"no-store"});if(!res.ok)throw new Error(`HTTP ${res.status}`);let d=await res.json();if(!Array.isArray(d))d=[];d=downsample(d,RANGES[currentRange].maxPoints);updateStats(d);byId("empty").classList.toggle("show",vals(d,c.field).length===0);const ds=dataSets(d);if(!chart){chart=new Chart(byId("chart"),{type:"line",data:{datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},scales:{x:xScale(),y:{beginAtZero:metric==="ppfd",ticks:{color:"#94a3b8"}}},plugins:{legend:{position:"bottom",labels:{color:"#e5e7eb"}},tooltip:{callbacks:{label:x=>`${x.dataset.label}: ${fmt(x.parsed.y,c.decimals)} ${c.unit}`}}}}})}else{chart.data.datasets=ds;chart.options.scales.x=xScale();chart.options.scales.y.beginAtZero=metric==="ppfd";chart.update("none")}}catch(e){console.error(e);byId("empty").textContent="Messwerte konnten gerade nicht geladen werden.";byId("empty").classList.add("show")}}'''

new_load = '''async function load(){const c=METRICS[metric],url=`/api/tents/${encodeURIComponent(TENT_ID)}/history?range=${currentRange}&type=${metric}`;let d;try{const res=await fetch(url,{cache:"no-store"});if(!res.ok)throw new Error(`HTTP ${res.status}`);d=await res.json();if(!Array.isArray(d))throw new Error("History API lieferte kein Array")}catch(e){console.error("History API:",e);byId("empty").textContent=`Messwerte konnten nicht geladen werden (${e.message}).`;byId("empty").classList.add("show");return}d=downsample(d,RANGES[currentRange].maxPoints);updateStats(d);const hasValues=vals(d,c.field).length>0;byId("empty").textContent="Für diesen Zeitraum sind noch keine Messwerte gespeichert.";byId("empty").classList.toggle("show",!hasValues);const ds=dataSets(d);try{if(!chart){chart=new Chart(byId("chart"),{type:"line",data:{datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},scales:{x:xScale(),y:{beginAtZero:metric==="ppfd",ticks:{color:"#94a3b8"}}},plugins:{legend:{position:"bottom",labels:{color:"#e5e7eb"}},tooltip:{callbacks:{label:x=>`${x.dataset.label}: ${fmt(x.parsed.y,c.decimals)} ${c.unit}`}}}}})}else{chart.data.datasets=ds;chart.options.scales.x=xScale();chart.options.scales.y.beginAtZero=metric==="ppfd";chart.update("none")}}catch(e){console.error("Chart render:",e);byId("empty").textContent=`Diagramm konnte nicht gezeichnet werden (${e.message}).`;byId("empty").classList.add("show")}}'''

if new_load not in text:
    if old_load not in text:
        fail("Alte load()-Funktion nicht gefunden")
    text = text.replace(old_load, new_load, 1)
    print("✅ API- und Chart-Fehler werden getrennt behandelt")
else:
    print("✅ Fehlerdiagnose bereits verbessert")

page.write_text(text, encoding="utf-8")

test_path = ROOT / "tests/regression/check_spiderfarmer_ppfd_dashboard.py"
if test_path.exists():
    test = test_path.read_text(encoding="utf-8")
    old = '''    require('safeText("light-level"' in template, "Dashboard aktualisiert vorbereitete Helligkeits-Kachel")'''
    new = '''    require(
        '"light-level"' in template and "state.light_ppfd" in template,
        "Dashboard aktualisiert vorbereitete Helligkeits-Kachel",
    )'''
    if new not in test:
        if old not in test:
            fail("Alter PPFD-Dashboard-Testmarker nicht gefunden")
        test_path.write_text(test.replace(old, new, 1), encoding="utf-8")
        print("✅ PPFD-Regressionstest toleriert formatierte JS-Zeilen")

print("✅ Growstar 3.15.3 / ENV.CHARTS.STABILITY vollständig angewendet")
