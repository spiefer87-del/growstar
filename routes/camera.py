"""Weboberfläche und API für lokale GrowCam-Snapshots."""

import shutil
from pathlib import Path

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
from plant_management.photos import (
    list_batch_photos,
    list_plant_photos,
    photo_storage_summary,
)
from services.growcam import (
    camera_for_tent,
    capture_snapshot,
    create_camera,
    delete_recording,
    delete_timelapse_frame,
    delete_timelapse_video,
    growcam_storage_summary,
    latest_image_path,
    list_all_timelapse_frames,
    list_public_configs,
    list_recordings,
    list_timelapse_frames,
    list_timelapse_videos,
    mjpeg_stream,
    next_timelapse_capture_label,
    public_config,
    resolve_recording,
    resolve_timelapse_video,
    resolve_timelapse_frame,
    save_config,
    status_snapshot,
    start_timelapse_render,
    start_video_recording,
    timelapse_frame_days,
    timelapse_download_filename,
    timelapse_summary,
)


ROOT = Path(__file__).resolve().parent.parent


def _audit(action, details=None, *, camera_id="camera_1"):
    user = getattr(g, "current_user", None)
    try:
        write_audit(
            action=action,
            user_id=user["id"] if user else None,
            entity_type="growcam",
            entity_id=camera_id,
            details=details,
            ip_address=request.remote_addr,
        )
    except Exception:
        pass


