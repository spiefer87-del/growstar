"""Growstar Alarm- und Telegram-Benachrichtigungseinstellungen."""

from flask import jsonify, render_template, request

from auth.decorators import permission_required
from services.alerts import alarm_runtime_status
from services.notification_settings import (
    clear_telegram_connection,
    load_notification_settings,
    public_notification_settings,
    save_bot_connection,
    save_discovered_chat,
    update_notification_preferences,
)
from services.notifications import (
    notification_runtime_status,
    send_test_notification,
)
from services.telegram import (
    TelegramError,
    discover_private_chat,
    get_me,
    validate_token_format,
)


def _error(message, status=400):
    return jsonify(
        success=False,
        error=str(message),
    ), status


def register(app):

    @app.route("/system/notifications")
    @permission_required("settings.view")
    def growstar_notifications_page():
        return render_template("notifications.html")

    @app.route("/system/notifications/status")
    @permission_required("settings.view")
    def growstar_notifications_status():
        return jsonify(
            success=True,
            settings=public_notification_settings(),
            notifications=notification_runtime_status(),
            alarms=alarm_runtime_status(),
        )

    @app.route("/system/notifications/telegram/connect", methods=["POST"])
    @permission_required("settings.manage")
    def growstar_notifications_telegram_connect():
        data = request.get_json(silent=True) or {}

        try:
            token = validate_token_format(data.get("token"))
            identity = get_me(token)
            settings = save_bot_connection(token, identity)
        except (ValueError, TelegramError) as exc:
            return _error(exc)

        return jsonify(
            success=True,
            settings=settings,
            bot=identity,
        )

    @app.route("/system/notifications/telegram/discover", methods=["POST"])
    @permission_required("settings.manage")
    def growstar_notifications_telegram_discover():
        settings = load_notification_settings()
        token = (settings.get("telegram") or {}).get("bot_token")

        if not token:
            return _error("Telegram Bot ist noch nicht verbunden")

        try:
            chat = discover_private_chat(token)
            public = save_discovered_chat(chat)
        except (ValueError, TelegramError) as exc:
            return _error(exc)

        return jsonify(
            success=True,
            settings=public,
            chat=chat,
        )

    @app.route("/system/notifications/preferences", methods=["POST"])
    @permission_required("settings.manage")
    def growstar_notifications_preferences():
        data = request.get_json(silent=True) or {}

        try:
            settings = update_notification_preferences(data)
        except (TypeError, ValueError) as exc:
            return _error(exc)

        return jsonify(
            success=True,
            settings=settings,
        )

    @app.route("/system/notifications/telegram/test", methods=["POST"])
    @permission_required("settings.manage")
    def growstar_notifications_telegram_test():
        try:
            result = send_test_notification()
        except (ValueError, TelegramError) as exc:
            return _error(exc, 503)

        return jsonify(
            success=True,
            result=result,
        )

    @app.route("/system/notifications/telegram/clear", methods=["POST"])
    @permission_required("settings.manage")
    def growstar_notifications_telegram_clear():
        return jsonify(
            success=True,
            settings=clear_telegram_connection(),
        )
