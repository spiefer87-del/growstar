from urllib.parse import urlsplit

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

from auth.csrf import rotate_csrf_token, validate_csrf_token
from auth.database import write_audit
from auth.decorators import login_required
from auth.service import authenticate


def _safe_next_url(value):
    if not value:
        return None

    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return None

    if not value.startswith("/") or value.startswith("//"):
        return None

    return value


def register(app):
    @app.route("/login", methods=["GET", "POST"], endpoint="auth_login")
    def login():
        if g.get("current_user"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            if not validate_csrf_token(request.form.get("csrf_token")):
                abort(400, "Ungültiges CSRF-Token")

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = authenticate(username, password)

            if not user:
                write_audit(
                    action="auth.login_failed",
                    details={"username": username},
                    ip_address=request.remote_addr,
                )
                flash("Benutzername oder Passwort ist falsch.", "error")
            else:
                next_url = _safe_next_url(
                    request.form.get("next") or request.args.get("next")
                )

                session.clear()
                session["user_id"] = user["id"]
                session["session_version"] = user["session_version"]
                session.permanent = True
                rotate_csrf_token()

                write_audit(
                    action="auth.login",
                    user_id=user["id"],
                    ip_address=request.remote_addr,
                )

                return redirect(next_url or url_for("dashboard"))

        return render_template(
            "auth/login.html",
            next_url=_safe_next_url(request.args.get("next")),
        )

    @app.post("/logout", endpoint="auth_logout")
    @login_required
    def logout():
        if not validate_csrf_token(request.form.get("csrf_token")):
            abort(400, "Ungültiges CSRF-Token")

        user_id = g.current_user["id"]
        write_audit(
            action="auth.logout",
            user_id=user_id,
            ip_address=request.remote_addr,
        )

        session.clear()
        return redirect(url_for("auth_login"))
