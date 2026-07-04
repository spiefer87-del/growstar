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

    @app.route("/devices/<gateway_id>")
    def gateway_details(gateway_id):
    
        gateway = manager.gateway(gateway_id)
    
        if not gateway:
            abort(404)
    
        return render_template(
            "gateway.html",
            gateway=gateway
        )
