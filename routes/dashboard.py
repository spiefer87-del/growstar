from flask import abort, redirect, render_template, url_for

from core.tents import manager as tent_manager, validate_tent_id


def _tent_page_context(tent_id):
    """Liefert ausschließlich sichere Metadaten für die Zelt-Ansicht."""
    try:
        tent_id = validate_tent_id(tent_id)
    except ValueError:
        abort(404)

    tent = tent_manager.get(tent_id)
    if tent is None:
        abort(404)

    return {
        "tent_id": tent_id,
        "tent_name": tent.get("name") or tent_id,
        "default_tent_id": tent_manager.default_tent_id(),
    }


def register(app):

    # ================================================================
    # Growstar Main Dashboard
    # ================================================================

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")


    # ================================================================
    # Grow Control
    # ================================================================

    @app.route("/grow-control")
    def grow_control_dashboard():
        return render_template("grow_control_dashboard.html")


    # Kompatibler Einstieg für bestehende Links / Bookmarks.
    # Er zeigt weiterhin das Default-Zelt, jetzt aber über dieselbe
    # zeltbezogene Template-Logik wie alle weiteren Zelte.
    @app.route("/grow-control/live")
    def grow_control_live():
        # Rückwärtskompatibler Alias. Kanonisch benutzen ALLE Grow-Einheiten
        # dieselbe generische Route.
        return redirect(
            url_for(
                "grow_control_tent",
                tent_id=tent_manager.default_tent_id(),
            ),
            code=302,
        )


    @app.route("/grow-control/tents/<tent_id>")
    def grow_control_tent(tent_id):
        return render_template(
            "grow_control.html",
            **_tent_page_context(tent_id),
        )


    @app.route("/settings")
    def settings():
        from core.config import config
        return render_template("settings.html", config=config)


    @app.route("/sensoren")
    def sensoren_page():
        return render_template("sensoren.html")


    @app.route("/diagrams")
    def diagrams_page():
        return render_template("diagrams.html")


    @app.route("/temperature")
    def temperature_page():
        return render_template("temperature.html")


    @app.route("/humidity")
    def humidity_page():
        return render_template("humidity.html")


    @app.route("/vpd")
    def vpd_page():
        return render_template("vpd.html")


    @app.route("/ventilator")
    def ventilator_page():
        return render_template("ventilator.html")


    @app.route("/heizung")
    def heizung_page():
        return render_template("heizung.html")


    @app.route("/licht")
    def licht_page():
        return render_template("licht.html")


    @app.route("/abluft")
    def abluft_page():
        return render_template("abluft.html")


    @app.route("/system")
    def system_page():
        return render_template("system.html")


    @app.route("/design")
    def design_page():
        return render_template("design.html")


    @app.route("/energie")
    def energie_page():
        return render_template("energie.html")


    @app.route("/energie/settings")
    def energie_settings_page():
        return render_template("energie_settings.html")


    @app.route("/connections")
    def connections_page():
        return render_template("connections.html")


    @app.route("/watchdog")
    def watchdog_page():
        return render_template("watchdog.html")


    @app.route("/devices")
    def devices():
        return render_template("devices.html")


    @app.route("/devices/<gateway_id>")
    def gateway_page(gateway_id):
        return render_template(
            "gateway.html",
            gateway_id=gateway_id,
        )


    @app.route("/devices/blu/<device_id>")
    def bluetooth_device_page(device_id):
        return render_template(
            "blu_device.html",
            device_id=device_id,
        )
