from werkzeug.security import check_password_hash, generate_password_hash

from .database import (
    assign_role,
    create_user,
    get_user_by_username,
    load_user,
    update_last_login,
)


MIN_PASSWORD_LENGTH = 12


def hash_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein"
        )
    return generate_password_hash(password)


def create_account(
    username,
    display_name,
    password,
    email=None,
    roles=None,
):
    password_hash = hash_password(password)
    user_id = create_user(
        username=username,
        display_name=display_name,
        password_hash=password_hash,
        email=email,
    )

    for role in roles or []:
        assign_role(user_id, role)

    return load_user(user_id)


def authenticate(username, password):
    user = get_user_by_username(username)

    if not user or not user["is_active"]:
        return None

    if not check_password_hash(user["password_hash"], password):
        return None

    update_last_login(user["id"])
    return load_user(user["id"])
