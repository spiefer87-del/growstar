from datetime import timedelta

from flask import (
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from markupsafe import escape

from .csrf import csrf_token, validate_request_csrf
from .database import PERMISSIONS, load_user, write_audit
from .policy import permission_requirement


PUBLIC_ENDPOINTS = {
    "auth_login",
    "static",
}


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _login_redirect():
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("auth_login", next=next_url))


def _authentication_required_response():
    if request.path.startswith("/api/"):
        return jsonify(
            success=False,
            error="authentication_required",
            message="Deine Sitzung ist abgelaufen oder du bist nicht angemeldet.",
        ), 401

    return _login_redirect()


def _csrf_failed_response():
    if request.path.startswith("/api/"):
        return jsonify(
            success=False,
            error="invalid_csrf",
            message=(
                "Die Sicherheitsprüfung ist fehlgeschlagen. "
                "Bitte lade die Seite neu und versuche es erneut."
            ),
        ), 400

    abort(400, "Ungültige oder fehlende CSRF-Prüfung")


def _permission_labels(requirement):
    if not requirement:
        return []

    return [
        PERMISSIONS.get(permission, permission)
        for permission in requirement.permissions
    ]


def _permission_message(requirement):
    labels = _permission_labels(requirement)

    if not labels:
        return "Du hast keine Berechtigung für diese Aktion."

    if len(labels) == 1:
        return f"Für diese Aktion wird die Berechtigung „{labels[0]}“ benötigt."

    joined = ", ".join(f"„{label}“" for label in labels)

    if requirement.mode == "all":
        return f"Für diese Aktion werden folgende Berechtigungen benötigt: {joined}."

    return f"Für diese Aktion wird eine der folgenden Berechtigungen benötigt: {joined}."


def _audit_denied(requirement):
    # Lesende Polling-Requests würden das Audit-Log unnötig fluten. Kritische
    # Schreibversuche werden dagegen protokolliert.
    if request.method in SAFE_METHODS:
        return

    user = getattr(g, "current_user", None)
    if not user:
        return

    try:
        write_audit(
            action="auth.permission_denied",
            user_id=user["id"],
            entity_type="route",
            entity_id=request.path,
            details={
                "method": request.method,
                "permissions": list(requirement.permissions),
                "mode": requirement.mode,
            },
            ip_address=request.remote_addr,
        )
    except Exception:
        # Ein Audit-Fehler darf die eigentliche Rechteprüfung nie abschalten.
        pass


def _audit_csrf_denied():
    user = getattr(g, "current_user", None)
    if not user:
        return

    try:
        write_audit(
            action="auth.csrf_denied",
            user_id=user["id"],
            entity_type="route",
            entity_id=request.path,
            details={
                "method": request.method,
                "origin": request.headers.get("Origin"),
            },
            ip_address=request.remote_addr,
        )
    except Exception:
        pass


def _inject_feedback_assets(response):
    """
    Übergangslösung für bestehende Growstar-Templates.

    Neue Seiten sollen templates/base.html verwenden. Bestehende ältere
    Templates bekommen das globale Feedback-Script hier automatisch in den
    <head> eingefügt. Dadurch müssen wir nicht sofort jede einzelne Growstar-
    Seite umbauen und trotzdem funktionieren Toasts/CSRF-Header überall.
    """

    if response.is_streamed or response.direct_passthrough:
        return response

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type.lower():
        return response

    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response

    if not html or "data-growstar-feedback" in html:
        return response

    head_end = html.lower().find("</head>")
    if head_end < 0:
        return response

    token = escape(csrf_token())
    script_url = escape(url_for("static", filename="js/growstar-feedback.js"))

    assets = (
        f'    <meta name="csrf-token" content="{token}">\n'
        f'    <script data-growstar-feedback src="{script_url}"></script>\n'
    )

    html = html[:head_end] + assets + html[head_end:]
    response.set_data(html)
    return response


def install_auth(app):
    """
    Installiert Login, zentrale RBAC-Prüfung, CSRF-Schutz und globales
    Benutzer-Feedback für Growstar.

    routes/admin.py behält seine feingranularen Decorators. Die bestehenden
    Grow-/Hardware-/Konfigurationsrouten werden zusätzlich über auth.policy
    nach Pfad und HTTP-Methode geschützt.
    """

    app.permanent_session_lifetime = timedelta(hours=12)

    @app.before_request
    def load_current_user_and_require_permissions():
        user_id = session.get("user_id")
        user = load_user(user_id) if user_id else None

        if user:
            session_version = session.get("session_version")
            if session_version != user.get("session_version"):
                session.clear()
                user = None

        g.current_user = user
        g.required_permissions = None

        if user_id and not g.current_user:
            session.clear()

        if request.endpoint in PUBLIC_ENDPOINTS:
            return None

        if request.path.startswith("/static/"):
            return None

        if not g.current_user:
            return _authentication_required_response()

        # Schreibende Requests benötigen entweder ein explizites CSRF-Token
        # oder müssen eindeutig aus derselben Origin stammen. Login prüft sein
        # Token weiterhin selbst, weil die Route öffentlich erreichbar ist.
        if request.method.upper() not in SAFE_METHODS:
            if not validate_request_csrf():
                _audit_csrf_denied()
                return _csrf_failed_response()

        requirement = permission_requirement(request.path, request.method)
        if requirement is None:
            return None

        g.required_permissions = requirement

        if requirement.allows(g.current_user.get("permissions", [])):
            return None

        _audit_denied(requirement)
        abort(403)

    @app.context_processor
    def inject_auth_context():
        current_user = getattr(g, "current_user", None)

        def has_permission(permission_name):
            return bool(
                current_user
                and permission_name in current_user.get("permissions", [])
            )

        def has_any_permission(*permission_names):
            return bool(
                current_user
                and set(permission_names).intersection(
                    current_user.get("permissions", [])
                )
            )

        def has_all_permissions(*permission_names):
            return bool(
                current_user
                and set(permission_names).issubset(
                    current_user.get("permissions", [])
                )
            )

        return {
            "current_user": current_user,
            "csrf_token": csrf_token,
            "has_permission": has_permission,
            "has_any_permission": has_any_permission,
            "has_all_permissions": has_all_permissions,
        }

    @app.after_request
    def add_global_feedback(response):
        return _inject_feedback_assets(response)

    @app.errorhandler(403)
    def permission_denied(error):
        requirement = getattr(g, "required_permissions", None)
        labels = _permission_labels(requirement)

        if request.path.startswith("/api/"):
            payload = {
                "success": False,
                "error": "forbidden",
                "message": _permission_message(requirement),
                "required_labels": labels,
            }

            if requirement:
                payload["requirement_mode"] = requirement.mode
                payload["required_permissions"] = list(requirement.permissions)

            return jsonify(payload), 403

        return render_template(
            "errors/403.html",
            requirement=requirement,
            permission_labels=labels,
        ), 403
