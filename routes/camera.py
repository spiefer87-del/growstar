"""Weboberfläche und API für lokale GrowCam-Snapshots."""

from flask import (
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from auth.database import write_audit
from auth.decorators import permission_required
from core.tents import manager as tent_manager
from services.growcam import (
    LATEST_IMAGE,
    capture_snapshot,
    public_config,
    save_config,
    status_snapshot,
)


def _audit(action, details=None):
    user = getattr(g, "current_user", None)
    try:
        write_audit(
            action=action,
            user_id=user["id"] if user else None,
            entity_type="growcam",
            entity_id="vsc-gcc4",
            details=details,
            ip_address=request.remote_addr,
        )
    except Exception:
        pass


def register(app):
    @app.get("/pflanzenmanagement/kamera")
    def growcam_page():
        return render_template(
            "plants/camera.html",
            camera=public_config(),
            camera_status=status_snapshot(),
            tents=tent_manager.list_tents(),
        )

    @app.post("/pflanzenmanagement/kamera/konfiguration")
    @permission_required("plants.edit")
    def growcam_configure():
        tent_id = str(request.form.get("tent_id") or "").strip()
        try:
            if not tent_manager.get(tent_id):
                raise ValueError("Die ausgewählte Station existiert nicht.")
            config = save_config({
                "enabled": request.form.get("enabled") == "1",
                "name": request.form.get("name"),
                "host": request.form.get("host"),
                "port": request.form.get("port"),
                "path": request.form.get("path"),
                "username": request.form.get("username"),
                "interval_sec": request.form.get("interval_sec"),
                "tent_id": tent_id,
            })
            _audit(
                "plants.growcam_configured",
                {
                    "enabled": config["enabled"],
                    "host": config["host"],
                    "port": config["port"],
                    "path": config["path"],
                    "tent_id": config["tent_id"],
                    "interval_sec": config["interval_sec"],
                },
            )
            flash("GrowCam-Konfiguration wurde gespeichert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("growcam_page"))

    @app.post("/pflanzenmanagement/kamera/aufnahme")
    @permission_required("plants.edit")
    def growcam_capture():
        result = capture_snapshot()
        if result.get("success"):
            _audit(
                "plants.growcam_snapshot",
                {
                    "width": result.get("width"),
                    "height": result.get("height"),
                },
            )
            flash("Aktuelles GrowCam-Bild wurde aufgenommen.", "success")
        else:
            flash(result.get("error") or "GrowCam-Aufnahme fehlgeschlagen.", "error")
        return redirect(url_for("growcam_page"))

    @app.get("/pflanzenmanagement/kamera/bild")
    def growcam_image():
        if not LATEST_IMAGE.is_file():
            abort(404)
        return send_file(
            LATEST_IMAGE,
            mimetype="image/jpeg",
            conditional=True,
            max_age=0,
        )

    @app.get("/api/plant-management/camera/status")
    def growcam_status_api():
        return jsonify({
            "success": True,
            "camera": status_snapshot(),
        })
