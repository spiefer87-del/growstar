#!/usr/bin/env python3
"""Combined historical climate series and navigation to the VPD map."""
from pathlib import Path
from unittest.mock import patch
import sqlite3
import sys
import tempfile
import types

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if 'flask' not in sys.modules:
    flask=types.ModuleType('flask')
    flask.jsonify=lambda *a,**kw:a[0] if a else kw
    flask.request=types.SimpleNamespace(args={})
    flask.send_file=lambda *a,**kw:None
    sys.modules['flask']=flask
from routes.diagrams import _history_rows


def require(condition,message):
    assert condition,message
    print('✅',message)


def main():
    with tempfile.TemporaryDirectory(prefix='growstar-climate-chart-') as folder:
        db=Path(folder)/'data.db';connect=sqlite3.connect
        with connect(db) as conn:
            conn.execute('CREATE TABLE temp_history(tent_id TEXT, ts INTEGER, temp REAL, hum REAL, temp_target REAL, hum_target REAL)')
            conn.executemany('INSERT INTO temp_history VALUES(?,?,?,?,?,?)',[
                ('tent_1',1000,24.0,56.0,25.0,60.0),
                ('tent_1',1100,None,57.0,25.0,60.0),
                ('tent_1',1200,24.5,None,25.5,59.0),
                ('tent_2',1200,30.0,40.0,29.0,45.0),
                ('tent_1',-5000,12.0,20.0,25.0,60.0),
            ])
        with patch('routes.diagrams.sqlite3.connect',side_effect=lambda *_:connect(db)),patch('routes.diagrams.time.time',return_value=1300):
            rows=_history_rows('tent_1','1h','climate')
            other=_history_rows('tent_2','1h','climate')
        require([r['ts'] for r in rows]==[1000,1100,1200] and len(other)==1,
                'Gemeinsame History trennt Stationen und Zeitfenster')
        require(rows[0]['temp']==24.0 and rows[0]['hum']==56.0 and rows[0]['temp_target']==25.0 and rows[0]['hum_target']==60.0,
                'Temperatur, Feuchte und ihre Sollwerte gehören zum selben Zeitpunkt')
        require(rows[1]['temp'] is None and rows[1]['hum']==57.0 and rows[2]['temp']==24.5 and rows[2]['hum'] is None,
                'Fehlende Einzelmessungen werden nicht als Nullwerte erfunden')
    page=(ROOT/'templates/environment_history.html').read_text()
    map_page=(ROOT/'templates/vpd_chart.html').read_text()
    dashboard=(ROOT/'templates/grow_control.html').read_text()
    require('data-metric="temp"' in page and 'data-metric="hum"' in page and 'grow_control_tent_vpd_chart' in page,
            'Verlaufsnavigation öffnet die VPD-Chart als Reiter')
    require('grow_control_tent_temperature' in map_page and 'grow_control_tent_humidity' in map_page and 'aria-current="page"' in map_page,
            'VPD-Chart bietet dieselbe Diagrammnavigation')
    require('vpd-chart-shortcut' not in dashboard and 'grow_control_tent_vpd_chart' not in dashboard,
            'Grüner Schnellbutton ist aus der VPD-Dashboardkachel entfernt')
    require('type=combined?"climate":requestedMetric' in page and 'yAxisID:"ySecondary"' in page
            and 'grid:{drawOnChartArea:false}' in page and 'aria-pressed="false"' in page,
            'Zusatzkurve verwendet gemeinsame Zeitachse und zweite Einheitenskala')
    require('metric==="temp"?(showSecondary?"Feuchte ausblenden":"Feuchte einblenden")' in page
            and 'showSecondary?"Temperatur ausblenden":"Temperatur einblenden"' in page,
            'Zusatzkurve ist von Temperatur und Feuchte aus ein- und ausschaltbar')
    print('✅ ENV.CLIMATE.COMBINED.1 erfolgreich')


if __name__=='__main__':main()
