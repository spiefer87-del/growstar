import json
import sqlite3
from datetime import datetime

from flask import (
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth.csrf import validate_csrf_token
from auth.database import (
    ADMIN_ROLE_NAME,
    count_active_administrators,
    create_role,
    create_user,
    get_admin_stats,
    get_role_by_id,
    get_role_permission_ids,
    get_user_by_id,
    get_user_role_ids,
    get_user_roles,
    is_user_administrator,
    list_audit_entries,
    list_permissions,
    list_roles,
    list_users,
    set_role_permissions,
    set_user_active,
    set_user_password_hash,
    set_user_roles,
    update_role,
    update_user,
    write_audit,
)
from auth.decorators import any_permission_required, permission_required
from auth.service import hash_password


def _require_csrf():
    if not validate_csrf_token(request.form.get("csrf_token")):
        abort(400, "Ungültiges CSRF-Token")


def _parse_ids(values):
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            abort(400, "Ungültige ID")
    return sorted(set(result))


def _admin_role_id(roles):
    for role in roles:
        if role["name"].casefold() == ADMIN_ROLE_NAME.casefold():
            return role["id"]
    return None


def _permission_groups(permissions):
    groups = {}
    for permission in permissions:
        prefix = permission["name"].split(".", 1)[0]
        groups.setdefault(prefix, []).append(permission)
    return groups


def _format_timestamp(value):
    if not value:
        return "–"
    return datetime.fromtimestamp(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")


def register(app):
    @app.get("/admin", endpoint="admin_index")
    @any_permission_required(
        "users.view",
        "users.manage",
        "roles.view",
        "roles.manage",
        "audit.view",
    )
    def admin_index():
        return render_template(
            "admin/index.html",
            stats=get_admin_stats(),
        )

    @app.get("/admin/users", endpoint="admin_users")
    @any_permission_required("users.view", "users.manage")
    def users_page():
        users = list_users()
        for user in users:
            user["created_at_display"] = _format_timestamp(user.get("created_at"))
            user["last_login_display"] = _format_timestamp(user.get("last_login_at"))
        return render_template("admin/users.html", users=users)

    @app.route(
        "/admin/users/new",
        methods=["GET", "POST"],
        endpoint="admin_user_new",
    )
    @permission_required("users.manage")
    def user_new():
        roles = list_roles()
        selected_role_ids = []

        if request.method == "POST":
            _require_csrf()

            username = request.form.get("username", "").strip()
            display_name = request.form.get("display_name", "").strip()
            email = request.form.get("email", "").strip() or None
            password = request.form.get("password", "")
            password_repeat = request.form.get("password_repeat", "")
            is_active = request.form.get("is_active") == "1"
            selected_role_ids = _parse_ids(request.form.getlist("roles"))

            if password != password_repeat:
                flash("Die Passwörter stimmen nicht überein.", "error")
            elif is_active and not selected_role_ids:
                flash("Ein aktiver Benutzer benötigt mindestens eine Rolle.", "error")
            else:
                try:
                    password_hash = hash_password(password)
                    user_id = create_user(
                        username=username,
                        display_name=display_name,
                        email=email,
                        password_hash=password_hash,
                        is_active=is_active,
                    )
                    set_user_roles(user_id, selected_role_ids)

                    write_audit(
                        action="user.create",
                        user_id=g.current_user["id"],
                        entity_type="user",
                        entity_id=user_id,
                        details={
                            "username": username,
                            "display_name": display_name,
                            "email": email,
                            "is_active": is_active,
                            "roles": get_user_roles(user_id),
                        },
                        ip_address=request.remote_addr,
                    )
                    flash(f"Benutzer '{username}' wurde angelegt.", "success")
                    return redirect(url_for("admin_user_edit", user_id=user_id))
                except ValueError as exc:
                    flash(str(exc), "error")
                except sqlite3.IntegrityError:
                    flash("Benutzername oder E-Mail-Adresse existiert bereits.", "error")

        return render_template(
            "admin/user_form.html",
            mode="new",
            user=None,
            roles=roles,
            selected_role_ids=set(selected_role_ids),
        )

    @app.route(
        "/admin/users/<int:user_id>",
        methods=["GET", "POST"],
        endpoint="admin_user_edit",
    )
    @permission_required("users.manage")
    def user_edit(user_id):
        user = get_user_by_id(user_id)
        if not user:
            abort(404)

        roles = list_roles()
        admin_role_id = _admin_role_id(roles)
        selected_role_ids = set(get_user_role_ids(user_id))

        if request.method == "POST":
            _require_csrf()

            username = request.form.get("username", "").strip()
            display_name = request.form.get("display_name", "").strip()
            email = request.form.get("email", "").strip() or None
            is_active = request.form.get("is_active") == "1"
            new_role_ids = set(_parse_ids(request.form.getlist("roles")))

            current_is_admin = is_user_administrator(user_id)
            will_be_admin = admin_role_id in new_role_ids if admin_role_id else False

            if user_id == g.current_user["id"] and not is_active:
                flash("Du kannst deinen eigenen Benutzer nicht deaktivieren.", "error")
            elif (
                user_id == g.current_user["id"]
                and current_is_admin
                and not will_be_admin
            ):
                flash(
                    "Du kannst dir die Administratorrolle nicht selbst entziehen.",
                    "error",
                )
            elif (
                user["is_active"]
                and current_is_admin
                and (not is_active or not will_be_admin)
                and count_active_administrators() <= 1
            ):
                flash(
                    "Der letzte aktive Administrator kann nicht deaktiviert oder herabgestuft werden.",
                    "error",
                )
            elif is_active and not new_role_ids:
                flash("Ein aktiver Benutzer benötigt mindestens eine Rolle.", "error")
            else:
                before = {
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "email": user["email"],
                    "is_active": bool(user["is_active"]),
                    "roles": get_user_roles(user_id),
                }

                try:
                    update_user(
                        user_id=user_id,
                        username=username,
                        display_name=display_name,
                        email=email,
                    )
                    set_user_active(user_id, is_active)
                    set_user_roles(user_id, new_role_ids)

                    after = {
                        "username": username,
                        "display_name": display_name,
                        "email": email,
                        "is_active": is_active,
                        "roles": get_user_roles(user_id),
                    }
                    write_audit(
                        action="user.update",
                        user_id=g.current_user["id"],
                        entity_type="user",
                        entity_id=user_id,
                        details={"before": before, "after": after},
                        ip_address=request.remote_addr,
                    )
                    flash("Benutzer wurde gespeichert.", "success")
                    return redirect(url_for("admin_user_edit", user_id=user_id))
                except ValueError as exc:
                    flash(str(exc), "error")
                except sqlite3.IntegrityError:
                    flash("Benutzername oder E-Mail-Adresse existiert bereits.", "error")

            selected_role_ids = new_role_ids
            user = get_user_by_id(user_id)

        return render_template(
            "admin/user_form.html",
            mode="edit",
            user=user,
            roles=roles,
            selected_role_ids=set(selected_role_ids),
        )

    @app.post(
        "/admin/users/<int:user_id>/password",
        endpoint="admin_user_password",
    )
    @permission_required("users.manage")
    def user_password(user_id):
        _require_csrf()
        user = get_user_by_id(user_id)
        if not user:
            abort(404)

        password = request.form.get("password", "")
        password_repeat = request.form.get("password_repeat", "")
        if password != password_repeat:
            flash("Die Passwörter stimmen nicht überein.", "error")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        try:
            new_session_version = set_user_password_hash(
                user_id,
                hash_password(password),
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        # Wenn ein Administrator sein eigenes Passwort ändert, darf diese eine
        # aktuelle Sitzung bestehen bleiben. Alle anderen Sitzungen sind ungültig.
        if user_id == g.current_user["id"]:
            session["session_version"] = new_session_version

        write_audit(
            action="user.password_reset",
            user_id=g.current_user["id"],
            entity_type="user",
            entity_id=user_id,
            details={"username": user["username"]},
            ip_address=request.remote_addr,
        )
        flash("Passwort wurde geändert. Andere Sitzungen dieses Benutzers sind abgemeldet.", "success")
        return redirect(url_for("admin_user_edit", user_id=user_id))

    @app.get("/admin/roles", endpoint="admin_roles")
    @any_permission_required("roles.view", "roles.manage")
    def roles_page():
        return render_template("admin/roles.html", roles=list_roles())

    @app.route(
        "/admin/roles/new",
        methods=["GET", "POST"],
        endpoint="admin_role_new",
    )
    @permission_required("roles.manage")
    def role_new():
        permissions = list_permissions()
        selected_permission_ids = set()

        if request.method == "POST":
            _require_csrf()
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip() or None
            selected_permission_ids = set(
                _parse_ids(request.form.getlist("permissions"))
            )

            try:
                role_id = create_role(name, description)
                set_role_permissions(role_id, selected_permission_ids)
                role = get_role_by_id(role_id)

                write_audit(
                    action="role.create",
                    user_id=g.current_user["id"],
                    entity_type="role",
                    entity_id=role_id,
                    details={
                        "name": role["name"],
                        "permissions": [p["name"] for p in role["permissions"]],
                    },
                    ip_address=request.remote_addr,
                )
                flash(f"Rolle '{role['name']}' wurde angelegt.", "success")
                return redirect(url_for("admin_role_edit", role_id=role_id))
            except ValueError as exc:
                flash(str(exc), "error")
            except sqlite3.IntegrityError:
                flash("Eine Rolle mit diesem Namen existiert bereits.", "error")

        return render_template(
            "admin/role_form.html",
            mode="new",
            role=None,
            permission_groups=_permission_groups(permissions),
            selected_permission_ids=selected_permission_ids,
            administrator_role=False,
        )

    @app.route(
        "/admin/roles/<int:role_id>",
        methods=["GET", "POST"],
        endpoint="admin_role_edit",
    )
    @permission_required("roles.manage")
    def role_edit(role_id):
        role = get_role_by_id(role_id)
        if not role:
            abort(404)

        permissions = list_permissions()
        selected_permission_ids = set(get_role_permission_ids(role_id))
        administrator_role = role["name"].casefold() == ADMIN_ROLE_NAME.casefold()

        if request.method == "POST":
            _require_csrf()
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip() or None
            new_permission_ids = set(
                _parse_ids(request.form.getlist("permissions"))
            )

            before = {
                "name": role["name"],
                "description": role["description"],
                "permissions": [p["name"] for p in role["permissions"]],
            }

            try:
                update_role(role_id, name, description)
                set_role_permissions(role_id, new_permission_ids)
                updated = get_role_by_id(role_id)

                after = {
                    "name": updated["name"],
                    "description": updated["description"],
                    "permissions": [p["name"] for p in updated["permissions"]],
                }
                write_audit(
                    action="role.update",
                    user_id=g.current_user["id"],
                    entity_type="role",
                    entity_id=role_id,
                    details={"before": before, "after": after},
                    ip_address=request.remote_addr,
                )
                flash("Rolle wurde gespeichert.", "success")
                return redirect(url_for("admin_role_edit", role_id=role_id))
            except ValueError as exc:
                flash(str(exc), "error")
            except sqlite3.IntegrityError:
                flash("Eine Rolle mit diesem Namen existiert bereits.", "error")

            selected_permission_ids = new_permission_ids
            role = get_role_by_id(role_id)

        return render_template(
            "admin/role_form.html",
            mode="edit",
            role=role,
            permission_groups=_permission_groups(permissions),
            selected_permission_ids=selected_permission_ids,
            administrator_role=administrator_role,
        )

    @app.get("/admin/audit", endpoint="admin_audit")
    @permission_required("audit.view")
    def audit_page():
        search = request.args.get("q", "").strip()
        entries = list_audit_entries(limit=250, search=search or None)
        for entry in entries:
            entry["created_at_display"] = _format_timestamp(entry.get("created_at"))
            details = entry.get("details_data")
            if details is None:
                entry["details_pretty"] = ""
            elif isinstance(details, (dict, list)):
                entry["details_pretty"] = json.dumps(
                    details,
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                entry["details_pretty"] = str(details)

        return render_template(
            "admin/audit.html",
            entries=entries,
            search=search,
        )
