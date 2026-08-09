from flask import abort, redirect, render_template, url_for

from core.tents import manager as tent_manager, validate_tent_id


_DEVICE_META = {
    "heating": {"label": "Heizung", "icon": "🔥"},
    "fan": {"label": "Lüfter", "icon": "💨"},
    "light": {"label": "Beleuchtung", "icon": "💡"},
    "vent": {"label": "Ventilator", "icon": "🌀"},
    "irrigation": {"label": "Bewässerung", "icon": "💧"},
    "humidifier": {"label": "Luftbefeuchter", "icon": "💦"},
    "dehumidifier": {"label": "Entfeuchter", "icon": "🌬️"},
    "light2": {"label": "Licht 2", "icon": "💡"},
    "vent2": {"label": "Ventilator 2", "icon": "🌀"},
}


def _tent_page_context(tent_id):
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


def _default_tent_url(endpoint, **values):
    return url_for(
        endpoint,
        tent_id=tent_manager.default_tent_id(),
        **values,
    )


def register(app):

    # ================================================================
    # Growstar Main Dashboard
    # ================================================================

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    # ================================================================
    # Grow Control Hub + generische Stationsseiten
    # ================================================================

    @app.route("/grow-control")
    def grow_control_dashboard():
        return render_template("grow_control_dashboard.html")

    @app.route("/grow-control/sensors")
    def grow_control_sensors_dashboard():
        return render_template("grow_control_sensors.html")

    @app.route("/grow-control/live")
    def grow_control_live():
        return redirect(
            _default_tent_url("grow_control_tent"),
            code=302,
        )

    @app.route("/grow-control/tents/<tent_id>")
    def grow_control_tent(tent_id):
        return render_template(
            "grow_control.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/temperature")
    def grow_control_tent_temperature(tent_id):
        return render_template(
            "temperature.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/humidity")
    def grow_control_tent_humidity(tent_id):
        return render_template(
            "humidity.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/vpd")
    def grow_control_tent_vpd(tent_id):
        return render_template(
            "vpd.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/settings")
    def grow_control_tent_settings(tent_id):
        return render_template(
            "settings.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/sensors")
    def grow_control_tent_sensors(tent_id):
        return render_template(
            "sensoren.html",
            **_tent_page_context(tent_id),
        )

    @app.route("/grow-control/tents/<tent_id>/devices/<device>")
    def grow_control_tent_device(tent_id, device):
        context = _tent_page_context(tent_id)
        meta = _DEVICE_META.get(device)
        if meta is None:
            abort(404)

        return render_template(
            "device_control.html",
            device_key=device,
            device_label=meta["label"],
            device_icon=meta["icon"],
            **context,
        )

    # ================================================================
    # Legacy URLs -> Default-Station
    # ================================================================

    @app.route("/settings")
    def settings():
        return redirect(_default_tent_url("grow_control_tent_settings"), code=302)

    @app.route("/sensoren")
    def sensoren_page():
        return redirect(_default_tent_url("grow_control_tent_sensors"), code=302)

    @app.route("/temperature")
    def temperature_page():
        return redirect(_default_tent_url("grow_control_tent_temperature"), code=302)

    @app.route("/humidity")
    def humidity_page():
        return redirect(_default_tent_url("grow_control_tent_humidity"), code=302)

    @app.route("/vpd")
    def vpd_page():
        return redirect(_default_tent_url("grow_control_tent_vpd"), code=302)

    @app.route("/heizung")
    def heizung_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="heating"), code=302)

    @app.route("/abluft")
    def abluft_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="fan"), code=302)

    @app.route("/licht")
    def licht_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="light"), code=302)

    @app.route("/ventilator")
    def ventilator_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="vent"), code=302)

    @app.route("/bewaesserung")
    def bewaesserung_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="irrigation"), code=302)

    @app.route("/luftbefeuchter")
    def luftbefeuchter_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="humidifier"), code=302)

    @app.route("/luftentfeuchter")
    def luftentfeuchter_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="dehumidifier"), code=302)

    @app.route("/licht2")
    def licht2_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="light2"), code=302)

    @app.route("/ventilator2")
    def ventilator2_page():
        return redirect(_default_tent_url("grow_control_tent_device", device="vent2"), code=302)

    # ================================================================
    # Weitere bestehende globale Module
    # ================================================================

    @app.route("/diagrams")
    def diagrams_page():
        return render_template("diagrams.html")

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
        return render_template("gateway.html", gateway_id=gateway_id)

    @app.route("/devices/blu/<device_id>")
    def bluetooth_device_page(device_id):
        return render_template("blu_device.html", device_id=device_id)
