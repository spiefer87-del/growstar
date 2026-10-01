#!/usr/bin/env python3
"""Station switch stays right of range controls across all environment charts."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
series=(ROOT/'templates/environment_history.html').read_text()
map_page=(ROOT/'templates/vpd_chart.html').read_text()


def require(condition,message):
    assert condition,message
    print('✅',message)


def main():
    require('.toolbar{display:grid;grid-template-columns:minmax(0,1fr) 132px' in series
            and '.station-select{grid-column:2;grid-row:1;' in series,
            'Stationswahl hat im Zeitverlauf eine feste rechte Spalte')
    require(series.index('<div class="range-bar">')<series.index('<select id="station-select"')<series.index('<div id="chart-actions"'),
            'Zeitraum und Station teilen Zeile 1; Zusatzschalter stehen darunter')
    require('.range-bar{display:flex;' in series and 'overflow-x:auto' in series
            and '@media(max-width:420px){.toolbar{grid-template-columns:minmax(0,1fr) 116px}' in series,
            'Schmale Handys scrollen nur die Zeitbereiche, nicht die Stationswahl')
    require('byId("chart-actions").hidden=!c.target&&secondary.hidden' in series
            and 'grid-column:1/-1' in series,
            'Leere Aktionszeilen verschwinden; Zusatzschalter ändern die Position nicht')
    require('.vc-tools{display:grid;grid-template-columns:minmax(0,1fr) 132px' in map_page
            and '.vc-tools select{grid-column:2;grid-row:1;' in map_page
            and map_page.index('<div class="vc-ranges">')<map_page.index('<select id="vc-station"'),
            'VPD-Karte richtet die Stationswahl ebenfalls fest rechts aus')
    print('✅ ENV.STATION.LAYOUT.1 erfolgreich')


if __name__=='__main__':main()
