from functools import wraps

from flask import abort, g, redirect, request, url_for


def _login_redirect():
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("auth_login", next=next_url))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "current_user", None):
            return _login_redirect()
        return view(*args, **kwargs)

    return wrapped


def permission_required(permission_name):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return _login_redirect()

            if permission_name not in user.get("permissions", []):
                abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator


def any_permission_required(*permission_names):
    required = set(permission_names)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return _login_redirect()

            user_permissions = set(user.get("permissions", []))
            if not required.intersection(user_permissions):
                abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator
