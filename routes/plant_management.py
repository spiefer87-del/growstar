from flask import (
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from auth.database import write_audit
from auth.decorators import permission_required
from plant_management.constants import (
    STAGES,
    STAGE_LABELS,
    STAGE_COLORS,
    PLANT_STATUSES,
    BATCH_STATUSES,
)
from plant_management.database import (
    get_dashboard,
    get_timeline,
    list_cultivars,
    get_cultivar,
    save_cultivar,
    list_batches,
    get_batch,
    save_batch,
    list_plants,
    get_plant,
    save_plant,
    set_plant_stage,
    set_plant_status,
    get_stage_events,
)
from plant_management.excel_io import (
    export_cultivars_xlsx,
    template_xlsx,
    import_cultivars_xlsx,
)


MAX_EXCEL_BYTES = 10 * 1024 * 1024


def _audit(action, entity_type=None, entity_id=None, details=None):
    user = getattr(g, "current_user", None)
    try:
        write_audit(
            action=action,
            user_id=user["id"] if user else None,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr,
        )
    except Exception:
        pass


def _form_data():
    return request.form.to_dict(flat=True)


def register(app):

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement")
    def plant_management_dashboard():
        data = get_dashboard()
        return render_template(
            "plants/dashboard.html",
            **data,
            stages=STAGES,
        )


    # ------------------------------------------------------------------
    # Sortenstamm
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/sorten")
    def cultivar_list():
        cultivars = list_cultivars(
            include_inactive=True,
            search=request.args.get("q"),
        )
        return render_template(
            "plants/cultivars.html",
            cultivars=cultivars,
            query=request.args.get("q", ""),
        )


    @app.route(
        "/pflanzenmanagement/sorten/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def cultivar_new():
        if request.method == "POST":
            try:
                cultivar_id = save_cultivar(_form_data())
                _audit(
                    "plants.cultivar_created",
                    "cultivar",
                    cultivar_id,
                )
                flash("Sorte wurde angelegt.", "success")
                return redirect(
                    url_for("cultivar_edit", cultivar_id=cultivar_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/cultivar_form.html",
            cultivar=None,
        )


    @app.route(
        "/pflanzenmanagement/sorten/<int:cultivar_id>",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def cultivar_edit(cultivar_id):
        cultivar = get_cultivar(cultivar_id)
        if not cultivar:
            abort(404)

        if request.method == "POST":
            try:
                save_cultivar(_form_data(), cultivar_id)
                _audit(
                    "plants.cultivar_updated",
                    "cultivar",
                    cultivar_id,
                )
                flash("Sorte wurde gespeichert.", "success")
                return redirect(
                    url_for("cultivar_edit", cultivar_id=cultivar_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/cultivar_form.html",
            cultivar=get_cultivar(cultivar_id),
        )


    @app.route("/pflanzenmanagement/sorten/export.xlsx")
    def cultivar_export():
        stream = export_cultivars_xlsx()
        _audit("plants.cultivar_exported", "cultivar")
        return send_file(
            stream,
            as_attachment=True,
            download_name="growstar_sortenstamm.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


    @app.route("/pflanzenmanagement/sorten/vorlage.xlsx")
    def cultivar_template():
        return send_file(
            template_xlsx(),
            as_attachment=True,
            download_name="growstar_sorten_importvorlage.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


    @app.route(
        "/pflanzenmanagement/sorten/import",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def cultivar_import():
        result = None

        if request.method == "POST":
            if request.content_length and request.content_length > MAX_EXCEL_BYTES:
                flash("Die Excel-Datei ist größer als 10 MB.", "error")
                return redirect(url_for("cultivar_import"))

            upload = request.files.get("file")
            if not upload or not upload.filename:
                flash("Bitte eine Excel-Datei auswählen.", "error")
            elif not upload.filename.lower().endswith(".xlsx"):
                flash("Es werden nur .xlsx-Dateien unterstützt.", "error")
            else:
                try:
                    result = import_cultivars_xlsx(upload.stream)
                    _audit(
                        "plants.cultivar_imported",
                        "cultivar",
                        details=result,
                    )
                    flash(
                        f"Import abgeschlossen: {result['created']} neu, "
                        f"{result['updated']} aktualisiert, "
                        f"{result['skipped']} übersprungen.",
                        "success",
                    )
                except Exception as exc:
                    flash(str(exc), "error")

        return render_template(
            "plants/cultivar_import.html",
            result=result,
        )


    # ------------------------------------------------------------------
    # Durchgänge
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/durchgaenge")
    def batch_list():
        return render_template(
            "plants/batches.html",
            batches=list_batches(include_archived=True),
        )


    @app.route(
        "/pflanzenmanagement/durchgaenge/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def batch_new():
        if request.method == "POST":
            try:
                batch_id = save_batch(_form_data())
                _audit("plants.batch_created", "batch", batch_id)
                flash("Durchgang wurde angelegt.", "success")
                return redirect(
                    url_for("batch_edit", batch_id=batch_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/batch_form.html",
            batch=None,
            batch_statuses=BATCH_STATUSES,
        )


    @app.route(
        "/pflanzenmanagement/durchgaenge/<int:batch_id>",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def batch_edit(batch_id):
        batch = get_batch(batch_id)
        if not batch:
            abort(404)

        if request.method == "POST":
            try:
                save_batch(_form_data(), batch_id)
                _audit("plants.batch_updated", "batch", batch_id)
                flash("Durchgang wurde gespeichert.", "success")
                return redirect(
                    url_for("batch_edit", batch_id=batch_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/batch_form.html",
            batch=get_batch(batch_id),
            batch_statuses=BATCH_STATUSES,
        )


    # ------------------------------------------------------------------
    # Pflanzen / WIP
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/pflanzen")
    def plant_list():
        filters = {
            "status": request.args.get("status") or None,
            "stage": request.args.get("stage") or None,
            "cultivar_id": request.args.get("cultivar_id") or None,
            "batch_id": request.args.get("batch_id") or None,
            "search": request.args.get("q") or None,
        }
        plants = list_plants(**filters)

        return render_template(
            "plants/plants.html",
            plants=plants,
            filters=filters,
            stages=STAGES,
            statuses=PLANT_STATUSES,
            cultivars=list_cultivars(include_inactive=False),
            batches=list_batches(include_archived=False),
        )


    @app.route(
        "/pflanzenmanagement/pflanzen/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def plant_new():
        if request.method == "POST":
            try:
                user = getattr(g, "current_user", None)
                plant_id = save_plant(
                    _form_data(),
                    created_by=user["id"] if user else None,
                )
                _audit("plants.plant_created", "plant", plant_id)
                flash("Pflanze wurde angelegt.", "success")
                return redirect(
                    url_for("plant_detail", plant_id=plant_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/plant_form.html",
            plant=None,
            stages=STAGES,
            statuses=PLANT_STATUSES,
            cultivars=list_cultivars(include_inactive=False),
            batches=list_batches(include_archived=False),
        )


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/bearbeiten",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def plant_edit(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        if request.method == "POST":
            try:
                user = getattr(g, "current_user", None)
                save_plant(
                    _form_data(),
                    plant_id,
                    created_by=user["id"] if user else None,
                )
                _audit("plants.plant_updated", "plant", plant_id)
                flash("Pflanze wurde gespeichert.", "success")
                return redirect(
                    url_for("plant_detail", plant_id=plant_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/plant_form.html",
            plant=get_plant(plant_id),
            stages=STAGES,
            statuses=PLANT_STATUSES,
            cultivars=list_cultivars(include_inactive=True),
            batches=list_batches(include_archived=True),
        )


    @app.route("/pflanzenmanagement/pflanzen/<int:plant_id>")
    def plant_detail(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        return render_template(
            "plants/plant_detail.html",
            plant=plant,
            events=get_stage_events(plant_id),
            stages=STAGES,
            stage_labels=STAGE_LABELS,
            stage_colors=STAGE_COLORS,
        )


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/phase",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def plant_stage_change(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        stage = request.form.get("stage", "").strip()
        allowed = {item[0] for item in STAGES}
        if stage not in allowed:
            flash("Ungültige Phase.", "error")
            return redirect(url_for("plant_detail", plant_id=plant_id))

        user = getattr(g, "current_user", None)
        changed = set_plant_stage(
            plant_id,
            stage,
            started_on=request.form.get("started_on"),
            note=request.form.get("note"),
            created_by=user["id"] if user else None,
        )

        if changed:
            _audit(
                "plants.stage_changed",
                "plant",
                plant_id,
                {"stage": stage},
            )
            flash("Phase wurde aktualisiert.", "success")
        else:
            flash("Die Pflanze befindet sich bereits in dieser Phase.", "info")

        return redirect(url_for("plant_detail", plant_id=plant_id))


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/status",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def plant_status_change(plant_id):
        status = request.form.get("status", "").strip()
        allowed = {item[0] for item in PLANT_STATUSES}
        if status not in allowed:
            flash("Ungültiger Status.", "error")
            return redirect(url_for("plant_detail", plant_id=plant_id))

        set_plant_status(plant_id, status)
        _audit(
            "plants.status_changed",
            "plant",
            plant_id,
            {"status": status},
        )
        flash("Status wurde aktualisiert.", "success")
        return redirect(url_for("plant_detail", plant_id=plant_id))


    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/timeline")
    def plant_timeline():
        return render_template(
            "plants/timeline.html",
            timeline=get_timeline(active_only=True),
            stages=STAGES,
        )


    # ------------------------------------------------------------------
    # Alte Links bleiben kompatibel
    # ------------------------------------------------------------------

    @app.route("/pflanzendaten")
    def pflanzendaten_page():
        return redirect(url_for("plant_list"))


    @app.route("/tagebuch")
    def tagebuch_page():
        return render_template("tagebuch.html")
