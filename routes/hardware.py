from flask import jsonify, request

from services.hardware import hardware
from core.hardware.shelly.provisioning import provisioning_discovery
from core.mqtt_sensor_devices import list_mqtt_sensor_devices
from core.hardware_assignments import hardware_snapshot
from core.tents import manager as tent_manager



def _assigned_actuator_views(gateway_rows, *, tents=None, snapshot_loader=None):
    """Verknüpft bestehende Stations-Zuordnungen read-only mit Gateway-Metadaten.

    Diese Darstellung ist ausschließlich für die Hardware-Oberfläche gedacht.
    Sie verändert weder Runtime-Konfiguration noch Aktor-/Safety-Logik und
    führt keine Netzwerkrequests aus. Gateway-Daten stammen nur aus dem bereits
    vorhandenen HardwareManager-Snapshot.
    """

    snapshot_loader = snapshot_loader or hardware_snapshot
    tents = tent_manager.list_tents() if tents is None else list(tents)

    gateway_by_ip = {}
    for gateway in gateway_rows or []:
        if not isinstance(gateway, dict):
            continue
        ip = str(gateway.get("ip") or "").strip().lower()
        if ip:
            gateway_by_ip[ip] = gateway

    result = []

    for tent in tents:
        if not isinstance(tent, dict):
            continue

        tent_id = str(tent.get("id") or "").strip()
        if not tent_id:
            continue

        try:
            snapshot = snapshot_loader(tent_id)
        except Exception:
            # Eine fehlerhafte/inzwischen entfernte Station darf die zentrale
            # Hardware-Uebersicht nicht komplett unbrauchbar machen.
            continue

        tent_name = str(snapshot.get("name") or tent.get("name") or tent_id)

        for assignment in (snapshot.get("assignments") or {}).values():
            if not isinstance(assignment, dict) or not assignment.get("configured"):
                continue

            ip = str(assignment.get("ip") or "").strip()
            if not ip:
                continue

            gateway = gateway_by_ip.get(ip.lower())
            gateway_view = None

            if gateway is not None:
                gateway_view = {
                    "id": gateway.get("id"),
                    "name": gateway.get("name"),
                    "model": gateway.get("model"),
                    "manufacturer": gateway.get("manufacturer"),
                    "ip": gateway.get("ip"),
                    "mac": gateway.get("mac"),
                    "online": bool(gateway.get("online")),
                    "firmware": gateway.get("firmware"),
                    "rssi": gateway.get("rssi"),
                    "uptime": gateway.get("uptime"),
                }

            result.append({
                "id": f"{tent_id}:{assignment.get('device') or ''}",
                "tent_id": tent_id,
                "tent_name": tent_name,
                "device": assignment.get("device"),
                "label": assignment.get("label") or assignment.get("device"),
                "icon": assignment.get("icon") or "🔌",
                "mode": assignment.get("mode") or "OFF",
                "ip": ip,
                "relay": assignment.get("relay"),
                "configured": True,
                "gateway_detected": gateway_view is not None,
                "gateway": gateway_view,
            })

    return result


