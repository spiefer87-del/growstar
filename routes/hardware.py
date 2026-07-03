from flask import jsonify

from services.hardware import hardware


def register(app):

    @app.post("/api/hardware/scan")
    def hardware_scan():

        print(">>> Hardware Scan angefordert")

        hardware.scan_gateways()

        return jsonify({
            "success": True,
            "gateways": len(hardware.gateways())
        })
