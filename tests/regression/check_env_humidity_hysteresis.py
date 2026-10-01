#!/usr/bin/env python3
"""Classic ENV humidification/dehumidification uses tolerance to start, target to stop."""
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if "requests" not in sys.modules:
    requests=types.ModuleType("requests")
    requests.RequestException=type("RequestException",(Exception,),{})
    requests.Timeout=requests.ConnectionError=requests.RequestException
    requests.get=requests.post=lambda *args,**kwargs:None
    sys.modules["requests"]=requests
import core.control as control


def runtime(tent_id,device,direction,humidity,shadow=False):
    return SimpleNamespace(
        tent_id=tent_id,control_enabled=not shadow,shadow_outputs={},state_lock=RLock(),
        state=SimpleNamespace(live_state={"hum":humidity,"hum_target":54.0,"hum_tol":4.0},humidifier_on=False,dehumidifier_on=False),
        config={"DEVICE_ENV_CONFIG":{device:{"use_hum":True,"use_temp":False,"direction":direction,"logic":"OR"}},
                "DEVICE_MODES":{device:"ENV"},"DEVICE_PARAMS":{device:{}}},
    )


def require(condition,message):
    assert condition,message
    print('✅',message)


def run(device,rt):
    control.control_device(device,runtime=rt)
    return rt.shadow_outputs.get(device) if not rt.control_enabled else getattr(rt.state,f"{device}_on")


def main():
    def apply(device,state,*,runtime=None,reason=""):
        power=bool(state.get("power"))
        if runtime.control_enabled:setattr(runtime.state,f"{device}_on",power)
        else:runtime.shadow_outputs[device]=power
    with patch.object(control,"resolve_runtime",side_effect=lambda runtime=None:runtime),\
         patch.object(control,"get_device_mode",side_effect=lambda device,runtime=None:runtime.config["DEVICE_MODES"][device]),\
         patch.object(control,"get_device_params",side_effect=lambda device,runtime=None:runtime.config["DEVICE_PARAMS"][device]),\
         patch.object(control,"apply_device_state",side_effect=apply),\
         patch.object(control,"vpd_manages_device",return_value=False):
        wet=runtime("tent_1","dehumidifier","HIGH",58.0)
        require(run("dehumidifier",wet) is False,"Bei exakt 58 % bleibt der zuvor ausgeschaltete Entfeuchter aus")
        wet.state.live_state["hum"]=58.1
        require(run("dehumidifier",wet) is True,"Oberhalb von 54 + 4 % startet Entfeuchtung")
        for value in (58.0,57.0,54.1):
            wet.state.live_state["hum"]=value
            require(run("dehumidifier",wet) is True,f"Bei {value} % läuft der begonnene Zyklus weiter")
        wet.state.live_state["hum"]=54.0
        require(run("dehumidifier",wet) is False,"Am Sollwert 54 % schaltet der Entfeuchter aus")
        wet.state.live_state["hum"]=57.9
        require(run("dehumidifier",wet) is False,"Innerhalb des Fensters startet er nicht erneut")
        wet.state.live_state["hum"]=58.1
        require(run("dehumidifier",wet) is True,"Erst erneute Überschreitung beginnt den nächsten Zyklus")
        wet.state.live_state["hum"]=None
        require(run("dehumidifier",wet) is False,"Fehlender Messwert beendet den Auftrag sicher")
        wet.state.live_state["hum"]=57.0
        require(run("dehumidifier",wet) is False,"Nach Sensorausfall wird mitten im Fenster kein Zyklus erfunden")

        dry=runtime("tent_2","humidifier","LOW",49.9)
        require(run("humidifier",dry) is True,"Befeuchtung beginnt unter 54 - 4 %")
        dry.state.live_state["hum"]=53.9
        require(run("humidifier",dry) is True,"Befeuchtung läuft bis zum Sollwert weiter")
        dry.state.live_state["hum"]=54.0
        require(run("humidifier",dry) is False,"Befeuchtung endet bei 54 %")
        require(wet.state.dehumidifier_on is False and dry.state.humidifier_on is False,"Beide Stationszustände sind getrennt")

        shadow=runtime("tent_shadow","dehumidifier","HIGH",58.1,shadow=True)
        require(run("dehumidifier",shadow) is True,"SHADOW merkt sich den angeforderten EIN-Zustand")
        shadow.state.live_state["hum"]=57.0
        require(run("dehumidifier",shadow) is True,"SHADOW führt den Zyklus bis zum Sollwert fort")
        require(shadow.state.dehumidifier_on is False,"SHADOW schaltet keine echte Relais-Statevariable")

        fan=runtime("tent_fan","fan","HIGH",58.1)
        fan.config["DEVICE_ENV_CONFIG"]["fan"]={"use_hum":True,"use_temp":False,"direction":"HIGH","logic":"OR"}
        fan.state.fan_on=True
        require(control.evaluate_env_conditions("fan",runtime=fan) is True,"Lüfter bleibt bei der bisherigen Startschwelle")
        fan.state.live_state["hum"]=57.0
        require(control.evaluate_env_conditions("fan",runtime=fan) is False,"Lüfter-Standby-Verhalten bleibt unverändert")
    print("✅ ENV.HUM.HYSTERESIS.1 erfolgreich")


if __name__=="__main__":main()
