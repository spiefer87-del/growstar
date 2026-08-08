from datetime import timedelta

from flask import g, redirect, request, session, url_for

from .csrf import csrf_token
from .database import load_user


PUBLIC_ENDPOINTS = {
    "auth_login",
    "static",
}


def install_auth(app):
    """Installiert Session-Login als Standard-Schutz für die gesamte Web-App."""

    app.permanent_session_lifetime = timedelta(hours=12)

    @app.before_request
    def load_current_user_and_require_login():
        user_id = session.get("user_id")
        user = load_user(user_id) if user_id else None

        # Phase 2: Passwort-Reset kann alle bisherigen Sessions dieses Users
        # ungültig machen. Alte Phase-1-Sessions werden einmalig neu angemeldet.
        if user:
            session_version = session.get("session_version")
            if session_version != user.get("session_version"):
                session.clear()
                user = None

        g.current_user = user

        if user_id and not g.current_user:
            session.clear()

        if request.endpoint in PUBLIC_ENDPOINTS:
            return None

        if request.path.startswith("/static/"):
            return None

        if g.current_user:
            return None

        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("auth_login", next=next_url))

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

        return {
            "current_user": current_user,
            "csrf_token": csrf_token,
            "has_permission": has_permission,
            "has_any_permission": has_any_permission,
        }
