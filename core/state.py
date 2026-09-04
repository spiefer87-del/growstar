from copy import deepcopy
from types import SimpleNamespace


# =========================================
# 📊 STATE-SCHEMA
# =========================================
#
# Das Modul bleibt für die bestehende Ein-Zelt-Installation vollständig
# kompatibel: alle bisherigen Variablen existieren weiterhin als Modul-
# Attribute. Zusätzlich kann Phase 2 nun unabhängige State-Container für
# weitere Zelte erzeugen.

_LIVE_STATE_TEMPLATE = {
    "temp": None,
    "temp_raw": None,
    "hum": None,
    "hum_raw": None,
    "vpd": None,

    # Optionales Außenklima für die intelligente VPD-Wirkungsprognose.
    # Diese Werte sind nie Ersatz für die Innenraumsensoren.
    "outside_temp": None,
    "outside_temp_raw": None,
    "outside_hum": None,
    "outside_hum_raw": None,
    "outside_temp_source": None,
    "outside_hum_source": None,

    # Öffentliche Diagnose der VPD-Zustandsmaschine. Der interne Verlauf wird
    # bei Bedarf separat und ausschließlich flüchtig im live_state angelegt.
    "vpd_control": {
        "mode": "OFF",
        "active": False,
        "takeover": False,
        "ready": False,
        "stage": "disabled",
        "managed_devices": [],
        "actions": {},
    },

    "profile": None,

    # Sollwerte (für Dashboard)
    "temp_target": None,
    "temp_tol": None,
    "hum_target": None,
    "hum_tol": None,
    # Klassische Profilwerte bleiben getrennt erhalten, wenn VPD-AUTO die
    # sichtbaren Live-Sollwerte stationsbezogen übernimmt.
    "climate_temp_target": None,
    "climate_hum_target": None,
    "climate_hum_tol": None,

    "heating": False,
    "fan": False,
    "light": False,

    # Phase 4P – sichere Startwerte der vier freien Universal-Aktoren.
    "aux1": False,
    "aux2": False,
    "aux3": False,
    "aux4": False,

    "ramp_active": False,
    "ramp_target": None,

    # Controller-weites Quellenverzeichnis. Für das bestehende Zelt bleibt
    # es wie bisher in live_state sichtbar. Weitere TentRuntime-Instanzen
    # lesen dieselben Quellen über core.sensor_sources, schreiben ihre
    # zugewiesenen Messwerte aber in ihren eigenen State.
    "sensor_sources": {},
}

_LIVE_STATE_TEMPLATE["energy"] = {
    "heating": {
        "power": None,
        "total": None,
    },
    "light": {
        "power": None,
        "total": None,
    },
}


def create_runtime_state():
    """Erzeugt einen vollständig unabhängigen Laufzeit-State.

    Der Default-Betrieb benutzt weiterhin dieses Modul selbst als State.
    Diese Factory ist die Grundlage für zusätzliche Zelte in den kommenden
    Phasen, ohne globale Modulvariablen teilen zu müssen.
    """

    return SimpleNamespace(
        live_state=deepcopy(_LIVE_STATE_TEMPLATE),

        heating_on=False,
        fan_on=False,
        light_on=False,
        vent_on=False,
        irrigation_on=False,
        humidifier_on=False,
        dehumidifier_on=False,
        light2_on=False,
        vent2_on=False,
        aux1_on=False,
        aux2_on=False,
        aux3_on=False,
        aux4_on=False,

        # Rohwerte
        last_temp_raw=None,
        last_hum_raw=None,

        # Korrigierte Werte (für Regelung & UI)
        last_ds_temp=None,
        last_hum=None,

        last_ds_time=0,
        last_dht_time=0,
        last_db_write=0,

        current_profile=None,

        # Rampe
        ramp_active=False,
        ramp_start_ts=None,
        ramp_end_ts=None,
        ramp_start_temp=None,
        ramp_target_temp=None,
        last_ramp_trigger_day=None,
        last_ramp_trigger_type=None,

        # Sensor Stale-Flags
        temp_stale=False,
        hum_stale=False,
    )


# =========================================
# 🧩 LEGACY / DEFAULT STATE = tent_1
# =========================================
# Diese Attribute bleiben absichtlich erhalten. Bestehende Routen und noch
# nicht migrierte Module können dadurch weiter ``import core.state as state``
# verwenden.

_default = create_runtime_state()

live_state = _default.live_state

heating_on = _default.heating_on
fan_on = _default.fan_on
light_on = _default.light_on
vent_on = _default.vent_on
irrigation_on = _default.irrigation_on
humidifier_on = _default.humidifier_on
dehumidifier_on = _default.dehumidifier_on
light2_on = _default.light2_on
vent2_on = _default.vent2_on
aux1_on = _default.aux1_on
aux2_on = _default.aux2_on
aux3_on = _default.aux3_on
aux4_on = _default.aux4_on

last_temp_raw = _default.last_temp_raw
last_hum_raw = _default.last_hum_raw
last_ds_temp = _default.last_ds_temp
last_hum = _default.last_hum
last_ds_time = _default.last_ds_time
last_dht_time = _default.last_dht_time
last_db_write = _default.last_db_write

current_profile = _default.current_profile

ramp_active = _default.ramp_active
ramp_start_ts = _default.ramp_start_ts
ramp_end_ts = _default.ramp_end_ts
ramp_start_temp = _default.ramp_start_temp
ramp_target_temp = _default.ramp_target_temp
last_ramp_trigger_day = _default.last_ramp_trigger_day
last_ramp_trigger_type = _default.last_ramp_trigger_type

temp_stale = _default.temp_stale
hum_stale = _default.hum_stale
