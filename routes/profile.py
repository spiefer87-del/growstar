from core.profile import (
    ProfileActivationError,
    apply_profile,
    PROFILES,
)


def register(app):

    @app.route("/api/profile/<name>", methods=["POST"])
    def api_set_profile(name):

        try:
            ok = apply_profile(name)
        except ProfileActivationError as exc:
            return {
                "error": exc.code,
                "message": str(exc),
            }, 409

        if not ok:
            return {
                "error": "unknown profile"
            }, 404

        return {
            "status": "ok",
            "active": name
        }

    @app.route("/api/profile")
    def get_profile_api():

        return {
            "active": PROFILES.get("active")
        }
