#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def req(cond,msg):
    if not cond:
        raise AssertionError(msg)
    print("✅",msg)

def main():
    page=(ROOT/"templates/environment_history.html").read_text(encoding="utf-8")

    req('temp:{title:"Temperatur"' in page and 'unit:"°C"' in page,
        "Temperatur-Einheit ist °C")
    req('hum:{title:"Luftfeuchtigkeit"' in page and 'unit:"%"' in page,
        "Feuchte-Einheit ist %")
    req('vpd:{title:"VPD"' in page and 'unit:"kPa"' in page,
        "VPD-Einheit ist kPa")
    req('ppfd:{title:"Helligkeit"' in page and 'unit:"µmol/m²/s"' in page,
        "PPFD-Einheit ist µmol/m²/s")
    req('function currentMetricConfig(){return METRICS[metric]}' in page,
        "Tooltip liest immer die aktuell gewählte Metrik")
    req('function tooltipLabel(ctx)' in page,
        "Dynamischer Tooltip-Formatter vorhanden")
    req('callbacks:{label:tooltipLabel}' in page,
        "Chart.js nutzt den dynamischen Tooltip-Formatter")
    req('const TOOLTIP_AUTO_HIDE_MS=2500' in page,
        "Tooltip schließt nach 2,5 Sekunden")
    req('function clearTooltip()' in page and 'function scheduleTooltipHide()' in page,
        "Tooltip-Close und Auto-Hide vorhanden")
    req('clearTooltip();metric=m' in page,
        "Metrikwechsel schließt offenen Tooltip")
    req('clearTooltip();currentRange=r' in page,
        "Zeitraumwechsel schließt offenen Tooltip")
    req('pointerup' in page and 'touchend' in page,
        "Maus/Pointer und Touch lösen Auto-Hide aus")
    req('setInterval(load,60000)' in page,
        "Bestehender 60-Sekunden-Auto-Refresh bleibt erhalten")

    print("✅ Growstar 3.15.6 / ENV.TOOLTIP.1 vollständig geprüft")

if __name__=="__main__":
    main()
