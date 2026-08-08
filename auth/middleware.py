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
        g.current_user = load_user(user_id) if user_id else None

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
        return {
            "current_user": getattr(g, "current_user", None),
            "csrf_token": csrf_token,
        }
