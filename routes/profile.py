from core.profile import (
    apply_profile,
    PROFILES,
)


def register(app):

    @app.route("/api/profile/<name>", methods=["POST"])
    def api_set_profile(name):

        ok = apply_profile(name)

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
