#!/usr/bin/env python3
import getpass
import sqlite3

from auth.database import init_auth_db
from auth.service import create_account


def main():
    init_auth_db()

    print("Growstar – ersten Administrator anlegen")
    print()

    username = input("Benutzername: ").strip()
    display_name = input("Anzeigename: ").strip() or username
    email = input("E-Mail (optional): ").strip() or None

    while True:
        password = getpass.getpass("Passwort (mind. 12 Zeichen): ")
        repeat = getpass.getpass("Passwort wiederholen: ")

        if password != repeat:
            print("Passwörter stimmen nicht überein.\n")
            continue

        try:
            user = create_account(
                username=username,
                display_name=display_name,
                email=email,
                password=password,
                roles=["Administrator"],
            )
        except ValueError as exc:
            print(f"Fehler: {exc}\n")
            continue
        except sqlite3.IntegrityError:
            print("Benutzername oder E-Mail existiert bereits.")
            return

        print()
        print(f"Administrator '{user['username']}' wurde angelegt.")
        return


if __name__ == "__main__":
    main()
