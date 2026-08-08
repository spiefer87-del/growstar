from flask import render_template


def register(app):
    """
    UI-Routen des Pflanzenmanagements.

    Die Daten-APIs bleiben weiterhin getrennt in:
      - routes/plants.py
      - routes/diary.py
    """

    @app.route("/pflanzenmanagement")
    def plant_management_dashboard():
        return render_template("plants/dashboard.html")


    @app.route("/pflanzendaten")
    def pflanzendaten_page():
        return render_template("pflanzendaten.html")


    @app.route("/tagebuch")
    def tagebuch_page():
        return render_template("tagebuch.html")
