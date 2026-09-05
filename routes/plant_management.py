import os

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
    PLANT_ROLES,
    PLANT_ROLE_LABELS,
    GENETIC_LINE_STATUSES,
    SEED_LOT_STATUSES,
    SEED_TYPES,
    SEED_ORIGIN_TYPES,
    SEED_MOVEMENT_TYPES,
    PROPAGATION_METHODS,
    PROPAGATION_UNIT_STATUS_LABELS,
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
from plant_management.grow_guides import build_vpd_guide


from plant_management.propagation import (
    list_genetic_lines,
    get_genetic_line,
    save_genetic_line,
    genetic_line_plants,
    set_plant_role,
    get_role_events,
    list_mother_plants,
    get_mother_summary,
    list_seed_lots,
    get_seed_lot,
    save_seed_lot,
    list_seed_movements,
    book_seed_movement,
    create_propagation_run,
    list_propagation_runs,
    get_propagation_run,
    update_propagation_unit,
    create_plant_from_propagation_unit,
    get_plant_origin,
    propagation_dashboard,
)
from plant_management.propagation_excel import (
    export_seed_lots_xlsx,
    seed_import_template_xlsx,
    import_seed_lots_xlsx,
)

from plant_management.journal import (
    JOURNAL_CATEGORIES,
    JOURNAL_SEVERITIES,
    MEASUREMENT_FIELDS,
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_PER_REQUEST,
    list_journal_entries,
    get_journal_entry,
    save_journal_entry,
    measurements_from_form,
    resolve_follow_up,
    cancel_journal_entry,
    get_revisions,
    journal_stats,
    save_attachments,
    get_attachment,
    remove_attachment,
    export_journal_xlsx,
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


def _current_user_identity():
    user = getattr(g, "current_user", None)
    if not user:
        return None, None

    name = (
        user.get("display_name")
        or user.get("username")
        or user.get("email")
        or f"Benutzer {user.get('id')}"
    )
    return user.get("id"), name


def _system_journal(
    title,
    *,
    body=None,
    category="care",
    severity="info",
    plant_ids=None,
    batch_ids=None,
    tags=None,
):
    """
    Automatische Betriebsdokumentation.
    Ein Fehler im Journal darf den fachlichen Vorgang nicht zurückrollen.
    """
    try:
        user_id, user_name = _current_user_identity()
        save_journal_entry(
            {
                "category": category,
                "severity": severity,
                "title": title,
                "body": body,
                "tags": tags,
            },
            plant_ids=plant_ids or [],
            batch_ids=batch_ids or [],
            user_id=user_id,
            user_name=user_name,
            source="system",
        )
    except Exception:
        pass


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
            journal_stats=journal_stats(),
            recent_journal=list_journal_entries(limit=6),
            propagation_stats=propagation_dashboard(),
        )


    @app.route("/pflanzenmanagement/anbauhilfe")
    def cultivation_guide():
        return render_template(
            "plants/cultivation_guide.html",
            guide=build_vpd_guide(list_plants(status="active")),
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


    @app.route("/pflanzenmanagement/durchgaenge/<int:batch_id>")
    def batch_detail(batch_id):
        batch = get_batch(batch_id)
        if not batch:
            abort(404)

        return render_template(
            "plants/batch_detail.html",
            batch=batch,
            plants=list_plants(batch_id=batch_id),
            journal_entries=list_journal_entries(batch_id=batch_id, limit=8),
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
                    url_for("batch_detail", batch_id=batch_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/batch_form.html",
            batch=None,
            batch_statuses=BATCH_STATUSES,
        )


    @app.route(
        "/pflanzenmanagement/durchgaenge/<int:batch_id>/bearbeiten",
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
                    url_for("batch_detail", batch_id=batch_id)
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
            journal_entries=list_journal_entries(
                plant_id=plant_id,
                limit=8,
            ),
            plant_origin=get_plant_origin(plant_id),
            role_events=get_role_events(plant_id),
            genetic_line=(
                get_genetic_line(plant.get("genetic_line_id"))
                if plant.get("genetic_line_id")
                else None
            ),
            mother_summary=(
                get_mother_summary(plant_id)
                if plant.get("current_role") in {"mother", "donor"}
                else None
            ),
            plant_roles=PLANT_ROLES,
            genetic_lines=list_genetic_lines(include_inactive=False),
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


    # ------------------------------------------------------------------
    # Betriebsjournal / Electronic Batch Record
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/tagebuch")
    def plant_journal():
        filters = {
            "search": request.args.get("q") or None,
            "category": request.args.get("category") or None,
            "severity": request.args.get("severity") or None,
            "plant_id": request.args.get("plant_id") or None,
            "batch_id": request.args.get("batch_id") or None,
            "date_from": request.args.get("date_from") or None,
            "date_to": request.args.get("date_to") or None,
            "open_follow_up": request.args.get("open") == "1",
        }

        return render_template(
            "plants/journal.html",
            entries=list_journal_entries(**filters),
            filters=filters,
            stats=journal_stats(),
            categories=JOURNAL_CATEGORIES,
            severities=JOURNAL_SEVERITIES,
            plants=list_plants(status="active"),
            batches=list_batches(include_archived=False),
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/neu",
        methods=["GET", "POST"],
    )
    @permission_required("diary.edit")
    def plant_journal_new():
        if request.method == "POST":
            try:
                user_id, user_name = _current_user_identity()

                entry_id = save_journal_entry(
                    _form_data(),
                    plant_ids=request.form.getlist("plant_ids"),
                    batch_ids=request.form.getlist("batch_ids"),
                    measurements=measurements_from_form(request.form),
                    user_id=user_id,
                    user_name=user_name,
                )

                save_attachments(
                    entry_id,
                    request.files.getlist("attachments"),
                    user_id=user_id,
                    user_name=user_name,
                )

                _audit(
                    "diary.entry_created",
                    "journal_entry",
                    entry_id,
                )

                flash("Journal-Eintrag wurde angelegt.", "success")
                return redirect(
                    url_for("plant_journal_detail", entry_id=entry_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/journal_form.html",
            entry=None,
            categories=JOURNAL_CATEGORIES,
            severities=JOURNAL_SEVERITIES,
            measurement_fields=MEASUREMENT_FIELDS,
            plants=list_plants(status="active"),
            batches=list_batches(include_archived=False),
            preselected_plant_id=request.args.get("plant_id"),
            preselected_batch_id=request.args.get("batch_id"),
            max_attachment_mb=MAX_ATTACHMENT_BYTES // 1024 // 1024,
            max_attachments=MAX_ATTACHMENTS_PER_REQUEST,
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/<int:entry_id>",
    )
    def plant_journal_detail(entry_id):
        entry = get_journal_entry(entry_id)
        if not entry:
            abort(404)

        return render_template(
            "plants/journal_detail.html",
            entry=entry,
            revisions=get_revisions(entry_id),
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/<int:entry_id>/bearbeiten",
        methods=["GET", "POST"],
    )
    @permission_required("diary.edit")
    def plant_journal_edit(entry_id):
        entry = get_journal_entry(entry_id)
        if not entry:
            abort(404)

        if entry["is_cancelled"]:
            flash(
                "Ein stornierter Journal-Eintrag kann nicht mehr bearbeitet werden.",
                "error",
            )
            return redirect(
                url_for("plant_journal_detail", entry_id=entry_id)
            )

        if request.method == "POST":
            try:
                user_id, user_name = _current_user_identity()

                save_journal_entry(
                    _form_data(),
                    entry_id=entry_id,
                    plant_ids=request.form.getlist("plant_ids"),
                    batch_ids=request.form.getlist("batch_ids"),
                    measurements=measurements_from_form(request.form),
                    user_id=user_id,
                    user_name=user_name,
                )

                save_attachments(
                    entry_id,
                    request.files.getlist("attachments"),
                    user_id=user_id,
                    user_name=user_name,
                )

                _audit(
                    "diary.entry_updated",
                    "journal_entry",
                    entry_id,
                )

                flash(
                    "Journal-Eintrag wurde gespeichert. "
                    "Die vorherige Version wurde revisionssicher archiviert.",
                    "success",
                )
                return redirect(
                    url_for("plant_journal_detail", entry_id=entry_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/journal_form.html",
            entry=get_journal_entry(entry_id),
            categories=JOURNAL_CATEGORIES,
            severities=JOURNAL_SEVERITIES,
            measurement_fields=MEASUREMENT_FIELDS,
            plants=list_plants(),
            batches=list_batches(include_archived=True),
            preselected_plant_id=None,
            preselected_batch_id=None,
            max_attachment_mb=MAX_ATTACHMENT_BYTES // 1024 // 1024,
            max_attachments=MAX_ATTACHMENTS_PER_REQUEST,
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/<int:entry_id>/erledigen",
        methods=["POST"],
    )
    @permission_required("diary.edit")
    def plant_journal_resolve(entry_id):
        user_id, user_name = _current_user_identity()

        try:
            changed = resolve_follow_up(
                entry_id,
                user_id=user_id,
                user_name=user_name,
            )
            if changed:
                _audit(
                    "diary.follow_up_resolved",
                    "journal_entry",
                    entry_id,
                )
                flash("Folgeaktion wurde als erledigt markiert.", "success")
            else:
                flash("Folgeaktion war bereits erledigt.", "info")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(
            url_for("plant_journal_detail", entry_id=entry_id)
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/<int:entry_id>/stornieren",
        methods=["POST"],
    )
    @permission_required("diary.edit")
    def plant_journal_cancel(entry_id):
        user_id, user_name = _current_user_identity()

        try:
            changed = cancel_journal_entry(
                entry_id,
                reason=request.form.get("reason"),
                user_id=user_id,
                user_name=user_name,
            )

            if changed:
                _audit(
                    "diary.entry_cancelled",
                    "journal_entry",
                    entry_id,
                    {"reason": request.form.get("reason")},
                )
                flash(
                    "Eintrag wurde storniert und bleibt aus "
                    "Nachvollziehbarkeitsgründen erhalten.",
                    "success",
                )
            else:
                flash("Eintrag war bereits storniert.", "info")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(
            url_for("plant_journal_detail", entry_id=entry_id)
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/anhaenge/<int:attachment_id>",
    )
    def plant_journal_attachment(attachment_id):
        attachment = get_attachment(attachment_id)
        if not attachment:
            abort(404)

        file_path = attachment["path"]
        if not os.path.isfile(file_path):
            abort(404)

        return send_file(
            file_path,
            mimetype=attachment["mime_type"],
            as_attachment=request.args.get("download") == "1",
            download_name=attachment["original_name"],
        )


    @app.route(
        "/pflanzenmanagement/tagebuch/anhaenge/<int:attachment_id>/entfernen",
        methods=["POST"],
    )
    @permission_required("diary.edit")
    def plant_journal_attachment_remove(attachment_id):
        attachment = get_attachment(attachment_id)
        if not attachment:
            abort(404)

        user_id, user_name = _current_user_identity()

        if remove_attachment(
            attachment_id,
            user_id=user_id,
            user_name=user_name,
        ):
            _audit(
                "diary.attachment_removed",
                "journal_attachment",
                attachment_id,
            )
            flash(
                "Anhang wurde aus der aktiven Ansicht entfernt. "
                "Der Audit-Trail bleibt erhalten.",
                "success",
            )

        return redirect(
            url_for(
                "plant_journal_detail",
                entry_id=attachment["entry_id"],
            )
        )


    @app.route("/pflanzenmanagement/tagebuch/export.xlsx")
    def plant_journal_export():
        filters = {
            "search": request.args.get("q") or None,
            "category": request.args.get("category") or None,
            "severity": request.args.get("severity") or None,
            "plant_id": request.args.get("plant_id") or None,
            "batch_id": request.args.get("batch_id") or None,
            "date_from": request.args.get("date_from") or None,
            "date_to": request.args.get("date_to") or None,
            "open_follow_up": request.args.get("open") == "1",
            "limit": 5000,
        }

        stream = export_journal_xlsx(
            list_journal_entries(**filters)
        )

        _audit(
            "diary.journal_exported",
            "journal_entry",
        )

        return send_file(
            stream,
            as_attachment=True,
            download_name="growstar_betriebsjournal.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )



    # ------------------------------------------------------------------
    # Phase 7 – Genetik / Mutterpflanzen
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/genetik")
    def genetics_dashboard():
        return render_template(
            "plants/genetics.html",
            genetic_lines=list_genetic_lines(),
            mothers=list_mother_plants(active_only=True),
        )


    @app.route(
        "/pflanzenmanagement/genetik/linien/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def genetic_line_new():
        source_plant_id = request.args.get("source_plant_id")
        source_plant = (
            get_plant(source_plant_id)
            if source_plant_id
            else None
        )

        if request.method == "POST":
            try:
                line_id = save_genetic_line(_form_data())
                _audit(
                    "plants.genetic_line_created",
                    "genetic_line",
                    line_id,
                )
                flash("Genetische Linie wurde angelegt.", "success")
                return redirect(
                    url_for(
                        "genetic_line_detail",
                        line_id=line_id,
                    )
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/genetic_line_form.html",
            line=None,
            cultivars=list_cultivars(include_inactive=False),
            plants=list_plants(),
            source_plant=source_plant,
            statuses=GENETIC_LINE_STATUSES,
        )


    @app.route(
        "/pflanzenmanagement/genetik/linien/<int:line_id>",
    )
    def genetic_line_detail(line_id):
        line = get_genetic_line(line_id)
        if not line:
            abort(404)

        return render_template(
            "plants/genetic_line_detail.html",
            line=line,
            plants=genetic_line_plants(line_id),
            mothers=[
                p
                for p in list_mother_plants(active_only=False)
                if p.get("genetic_line_id") == line_id
            ],
        )


    @app.route(
        "/pflanzenmanagement/genetik/linien/<int:line_id>/bearbeiten",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def genetic_line_edit(line_id):
        line = get_genetic_line(line_id)
        if not line:
            abort(404)

        if request.method == "POST":
            try:
                save_genetic_line(_form_data(), line_id)
                _audit(
                    "plants.genetic_line_updated",
                    "genetic_line",
                    line_id,
                )
                flash("Genetische Linie wurde gespeichert.", "success")
                return redirect(
                    url_for(
                        "genetic_line_detail",
                        line_id=line_id,
                    )
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/genetic_line_form.html",
            line=get_genetic_line(line_id),
            cultivars=list_cultivars(include_inactive=True),
            plants=list_plants(),
            source_plant=None,
            statuses=GENETIC_LINE_STATUSES,
        )


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/rolle",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def plant_role_change(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        role = request.form.get("role", "").strip()
        user_id, user_name = _current_user_identity()

        try:
            changed = set_plant_role(
                plant_id,
                role,
                started_on=request.form.get("started_on"),
                genetic_line_id=request.form.get("genetic_line_id"),
                note=request.form.get("note"),
                user_id=user_id,
                user_name=user_name,
            )

            if changed:
                _audit(
                    "plants.role_changed",
                    "plant",
                    plant_id,
                    {"role": role},
                )
                _system_journal(
                    f"Pflanzenrolle geändert: {PLANT_ROLE_LABELS.get(role, role)}",
                    body=request.form.get("note"),
                    plant_ids=[plant_id],
                    tags="rolle,lifecycle",
                )
                flash("Pflanzenrolle wurde aktualisiert.", "success")
            else:
                flash("Die Rolle war bereits gesetzt.", "info")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("plant_detail", plant_id=plant_id))


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/mutter-in-bluete",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def mother_release_to_flower(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        if plant.get("current_role") not in {"mother", "donor"}:
            flash("Diese Pflanze ist keine aktive Mutter-/Spenderpflanze.", "error")
            return redirect(url_for("plant_detail", plant_id=plant_id))

        started_on = request.form.get("started_on")
        note = request.form.get("note") or (
            "Mutterfunktion beendet; Pflanze in den normalen Produktions-Lifecycle überführt."
        )
        user_id, user_name = _current_user_identity()

        try:
            set_plant_role(
                plant_id,
                "production",
                started_on=started_on,
                note=note,
                user_id=user_id,
                user_name=user_name,
            )
            set_plant_stage(
                plant_id,
                "flowering",
                started_on=started_on,
                note=note,
                created_by=user_id,
            )

            _audit(
                "plants.mother_released_to_flower",
                "plant",
                plant_id,
            )
            _system_journal(
                "Mutterpflanze in Produktions-Lifecycle überführt",
                body=note,
                category="care",
                plant_ids=[plant_id],
                tags="mutter,lifecycle",
            )
            flash(
                "Die Mutterpflanze wurde aus der Mutterrolle gelöst und "
                "in die Blütephase überführt. Abstammung und Historie bleiben erhalten.",
                "success",
            )
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("plant_detail", plant_id=plant_id))


    @app.route(
        "/pflanzenmanagement/pflanzen/<int:plant_id>/lebenszyklus-beenden",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def plant_end_lifecycle(plant_id):
        plant = get_plant(plant_id)
        if not plant:
            abort(404)

        ended_on = request.form.get("ended_on")
        reason = request.form.get("reason") or "Lebenszyklus regulär beendet"
        user_id, user_name = _current_user_identity()

        try:
            set_plant_role(
                plant_id,
                "retired",
                started_on=ended_on,
                note=reason,
                user_id=user_id,
                user_name=user_name,
            )
            set_plant_stage(
                plant_id,
                "finished",
                started_on=ended_on,
                note=reason,
                created_by=user_id,
            )

            _audit(
                "plants.lifecycle_finished",
                "plant",
                plant_id,
                {"reason": reason},
            )
            _system_journal(
                "Pflanzen-Lebenszyklus beendet",
                body=reason,
                category="care",
                plant_ids=[plant_id],
                tags="lifecycle,abschluss",
            )
            flash(
                "Der Lebenszyklus wurde beendet. Die Pflanze bleibt vollständig "
                "in Historie, Genetik und Abstammung nachvollziehbar.",
                "success",
            )
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("plant_detail", plant_id=plant_id))


    # ------------------------------------------------------------------
    # Phase 7 – Vermehrung / Saatgut
    # ------------------------------------------------------------------

    @app.route("/pflanzenmanagement/vermehrung")
    def propagation_dashboard_page():
        return render_template(
            "plants/propagation_dashboard.html",
            stats=propagation_dashboard(),
            recent_runs=list_propagation_runs(limit=8),
            seed_lots=list_seed_lots(
                include_empty=False,
                include_archived=False,
            )[:8],
            mothers=list_mother_plants(active_only=True),
        )


    @app.route("/pflanzenmanagement/vermehrung/saatgut")
    def seed_lot_list():
        return render_template(
            "plants/seed_lots.html",
            lots=list_seed_lots(
                include_empty=True,
                include_archived=True,
                search=request.args.get("q"),
            ),
            query=request.args.get("q", ""),
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/saatgut/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def seed_lot_new():
        if request.method == "POST":
            try:
                user_id, user_name = _current_user_identity()
                lot_id = save_seed_lot(
                    _form_data(),
                    initial_quantity=request.form.get("initial_quantity"),
                    user_id=user_id,
                    user_name=user_name,
                )
                lot = get_seed_lot(lot_id)

                _audit(
                    "plants.seed_lot_created",
                    "seed_lot",
                    lot_id,
                )
                _system_journal(
                    f"Saatgut-Lot angelegt: {lot['code']}",
                    body=(
                        f"{lot['cultivar_name']} · Anfangsbestand "
                        f"{lot['stock']} · Lagerort "
                        f"{lot.get('storage_location') or '—'}"
                    ),
                    category="note",
                    tags="saatgut,lager",
                )
                flash("Saatgut-Lot wurde angelegt.", "success")
                return redirect(
                    url_for("seed_lot_detail", lot_id=lot_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/seed_lot_form.html",
            lot=None,
            cultivars=list_cultivars(include_inactive=False),
            statuses=SEED_LOT_STATUSES,
            seed_types=SEED_TYPES,
            origin_types=SEED_ORIGIN_TYPES,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/saatgut/<int:lot_id>",
    )
    def seed_lot_detail(lot_id):
        lot = get_seed_lot(lot_id)
        if not lot:
            abort(404)

        return render_template(
            "plants/seed_lot_detail.html",
            lot=lot,
            movements=list_seed_movements(lot_id),
            movement_types=SEED_MOVEMENT_TYPES,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/saatgut/<int:lot_id>/bearbeiten",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def seed_lot_edit(lot_id):
        lot = get_seed_lot(lot_id)
        if not lot:
            abort(404)

        if request.method == "POST":
            try:
                save_seed_lot(_form_data(), lot_id)
                _audit(
                    "plants.seed_lot_updated",
                    "seed_lot",
                    lot_id,
                )
                flash("Saatgut-Lot wurde gespeichert.", "success")
                return redirect(
                    url_for("seed_lot_detail", lot_id=lot_id)
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/seed_lot_form.html",
            lot=get_seed_lot(lot_id),
            cultivars=list_cultivars(include_inactive=True),
            statuses=SEED_LOT_STATUSES,
            seed_types=SEED_TYPES,
            origin_types=SEED_ORIGIN_TYPES,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/saatgut/<int:lot_id>/bewegung",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def seed_lot_movement(lot_id):
        lot = get_seed_lot(lot_id)
        if not lot:
            abort(404)

        user_id, user_name = _current_user_identity()

        try:
            quantity = int(request.form.get("quantity", "0"))
            new_stock = book_seed_movement(
                lot_id,
                quantity,
                request.form.get("movement_type") or "adjustment",
                occurred_on=request.form.get("occurred_on"),
                note=request.form.get("note"),
                user_id=user_id,
                user_name=user_name,
            )

            _audit(
                "plants.seed_movement",
                "seed_lot",
                lot_id,
                {
                    "quantity": quantity,
                    "new_stock": new_stock,
                },
            )
            _system_journal(
                f"Saatgutbestand gebucht: {lot['code']} {quantity:+d}",
                body=f"Neuer Bestand: {new_stock}. {request.form.get('note') or ''}",
                category="note",
                tags="saatgut,lager,buchung",
            )
            flash(f"Bestand gebucht. Neuer Bestand: {new_stock}.", "success")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(url_for("seed_lot_detail", lot_id=lot_id))


    @app.route("/pflanzenmanagement/vermehrung/saatgut/export.xlsx")
    def seed_lot_export():
        _audit("plants.seed_exported", "seed_lot")
        return send_file(
            export_seed_lots_xlsx(),
            as_attachment=True,
            download_name="growstar_saatgut.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


    @app.route("/pflanzenmanagement/vermehrung/saatgut/vorlage.xlsx")
    def seed_lot_template():
        return send_file(
            seed_import_template_xlsx(),
            as_attachment=True,
            download_name="growstar_saatgut_importvorlage.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/saatgut/import",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def seed_lot_import():
        result = None

        if request.method == "POST":
            upload = request.files.get("file")

            if not upload or not upload.filename:
                flash("Bitte eine Excel-Datei auswählen.", "error")
            elif not upload.filename.lower().endswith(".xlsx"):
                flash("Es werden nur .xlsx-Dateien unterstützt.", "error")
            else:
                try:
                    user_id, user_name = _current_user_identity()
                    result = import_seed_lots_xlsx(
                        upload.stream,
                        user_id=user_id,
                        user_name=user_name,
                    )
                    _audit(
                        "plants.seed_imported",
                        "seed_lot",
                        details=result,
                    )
                    flash(
                        f"Import abgeschlossen: {result['created']} neu, "
                        f"{result['updated']} aktualisiert, "
                        f"{result['booked']} Bestandsbuchungen, "
                        f"{result['skipped']} übersprungen.",
                        "success",
                    )
                except Exception as exc:
                    flash(str(exc), "error")

        return render_template(
            "plants/seed_import.html",
            result=result,
        )


    @app.route("/pflanzenmanagement/vermehrung/ansaetze")
    def propagation_run_list():
        return render_template(
            "plants/propagation_runs.html",
            runs=list_propagation_runs(
                method=request.args.get("method") or None,
                status=request.args.get("status") or None,
            ),
            method_filter=request.args.get("method", ""),
            status_filter=request.args.get("status", ""),
            methods=PROPAGATION_METHODS,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/ansaetze/neu",
        methods=["GET", "POST"],
    )
    @permission_required("plants.edit")
    def propagation_run_new():
        if request.method == "POST":
            try:
                user_id, user_name = _current_user_identity()
                run_id = create_propagation_run(
                    _form_data(),
                    user_id=user_id,
                    user_name=user_name,
                )
                run = get_propagation_run(run_id)

                _audit(
                    "plants.propagation_started",
                    "propagation_run",
                    run_id,
                    {
                        "method": run["method"],
                        "target_count": run["target_count"],
                    },
                )
                _system_journal(
                    f"Vermehrungsansatz gestartet: {run['code']}",
                    body=(
                        f"{run['method_label']} · {run['target_count']} Einheiten · "
                        f"{run['cultivar_name']}"
                    ),
                    category="care",
                    plant_ids=(
                        [run["mother_plant_id"]]
                        if run.get("mother_plant_id")
                        else []
                    ),
                    batch_ids=(
                        [run["batch_id"]]
                        if run.get("batch_id")
                        else []
                    ),
                    tags="vermehrung",
                )

                flash("Vermehrungsansatz wurde gestartet.", "success")
                return redirect(
                    url_for(
                        "propagation_run_detail",
                        run_id=run_id,
                    )
                )
            except Exception as exc:
                flash(str(exc), "error")

        return render_template(
            "plants/propagation_run_form.html",
            seed_lots=list_seed_lots(
                include_empty=False,
                include_archived=False,
            ),
            mothers=list_mother_plants(active_only=True),
            batches=list_batches(include_archived=False),
            methods=PROPAGATION_METHODS,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/ansaetze/<int:run_id>",
    )
    def propagation_run_detail(run_id):
        run = get_propagation_run(run_id)
        if not run:
            abort(404)

        return render_template(
            "plants/propagation_run_detail.html",
            run=run,
            unit_status_labels=PROPAGATION_UNIT_STATUS_LABELS,
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/einheiten/<int:unit_id>/status",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def propagation_unit_status(unit_id):
        run_id = request.form.get("run_id")

        try:
            update_propagation_unit(
                unit_id,
                status=request.form.get("status"),
                outcome_on=request.form.get("outcome_on"),
                notes=request.form.get("notes"),
            )
            _audit(
                "plants.propagation_unit_updated",
                "propagation_unit",
                unit_id,
                {"status": request.form.get("status")},
            )
            flash("Status wurde aktualisiert.", "success")
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(
            url_for(
                "propagation_run_detail",
                run_id=run_id,
            )
        )


    @app.route(
        "/pflanzenmanagement/vermehrung/einheiten/<int:unit_id>/pflanze-erzeugen",
        methods=["POST"],
    )
    @permission_required("plants.edit")
    def propagation_unit_create_plant(unit_id):
        run_id = request.form.get("run_id")
        user_id, user_name = _current_user_identity()

        try:
            plant_id = create_plant_from_propagation_unit(
                unit_id,
                display_name=request.form.get("display_name"),
                location=request.form.get("location"),
                user_id=user_id,
                user_name=user_name,
            )
            plant = get_plant(plant_id)

            _audit(
                "plants.created_from_propagation",
                "plant",
                plant_id,
                {"propagation_unit_id": unit_id},
            )
            _system_journal(
                f"Pflanze aus Vermehrung erzeugt: {plant['code']}",
                body=plant["display_name"],
                category="care",
                plant_ids=[plant_id],
                tags="vermehrung,pflanze",
            )

            flash(
                "Pflanze wurde erzeugt und ihre Herkunft vollständig verknüpft.",
                "success",
            )
            return redirect(
                url_for("plant_detail", plant_id=plant_id)
            )
        except Exception as exc:
            flash(str(exc), "error")

        return redirect(
            url_for(
                "propagation_run_detail",
                run_id=run_id,
            )
        )


    # Alter Link bleibt kompatibel.
    @app.route("/tagebuch")
    def tagebuch_page():
        return redirect(url_for("plant_journal"))
