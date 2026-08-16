#!/usr/bin/env python3
"""Phase 4N – stationsbezogenes Dashboard-Design.

Hardware- und netzwerkfrei. Prüft nur Routing, Rechte und UI-Kontrakte.
"""
from pathlib import Path
import ast

try:
    from jinja2 import Environment, DictLoader
except ModuleNotFoundError:
    Environment = None

ROOT = Path(__file__).resolve().parent

def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
def require(cond,msg):
    if not cond: raise AssertionError(msg)
    print('✅',msg)

def main():
    dashboard=read('routes/dashboard.py')
    policy=read('auth/policy.py')
    design=read('templates/design.html')
    grow=read('templates/grow_control.html')
    self_src=read('check_multi_tent_phase4n.py')

    for name,src in [('routes/dashboard.py',dashboard),('auth/policy.py',policy),('check_multi_tent_phase4n.py',self_src)]:
        ast.parse(src,filename=name)
    print('✅ Python-Syntax Phase 4N')

    if Environment is not None:
        env=Environment(loader=DictLoader({'base.html':'<html><head>{% block head %}{% endblock %}</head><body>{% block page %}{% endblock %}</body></html>','design.html':design,'grow_control.html':grow}))
        env.parse(design); env.parse(grow)
        print('✅ Jinja-Syntax Phase 4N')

    require('@app.route("/grow-control/tents/<tent_id>/design")' in dashboard,'Stationsbezogene Design-Route vorhanden')
    require('_design_page_context(tent_id)' in dashboard and 'design_tents' in dashboard,'Design-Route erhält Stationsliste ohne zusätzliche API-Abhängigkeit')
    require('@app.route("/design")' in dashboard and 'default_tent_id()' in dashboard,'Legacy /design bleibt für Default-Station erhalten')
    require('path.endswith("/design")' in policy and 'require("settings.view")' in policy,'Stationsbezogene Design-Seite benötigt settings.view')

    require('/api/tents/${encodeURIComponent(TENT_ID)}/config' in design,'Design liest/schreibt stationsbezogene Config')
    require('/api/config' not in design,'Design verwendet kein globales /api/config mehr')
    require('DASH_ENV' in design and 'DASH_ENV_ORDER' in design and 'DASH_DEVICE' in design and 'DASH_DEVICE_ORDER' in design,'Alle vier Dashboard-Strukturen werden gespeichert')
    require("{key:'irrigation', label:'💧 Bewässerung'}" in design,'Bewässerung ist explizit auf der Design-Seite vorhanden')
    for key in ('heating','fan','light','vent','irrigation','humidifier','dehumidifier','light2','vent2'):
        require(f"key:'{key}'" in design,f'Gerätekachel {key} konfigurierbar')
    require('moveItem(kind, index, -1)' in design and 'moveItem(kind, index, 1)' in design,'Reihenfolge lässt sich mobil über Hoch/Runter ändern')
    require('result[item.key] = index + 1' in design,'Speichern normalisiert eindeutige Reihenfolge')
    require('const result = {...raw}' in design,'Unbekannte zukünftige Dashboard-Schlüssel bleiben beim Speichern erhalten')
    require("has_any_permission('grow.configure', 'settings.manage')" in design,'Schreib-UI respektiert Konfigurationsrechte')
    require('Eine Hardware-Zuordnung blendet' in design,'Hardware-Zuordnung und Sichtbarkeit bleiben bewusst getrennt')

    require("grow_control_tent_design" in grow and '🎨 Design' in grow,'Jede Stationsansicht verlinkt ihr eigenes Dashboard-Design')
    require('irrigation: document.getElementById("irrigation-card")' in grow,'Grow-Dashboard besitzt weiterhin Bewässerungs-Kachel')
    require('const devVisible = cfg.DASH_DEVICE || {}' in grow and 'devVisible[key] !== false' in grow,'Grow-Dashboard verwendet stationsbezogene Sichtbarkeit')

    print('✅ Phase 4N stationsbezogenes Dashboard-Design vollständig')

if __name__=='__main__': main()
