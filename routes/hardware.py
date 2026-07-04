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
