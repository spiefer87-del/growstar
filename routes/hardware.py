from flask import jsonify

from services.hardware import hardware


def register(app):

    @app.post("/api/hardware/scan")
    def hardware_scan():

        found = hardware.scan_gateways()

        return jsonify({

            "success": True,

            "found": found,

            "gateways": len(
                hardware.gateways()
            )

        })

