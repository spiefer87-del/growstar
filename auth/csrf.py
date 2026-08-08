import hmac
import secrets
from urllib.parse import urlsplit

from flask import request, session


SESSION_KEY = "_csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def rotate_csrf_token():
    token = secrets.token_urlsafe(32)
    session[SESSION_KEY] = token
    return token


def validate_csrf_token(candidate):
    expected = session.get(SESSION_KEY)
    if not expected or not candidate:
        return False
    return hmac.compare_digest(expected, candidate)


def _normalized_origin(url):
    """Normalisiert scheme://host:port für sichere Same-Origin-Vergleiche."""

    try:
        parts = urlsplit(url)
    except Exception:
        return None

    if not parts.scheme or not parts.hostname:
        return None

    scheme = parts.scheme.lower()
    host = parts.hostname.lower()

    try:
        port = parts.port
    except ValueError:
        return None

    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else None

    if port is None:
        return None

    return scheme, host, port


def _request_origin():
    # request.host_url berücksichtigt hinter ProxyFix auch X-Forwarded-Proto
    # und X-Forwarded-Host des vertrauenswürdigen Caddy-Proxys.
    return _normalized_origin(request.host_url)


def _same_origin(value):
    candidate = _normalized_origin(value)
    expected = _request_origin()
    return bool(candidate and expected and candidate == expected)


def validate_request_csrf():
    """
    CSRF-Prüfung für bestehende und neue schreibende Requests.

    Reihenfolge:
    1. Sicherer HTTP-Request -> erlaubt.
    2. Explizites CSRF-Token aus Header/Form -> erlaubt.
    3. Same-Origin Origin/Referer -> erlaubt.
    4. Sonst -> blockieren.

    Damit bleiben bestehende Same-Origin fetch()-Aufrufe kompatibel, während
    externe Webseiten keine schreibenden Requests mit der Growstar-Session
    ausführen können. Neue API-Aufrufe sollten bevorzugt X-CSRF-Token senden.
    """

    if request.method.upper() in SAFE_METHODS:
        return True

    candidate = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    if candidate and validate_csrf_token(candidate):
        return True

    origin = request.headers.get("Origin")
    if origin:
        return _same_origin(origin)

    referer = request.headers.get("Referer")
    if referer:
        return _same_origin(referer)

    return False
