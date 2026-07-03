from flask import render_template
from services.hardware import hardware

from core.hardware.manager import manager
from core.hardware.models import Device


def register(app):

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")


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


    @app.route("/pflanzendaten")
    def pflanzendaten_page():
        return render_template("pflanzendaten.html")


    @app.route("/energie/settings")
    def energie_settings_page():
        return render_template("energie_settings.html")


    @app.route("/connections")
    def connections_page():
        return render_template("connections.html")


    @app.route("/tagebuch")
    def tagebuch_page():
        return render_template("tagebuch.html")


    @app.route("/watchdog")
    def watchdog_page():
        return render_template("watchdog.html")
    
    @app.route("/devices")
    def devices():
    
        return render_template(
            "devices.html",
            devices=hardware.devices()
        )
