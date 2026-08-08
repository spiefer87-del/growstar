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

from .csrf import csrf_token
from .database import load_user, write_audit
from .policy import permission_requirement


PUBLIC_ENDPOINTS = {
    "auth_login",
    "static",
}


def _login_redirect():
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("auth_login", next=next_url))


def _authentication_required_response():
    if request.path.startswith("/api/"):
        return jsonify(
            success=False,
            error="authentication_required",
        ), 401

    return _login_redirect()


def _audit_denied(requirement):
    # Lesende Polling-Requests würden das Audit-Log unnötig fluten. Kritische
    # Schreibversuche werden dagegen protokolliert.
    if request.method in {"GET", "HEAD", "OPTIONS"}:
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


def install_auth(app):
    """
    Installiert Login + zentrale RBAC-Prüfung für die gesamte Growstar-Web-App.

    routes/admin.py behält seine feingranularen Decorators. Alle bestehenden
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

    @app.errorhandler(403)
    def permission_denied(error):
        if request.path.startswith("/api/"):
            return jsonify(
                success=False,
                error="forbidden",
            ), 403

        requirement = getattr(g, "required_permissions", None)
        return render_template(
            "errors/403.html",
            requirement=requirement,
        ), 403
