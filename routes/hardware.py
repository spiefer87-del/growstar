from flask import jsonify

from services.hardware import hardware


def register(app):

    @app.post("/api/hardware/scan")
    def hardware_scan():

        found = hardware.scan_gateways()

        return jsonify({
            "success": True,
            "found": found,
            "gateways": len(hardware.gateways())
        })


    @app.get("/api/hardware")
    def hardware_status():

        return jsonify({

            "gateways": [
                gateway.to_dict()
                for gateway in hardware.gateways()
            ],

            "devices": [
                device.to_dict()
                for device in hardware.devices()
            ],

            "actuators": [
                actuator.to_dict()
                for actuator in hardware.actuators()
            ]

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

    @app.post("/api/hardware/<gateway_id>/ble/scan")
    def ble_scan(gateway_id):
    
        result = hardware.start_ble_scan(
            gateway_id
        )
    
        return jsonify({
    
            "success": result is not None,
    
            "result": result
    
        })

    @app.get("/api/hardware/<gateway_id>/ble/status")
    def ble_status(gateway_id):
    
        status = hardware.ble_status(
            gateway_id
        )
    
        return jsonify({
    
            "success": status is not None,
    
            "status": status
    
        })

    @app.get("/api/hardware/<gateway_id>/ble/objects")
    def ble_objects(gateway_id):
    
        objects = hardware.ble_objects(
            gateway_id
        )
    
        return jsonify({
    
            "success": objects is not None,
    
            "objects": objects
    
        })