def register(app):
    def selected_camera():
        camera_id = request.values.get("camera_id")
        camera = public_config(camera_id)
        if camera is None:
            abort(404)
        return camera

    @app.get("/pflanzenmanagement/kamera")
    def growcam_page():
        camera = selected_camera()
        camera_id = camera["camera_id"]
        camera_status = status_snapshot(camera_id)
        return render_template(
            "plants/camera.html",
            camera=camera,
            cameras=list_public_configs(),
            camera_status=camera_status,
            tents=tent_manager.list_tents(),
            batches=list_batches(),
            camera_recordings=list_recordings(
                camera_id=camera_id, page=1, per_page=6
            ),
        )

    @app.get("/pflanzenmanagement/zeitraffer")
    def growcam_timelapse_page():
        camera = selected_camera()
        camera_id = camera["camera_id"]
        camera_status = status_snapshot(camera_id)
        requested_batch_id = request.args.get("batch_id", type=int)
        if requested_batch_id and get_batch(requested_batch_id):
            camera["batch_id"] = requested_batch_id
            camera_status["batch_id"] = requested_batch_id
            camera_status["timelapse"] = timelapse_summary(
                requested_batch_id, camera_id=camera_id
            )
        frame_page = request.args.get("frame_page", default=1, type=int)
        return render_template(
            "plants/timelapse.html",
            camera=camera,
            cameras=list_public_configs(),
            camera_status=camera_status,
            batches=list_batches(include_archived=True),
            timelapse_frames=list_timelapse_frames(
                camera.get("batch_id"), camera_id=camera_id, page=frame_page
            ),
            frame_day_counts=timelapse_frame_days(camera.get("batch_id"), camera_id=camera_id),
            recent_videos=list_timelapse_videos(camera.get("batch_id"), camera_id=camera_id, per_page=6)["items"] if camera.get("batch_id") else [],
            next_timelapse_capture=next_timelapse_capture_label(camera),
        )

    @app.post("/pflanzenmanagement/zeitraffer/aktivieren")
    @permission_required("plants.edit")
    def growcam_timelapse_toggle():
        current = selected_camera()
        camera_id = current["camera_id"]
        enabled = request.form.get("enabled") == "1"
        try:
            config = save_config({**current, "timelapse_enabled": enabled}, camera_id=camera_id)
            _audit("plants.growcam_timelapse_configured", {
                "batch_id": config["batch_id"], "enabled": config["timelapse_enabled"],
            }, camera_id=camera_id)
            flash("Zeitraffer-Aufnahmen aktiviert." if enabled else "Zeitraffer-Aufnahmen deaktiviert.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("growcam_timelapse_page", camera_id=camera_id, plan=1, _anchor="timelapse-plan"))
        return redirect(url_for("growcam_timelapse_page", camera_id=camera_id))

    @app.post("/pflanzenmanagement/kamera/konfiguration")
    @permission_required("plants.edit")
    def growcam_configure():
        current = selected_camera()
        camera_id = current["camera_id"]
        tent_id = str(request.form.get("tent_id") or "").strip()
        try:
            if not tent_manager.get(tent_id):
                raise ValueError("Die ausgewählte Station existiert nicht.")
            duplicate = camera_for_tent(tent_id, enabled_only=False)
            if duplicate and duplicate["camera_id"] != camera_id:
                raise ValueError("Dieser Station ist bereits eine Kamera zugeordnet.")
            config = save_config({
                **current,
                "enabled": request.form.get("enabled") == "1",
                "interval_sec": request.form.get("interval_sec"),
                "tent_id": tent_id,
                "live_width": request.form.get("live_width"),
                "live_fps": request.form.get("live_fps"),
            }, camera_id=camera_id)
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
                    "video_retention_count": config["video_retention_count"],
                },
                camera_id=camera_id,
            )
            flash("GrowCam-Konfiguration wurde gespeichert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("growcam_page", camera_id=camera_id))

    @app.post("/pflanzenmanagement/zeitraffer/konfiguration")
    @permission_required("plants.edit")
    def growcam_timelapse_configure():
        current = selected_camera()
        camera_id = current["camera_id"]
        try:
            batch_id = request.form.get("batch_id", type=int)
            if batch_id and not get_batch(batch_id):
                raise ValueError("Der ausgewählte Durchgang existiert nicht.")
            config = save_config({
                **current,
                "batch_id": batch_id,
                "timelapse_enabled": current["timelapse_enabled"],
                "timelapse_interval_sec": request.form.get("timelapse_interval_sec"),
                "timelapse_start_time": request.form.get("timelapse_start_time"),
                "retention_days": request.form.get("retention_days"),
                "video_retention_count": request.form.get("video_retention_count"),
            }, camera_id=camera_id)
            _audit(
                "plants.growcam_timelapse_configured",
                {
                    "batch_id": config["batch_id"],
                    "enabled": config["timelapse_enabled"],
                    "interval_sec": config["timelapse_interval_sec"],
                    "start_time": config["timelapse_start_time"],
                },
                camera_id=camera_id,
            )
            flash("Zeitraffer-Konfiguration wurde gespeichert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("growcam_timelapse_page", camera_id=camera_id, plan=1, _anchor="timelapse-plan"))

    @app.post("/devices/growcam/hinzufuegen")
    @app.post("/grow-control/connections/growcam/hinzufuegen")
    @permission_required("hardware.configure")
    def growcam_hardware_add():
        tent_id = str(request.form.get("tent_id") or "").strip()
        try:
            tent = tent_manager.get(tent_id)
            if not tent:
                raise ValueError("Die ausgewählte Station existiert nicht.")
            existing = camera_for_tent(tent_id, enabled_only=False)
            if existing:
                raise ValueError("Dieser Station ist bereits eine Kamera zugeordnet.")
            camera = create_camera({
                "enabled": True,
                "name": request.form.get("name") or f"GrowCam {tent.get('name') or tent_id}",
                "host": request.form.get("host"),
                "tent_id": tent_id,
            })
            _audit(
                "hardware.growcam_added",
                {"host": camera["host"], "tent_id": tent_id},
                camera_id=camera["camera_id"],
            )
            flash("GrowCam wurde hinzugefügt und aktiviert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("grow_control_connections", _anchor="growcam-connection"))

    @app.post("/devices/growcam/konfiguration")
    @app.post("/grow-control/connections/growcam/konfiguration")
    @permission_required("hardware.configure")
    def growcam_hardware_configure():
        current = selected_camera()
        camera_id = current["camera_id"]
        try:
            tent_id = str(request.form.get("tent_id") or current.get("tent_id") or "").strip()
            if not tent_manager.get(tent_id):
                raise ValueError("Die ausgewählte Station existiert nicht.")
            duplicate = camera_for_tent(tent_id, enabled_only=False)
            if duplicate and duplicate["camera_id"] != camera_id:
                raise ValueError("Dieser Station ist bereits eine Kamera zugeordnet.")
            config = save_config({
                **current,
                "name": request.form.get("name"),
                "host": request.form.get("host"),
                "port": request.form.get("port"),
                "path": request.form.get("path"),
                "username": request.form.get("username"),
                "tent_id": tent_id,
            }, camera_id=camera_id)
            _audit(
                "hardware.growcam_connection_configured",
                {
                    "host": config["host"],
                    "port": config["port"],
                    "path": config["path"],
                },
                camera_id=camera_id,
            )
            flash("GrowCam-Verbindung wurde gespeichert.", "success")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("grow_control_connections", _anchor="growcam-connection"))

    @app.post("/pflanzenmanagement/kamera/aufnahme")
    @permission_required("plants.edit")
    def growcam_capture():
        camera = selected_camera()
        camera_id = camera["camera_id"]
        result = capture_snapshot(archive=True, camera_id=camera_id)
        if result.get("success"):
            _audit(
                "plants.growcam_snapshot",
                {
                    "width": result.get("width"),
                    "height": result.get("height"),
                },
                camera_id=camera_id,
            )
            flash("Aktuelles GrowCam-Bild wurde aufgenommen.", "success")
        else:
            flash(result.get("error") or "GrowCam-Aufnahme fehlgeschlagen.", "error")
        return redirect(url_for("growcam_page", camera_id=camera_id))

    @app.post("/pflanzenmanagement/kamera/video-aufnahme")
    @permission_required("plants.edit")
    def growcam_recording_start():
        camera = selected_camera()
        camera_id = camera["camera_id"]
        batch_id = request.form.get("batch_id", type=int)
        if not batch_id or not get_batch(batch_id):
            flash("Bitte einen vorhandenen Durchgang auswählen.", "error")
        else:
            result = start_video_recording(
                request.form.get("duration_sec"),
                batch_id,
                camera_id=camera_id,
            )
            if result.get("success"):
                _audit(
                    "plants.growcam_recording_started",
                    {
                        "batch_id": batch_id,
                        "duration_sec": result["duration_sec"],
                    },
                    camera_id=camera_id,
                )
                flash("Videoaufnahme wurde gestartet und wird im Hintergrund gespeichert.", "success")
            else:
                flash(result.get("error") or "Videoaufnahme konnte nicht gestartet werden.", "error")
        return redirect(url_for("growcam_page", camera_id=camera_id))

    @app.get("/pflanzenmanagement/kamera/video/<camera_id>/<int:batch_id>/<filename>")
    def growcam_recording_file(camera_id, batch_id, filename):
        try:
            video = resolve_recording(camera_id, batch_id, filename)
        except (TypeError, ValueError):
            video = None
        if video is None:
            abort(404)
        download = request.args.get("download") == "1"
        return send_file(
            video,
            mimetype="video/mp4",
            conditional=True,
            as_attachment=download,
            download_name=video.name if download else None,
        )

    @app.post("/pflanzenmanagement/kamera/video/<camera_id>/<int:batch_id>/<filename>/loeschen")
    @permission_required("plants.edit")
    def growcam_recording_delete(camera_id, batch_id, filename):
        try:
            result = delete_recording(camera_id, batch_id, filename)
        except (TypeError, ValueError):
            result = {"success": False, "error": "Videoaufnahme wurde nicht gefunden."}
        if result.get("success"):
            _audit(
                "plants.growcam_recording_deleted",
                {"batch_id": batch_id, "filename": result["filename"]},
                camera_id=camera_id,
            )
            flash("Videoaufnahme wurde gelöscht.", "success")
        else:
            flash(result.get("error") or "Videoaufnahme konnte nicht gelöscht werden.", "error")
        return redirect(url_for(
            "plant_media_explorer",
            kind="recordings",
            page=request.form.get("page", type=int) or 1,
        ))

    @app.get("/pflanzenmanagement/kamera/bild")
    def growcam_image():
        camera = selected_camera()
        image = latest_image_path(camera["camera_id"])
        if not image.is_file():
            abort(404)
        return send_file(
            image,
            mimetype="image/jpeg",
            conditional=True,
            max_age=0,
        )

    @app.get("/pflanzenmanagement/kamera/live.mjpg")
    def growcam_live():
        config = selected_camera()
        if not config.get("enabled") or not config.get("host"):
            abort(503)
        response = Response(
            stream_with_context(mjpeg_stream(config["camera_id"])),
            mimetype="multipart/x-mixed-replace; boundary=growcam",
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.get("/pflanzenmanagement/kamera/live")
    def growcam_live_viewer():
        camera = selected_camera()
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
        camera = selected_camera()
        camera_id = camera["camera_id"]
        result = start_timelapse_render({
            "video_fps": request.form.get("video_fps"),
            "video_width": request.form.get("video_width"),
            "video_crf": request.form.get("video_crf"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
        }, camera_id=camera_id)
        if result.get("success"):
            _audit(
                "plants.growcam_timelapse_started",
                {
                    "batch_id": camera.get("batch_id"),
                    "frame_count": result.get("frame_count"),
                    "options": result.get("options"),
                },
                camera_id=camera_id,
            )
            flash("Zeitraffer-Erstellung wurde im Hintergrund gestartet.", "success")
        else:
            flash(result.get("error") or "Zeitraffer konnte nicht gestartet werden.", "error")
        return redirect(url_for("growcam_timelapse_page", camera_id=camera_id, create=1, _anchor="video-create"))

    @app.get("/pflanzenmanagement/kamera/zeitraffer/<int:batch_id>/<filename>")
    def growcam_timelapse_video(batch_id, filename):
        camera = selected_camera()
        video = resolve_timelapse_video(
            batch_id, filename, camera_id=camera["camera_id"]
        )
        if video is None:
            abort(404)
        download = request.args.get("download") == "1"
        return send_file(
            video,
            mimetype="video/mp4",
            conditional=True,
            as_attachment=download,
            download_name=timelapse_download_filename(video, camera.get("tent_id"), camera_id=camera["camera_id"]) if download else None,
        )

    @app.post("/pflanzenmanagement/kamera/zeitraffer/<int:batch_id>/<filename>/loeschen")
    @permission_required("plants.edit")
    def growcam_timelapse_video_delete(batch_id, filename):
        camera = selected_camera()
        camera_id = camera["camera_id"]
        result = delete_timelapse_video(
            batch_id, filename, camera_id=camera_id
        )
        if result.get("success"):
            _audit(
                "plants.growcam_timelapse_video_deleted",
                {"batch_id": batch_id, "filename": result.get("filename")},
                camera_id=camera_id,
            )
            flash("Zeitraffer-Video wurde dauerhaft entfernt.", "success")
        else:
            flash(result.get("error") or "Video konnte nicht entfernt werden.", "error")
        if request.form.get("return_to") == "timelapse":
            return redirect(url_for(
                "growcam_timelapse_page", camera_id=camera_id, batch_id=batch_id
            ))
        return redirect(
            url_for(
                "plant_media_explorer",
                kind="videos",
                page=request.form.get("page", type=int) or 1,
            )
        )

    @app.get("/pflanzenmanagement/kamera/zeitraffer-bild/<int:batch_id>/<filename>")
    def growcam_timelapse_frame(batch_id, filename):
        camera = selected_camera()
        download = request.args.get("download") == "1"
        frame = resolve_timelapse_frame(
            batch_id,
            filename,
            camera_id=camera["camera_id"],
            thumbnail=request.args.get("thumbnail") == "1" and not download,
        )
        if frame is None:
            abort(404)
        return send_file(
            frame,
            mimetype="image/jpeg",
            conditional=True,
            max_age=3600,
            as_attachment=download,
            download_name=frame.name if download else None,
        )

    @app.post("/pflanzenmanagement/kamera/zeitraffer-bild/<int:batch_id>/<filename>/loeschen")
    @permission_required("plants.edit")
    def growcam_timelapse_frame_delete(batch_id, filename):
        camera = selected_camera()
        camera_id = camera["camera_id"]
        result = delete_timelapse_frame(
            batch_id, filename, camera_id=camera_id
        )
        if result.get("success"):
            _audit(
                "plants.growcam_timelapse_frame_deleted",
                {"batch_id": batch_id, "filename": result.get("filename")},
                camera_id=camera_id,
            )
            flash("Zeitrafferbild wurde entfernt.", "success")
        else:
            flash(result.get("error") or "Bild konnte nicht entfernt werden.", "error")
        if request.form.get("return_to") == "media":
            return redirect(
                url_for(
                    "plant_media_explorer",
                    kind="timelapse_frames",
                    page=request.form.get("page", type=int) or 1,
                )
            )
        return redirect(
            url_for(
                "growcam_timelapse_page",
                camera_id=camera_id,
                batch_id=batch_id,
                frame_page=request.form.get("frame_page", type=int) or 1,
            )
        )

    @app.get("/pflanzenmanagement/medien")
    def plant_media_explorer():
        kind = request.args.get("kind") or "videos"
        if kind not in {
            "recordings", "videos", "timelapse_frames", "plant_photos", "batch_photos"
        }:
            kind = "videos"
        page = max(1, request.args.get("page", default=1, type=int) or 1)
        per_page = 24
        camera_storage = growcam_storage_summary()
        photo_storage = photo_storage_summary()
        batches = list_batches(include_archived=True)
        batch_by_id = {int(batch["id"]): batch for batch in batches}
        camera_by_id = {
            camera["camera_id"]: camera for camera in list_public_configs()
        }

        if kind == "recordings":
            media_page = list_recordings(page=page, per_page=per_page)
            for item in media_page["items"]:
                item["batch"] = batch_by_id.get(item["batch_id"])
                item["camera"] = camera_by_id.get(item["camera_id"])
        elif kind == "videos":
            media_page = list_timelapse_videos(page=page, per_page=per_page)
            for item in media_page["items"]:
                item["batch"] = batch_by_id.get(item["batch_id"])
                item["camera"] = camera_by_id.get(item["camera_id"])
        elif kind == "timelapse_frames":
            media_page = list_all_timelapse_frames(page=page, per_page=per_page)
            for item in media_page["items"]:
                item["batch"] = batch_by_id.get(item["batch_id"])
                item["camera"] = camera_by_id.get(item["camera_id"])
        else:
            total = (
                photo_storage["plant_count"]
                if kind == "plant_photos"
                else photo_storage["batch_count"]
            )
            pages = (total + per_page - 1) // per_page
            page = max(1, min(page, pages or 1))
            loader = list_plant_photos if kind == "plant_photos" else list_batch_photos
            items = loader(limit=per_page, offset=(page - 1) * per_page)
            media_page = {
                "items": items,
                "page": page,
                "pages": pages,
                "total": total,
            }

        disk = shutil.disk_usage(ROOT)
        managed_bytes = camera_storage["total_bytes"] + photo_storage["total_bytes"]
        return render_template(
            "plants/media_explorer.html",
            kind=kind,
            media_page=media_page,
            camera_storage=camera_storage,
            photo_storage=photo_storage,
            managed_bytes=managed_bytes,
            disk={"total": disk.total, "used": disk.used, "free": disk.free},
        )

    @app.get("/api/plant-management/camera/status")
    def growcam_status_api():
        camera = selected_camera()
        return jsonify({
            "success": True,
            "camera": status_snapshot(camera["camera_id"]),
        })