def register(app):

    @app.post("/api/hardware/scan")
    def hardware_scan():

        data = request.get_json(
            silent=True
        ) or {}

        # Phase 4W:
        # Der bestehende Hardware-Scan-Endpunkt bleibt erhalten. Ein expliziter
        # Modus startet zusätzlich den lokalen Raspberry-Bluetooth-Discovery-
        # Adapter für fabrikneue Shellys. Diese Kandidaten werden NICHT in den
        # HardwareManager übernommen und nicht gepairt/provisioniert.
        if data.get("mode") == "provisioning":

            result = provisioning_discovery.scan(
                seconds=data.get("seconds")
            )

            return jsonify({
                "success": bool(result.get("success")),
                "mode": "provisioning",
                "result": result,
            })

        found = hardware.scan_gateways()

        return jsonify({
            "success": True,
            "mode": "gateways",
            "found": found,
            "gateways": len(hardware.gateways())
        })


    @app.get("/api/hardware/provisioning/status")
    def hardware_provisioning_status():

        return jsonify(
            provisioning_discovery.status()
        )


    @app.get("/api/hardware")
    def hardware_status():

        gateways = [
            gateway.to_dict()
            for gateway in hardware.gateways()
        ]

        return jsonify({

            "gateways": gateways,

            "devices": [
                device.to_dict()
                for device in hardware.devices()
            ],

            # Legacy HardwareManager-Aktoren bleiben unverändert erhalten.
            # Growstar-Aktorzuordnungen werden zusätzlich read-only aus den
            # bereits bestehenden stationsbezogenen Assignments dargestellt.
            "actuators": [
                actuator.to_dict()
                for actuator in hardware.actuators()
            ],

            "assigned_actuators": _assigned_actuator_views(
                gateways
            ),

            # Controller-weite MQTT-Sensorcontroller (Pico etc.).
            # Sie gehören bewusst zu keinem Zelt; die Zuordnung erfolgt erst
            # über SENSOR_ASSIGNMENTS.
            "mqtt_devices": list_mqtt_sensor_devices(),

        })

    @app.get("/api/hardware/<gateway_id>")
    def hardware_gateway(gateway_id):
    
        gateway = hardware.gateway(gateway_id)
    
        if gateway is None:
    
            return jsonify({
                "success": False
            }), 404
    
        return jsonify({
    
            "success": True,
    
            "gateway": gateway.to_dict()
    
        })

    @app.post("/api/hardware/device/<device_id>/setup-sensors")
    def hardware_device_setup_sensors(device_id):
    
        result = hardware.setup_ble_sensor(
            device_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)

    @app.post("/api/hardware/device/<device_id>/pair")
    def hardware_device_pair(device_id):
    
        data = request.get_json(
            silent=True
        ) or {}
    
        gateway_id = data.get(
            "gateway_id",
            "192.168.178.91"
        )
    
        result = hardware.pair_ble_device(
            device_id,
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)
    
    
    @app.post("/api/hardware/device/<device_id>/unpair")
    def hardware_device_unpair(device_id):
    
        result = hardware.unpair_ble_device(
            device_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)
    
    @app.post("/api/hardware/<gateway_id>/refresh")
    def refresh_gateway(gateway_id):
        
        gateway = hardware.refresh_gateway(gateway_id)
        
        if gateway is None:
        
            return jsonify({
                "success": False
            }), 404
        
        return jsonify({
        
            "success": True,
        
            "gateway": gateway.to_dict()
        
        })

    @app.post("/api/hardware/<gateway_id>/bluetooth/enable")
    def enable_bt(gateway_id):
    
        ok = hardware.enable_bluetooth(gateway_id)
    
        return jsonify({
            "success": bool(ok)
        })

    @app.post("/api/hardware/<gateway_id>/bluetooth/disable")
    def disable_bt(gateway_id):
    
        ok = hardware.disable_bluetooth(gateway_id)
    
        return jsonify({
            "success": bool(ok)
        })

    @app.get("/api/hardware/<gateway_id>/methods")
    def hardware_methods(gateway_id):
    
        methods = hardware.list_gateway_methods(
            gateway_id
        )
    
        if methods is None:
    
            return jsonify({
                "success": False
            }), 404
    
        return jsonify({
    
            "success": True,
    
            "methods": methods
    
        })

    @app.get("/api/hardware/device/<device_id>")
    def hardware_device(device_id):
    
        device = hardware.device(
            device_id
        )
    
        if device is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify({
            "success": True,
            "device": device.to_dict()
        })

    @app.post("/api/hardware/device/<device_id>/read-values")
    def hardware_device_read_values(device_id):
    
        result = hardware.read_ble_sensor_values(
            device_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)

    @app.post("/api/hardware/<gateway_id>/ble/scan")
    def ble_scan(gateway_id):
    
        result = hardware.start_ble_scan(
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "BLE Scan konnte nicht gestartet werden.",
                "result": None
            })
    
        return jsonify({
            "success": True,
            "result": result
        })

    @app.get("/api/hardware/<gateway_id>/ble/discovered")
    def ble_discovered(gateway_id):
    
        result = hardware.get_ble_scan_result(
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "BLE Scan Ergebnis konnte nicht geladen werden.",
                "result": None
            })
    
        return jsonify({
            "success": True,
            "result": result
        })
    
    
    @app.get("/api/hardware/<gateway_id>/ble/status")
    def ble_status(gateway_id):
    
        status = hardware.get_ble_status(
            gateway_id
        )
    
        if status is None:
    
            return jsonify({
                "success": False,
                "message": "BLE Status konnte nicht geladen werden.",
                "status": None
            })
    
        return jsonify({
            "success": True,
            "status": status
        })
    
    
    @app.get("/api/hardware/<gateway_id>/ble/objects")
    def ble_objects(gateway_id):
    
        objects = hardware.get_ble_objects(
            gateway_id
        )
    
        if objects is None:
    
            return jsonify({
                "success": False,
                "message": "BLE Objekte konnten nicht geladen werden.",
                "objects": None
            })
    
        return jsonify({
            "success": True,
            "objects": objects
        })

    @app.post("/api/hardware/<gateway_id>/ble/add-discovered")
    def ble_add_discovered(gateway_id):
    
        result = hardware.add_discovered_ble_devices(
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gateway nicht gefunden.",
                "result": None
            }), 404
    
        return jsonify({
            "success": True,
            "result": result
        })

    @app.post("/api/hardware/<gateway_id>/ble/register-discovered")
    def ble_register_discovered(gateway_id):
    
        result = hardware.register_discovered_ble_devices(
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gateway nicht gefunden.",
                "result": None
            }), 404
    
        return jsonify({
            "success": True,
            "result": result
        })

    @app.post("/api/hardware/<gateway_id>/ble/device/<device_id>/pair")
    def gateway_pair_ble_device(gateway_id, device_id):
    
        result = hardware.pair_ble_device(
            device_id,
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)
    
    
    @app.post("/api/hardware/<gateway_id>/ble/device/<device_id>/unpair")
    def gateway_unpair_ble_device(gateway_id, device_id):
    
        result = hardware.unpair_ble_device(
            device_id,
            gateway_id
        )
    
        if result is None:
    
            return jsonify({
                "success": False,
                "message": "Gerät nicht gefunden."
            }), 404
    
        return jsonify(result)
