"""Read-only Versions- und Patch-Informationen für Growstar."""

from flask import jsonify, render_template

from core.release import current_release, release_history, release_summary


def register(app):

    @app.context_processor
    def inject_growstar_release():
        # Dadurch kann base.html die Version anzeigen, ohne dass jede Route
        # eigene Release-Daten übergeben muss.
        return {
            "growstar_release": release_summary(),
        }

    @app.route("/system/patch-notes")
    def patch_notes_page():
        return render_template(
            "patch_notes.html",
            current_release=current_release(),
            releases=release_history(),
        )

    @app.route("/api/system/version")
    def api_system_version():
        return jsonify(
            success=True,
            **release_summary(),
        )
