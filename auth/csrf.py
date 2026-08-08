import hmac
import secrets

from flask import session


SESSION_KEY = "_csrf_token"


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
