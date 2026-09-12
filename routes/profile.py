from core.profile import (
    ProfileActivationError,
    apply_profile,
    PROFILES,
)
from core.runtime import get_default_runtime
from services.grow_events import enqueue_event
import time


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

        occurred_at = int(time.time())
        runtime = get_default_runtime()
        enqueue_event(
            station_id=runtime.tent_id,
            occurred_at=occurred_at,
            category="system",
            event_type="grow_profile_applied",
            severity="success",
            title=f"Grow-Profil aktiviert: {name}",
            summary="Die gespeicherten Profilwerte wurden auf die Station angewendet.",
            source="profile_manager",
            source_id=str(name),
            dedupe_key=f"profile-apply:{runtime.tent_id}:{name}:{occurred_at // 60}",
            metadata={"profil": name},
        )

        return {
            "status": "ok",
            "active": name
        }

    @app.route("/api/profile")
    def get_profile_api():

        return {
            "active": PROFILES.get("active")
        }
