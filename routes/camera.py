"""Weboberfläche und API für lokale GrowCam-Snapshots."""

from flask import (
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    stream_with_context,
    url_for,
)

from auth.database import write_audit
from auth.decorators import permission_required
from core.tents import manager as tent_manager
from plant_management.database import get_batch, list_batches
from services.growcam import (
    LATEST_IMAGE,
    capture_snapshot,
    delete_timelapse_frame,
    list_timelapse_frames,
    mjpeg_stream,
    public_config,
    resolve_timelapse_video,
    resolve_timelapse_frame,
    save_config,
    status_snapshot,
    start_timelapse_render,
    timelapse_summary,
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
        camera = public_config()
        camera_status = status_snapshot()
        requested_batch_id = request.args.get("batch_id", type=int)
        if requested_batch_id and get_batch(requested_batch_id):
            camera["batch_id"] = requested_batch_id
            camera_status["batch_id"] = requested_batch_id
            camera_status["timelapse"] = timelapse_summary(requested_batch_id)
        frame_page = request.args.get("frame_page", default=1, type=int)
        return render_template(
            "plants/camera.html",
            camera=camera,
            camera_status=camera_status,
            tents=tent_manager.list_tents(),
            batches=list_batches(),
            timelapse_frames=list_timelapse_frames(
                camera.get("batch_id"), page=frame_page
            ),
        )

    @app.post("/pflanzenmanagement/kamera/konfiguration")
    @permission_required("plants.edit")
    def growcam_configure():
        tent_id = str(request.form.get("tent_id") or "").strip()
        try:
            if not tent_manager.get(tent_id):
                raise ValueError("Die ausgewählte Station existiert nicht.")
            batch_id = request.form.get("batch_id", type=int)
            if batch_id and not get_batch(batch_id):
                raise ValueError("Der ausgewählte Durchgang existiert nicht.")
            config = save_config({
                "enabled": request.form.get("enabled") == "1",
                "name": request.form.get("name"),
                "host": request.form.get("host"),
                "port": request.form.get("port"),
                "path": request.form.get("path"),
                "username": request.form.get("username"),
                "interval_sec": request.form.get("interval_sec"),
                "tent_id": tent_id,
                "batch_id": batch_id,
                "timelapse_enabled": request.form.get("timelapse_enabled") == "1",
                "timelapse_interval_sec": request.form.get("timelapse_interval_sec"),
                "retention_days": request.form.get("retention_days"),
                "live_width": request.form.get("live_width"),
                "live_fps": request.form.get("live_fps"),
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
                    "batch_id": config["batch_id"],
                    "timelapse_enabled": config["timelapse_enabled"],
                    "timelapse_interval_sec": config["timelapse_interval_sec"],
                },
            )
            flash("GrowCam-Konfiguration wurde gespeichert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("growcam_page"))

    @app.post("/pflanzenmanagement/kamera/aufnahme")
    @permission_required("plants.edit")
    def growcam_capture():
        result = capture_snapshot(archive=True)
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

    @app.get("/pflanzenmanagement/kamera/live.mjpg")
    def growcam_live():
        config = public_config()
        if not config.get("enabled") or not config.get("host"):
            abort(503)
        response = Response(
            stream_with_context(mjpeg_stream()),
            mimetype="multipart/x-mixed-replace; boundary=growcam",
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.get("/pflanzenmanagement/kamera/live")
    def growcam_live_viewer():
        camera = public_config()
        if not camera.get("enabled") or not camera.get("host"):
            abort(404)

        tent = tent_manager.get(str(camera.get("tent_id") or ""))
        return render_template(
            "plants/camera_live.html",
            camera=camera,
            tent_name=(tent or {}).get("name") or camera.get("tent_id"),
        )

    @app.post("/pflanzenmanagement/kamera/zeitraffer")
    @permission_required("plants.edit")
    def growcam_timelapse_create():
        result = start_timelapse_render({
            "video_fps": request.form.get("video_fps"),
            "video_width": request.form.get("video_width"),
            "video_crf": request.form.get("video_crf"),
        })
        if result.get("success"):
            _audit(
                "plants.growcam_timelapse_started",
                {
                    "batch_id": public_config().get("batch_id"),
                    "frame_count": result.get("frame_count"),
                    "options": result.get("options"),
                },
            )
            flash("Zeitraffer-Erstellung wurde im Hintergrund gestartet.", "success")
        else:
            flash(result.get("error") or "Zeitraffer konnte nicht gestartet werden.", "error")
        return redirect(url_for("growcam_page"))

    @app.get("/pflanzenmanagement/kamera/zeitraffer/<int:batch_id>/<filename>")
    def growcam_timelapse_video(batch_id, filename):
        video = resolve_timelapse_video(batch_id, filename)
        if video is None:
            abort(404)
        return send_file(video, mimetype="video/mp4", conditional=True)

    @app.get("/pflanzenmanagement/kamera/zeitraffer-bild/<int:batch_id>/<filename>")
    def growcam_timelapse_frame(batch_id, filename):
        frame = resolve_timelapse_frame(
            batch_id,
            filename,
            thumbnail=request.args.get("thumbnail") == "1",
        )
        if frame is None:
            abort(404)
        return send_file(frame, mimetype="image/jpeg", conditional=True, max_age=3600)

    @app.post("/pflanzenmanagement/kamera/zeitraffer-bild/<int:batch_id>/<filename>/loeschen")
    @permission_required("plants.edit")
    def growcam_timelapse_frame_delete(batch_id, filename):
        result = delete_timelapse_frame(batch_id, filename)
        if result.get("success"):
            _audit(
                "plants.growcam_timelapse_frame_deleted",
                {"batch_id": batch_id, "filename": result.get("filename")},
            )
            flash("Zeitrafferbild wurde entfernt.", "success")
        else:
            flash(result.get("error") or "Bild konnte nicht entfernt werden.", "error")
        return redirect(
            url_for(
                "growcam_page",
                batch_id=batch_id,
                frame_page=request.form.get("frame_page", type=int) or 1,
            )
        )

    @app.get("/api/plant-management/camera/status")
    def growcam_status_api():
        return jsonify({
            "success": True,
            "camera": status_snapshot(),
        })
