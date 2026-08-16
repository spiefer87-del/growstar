#!/usr/bin/env python3
"""Phase 4Q – Growstar Versions- und Patch-Informationssystem.

Nur Read-only/UI-/Routing-Tests. Keine Hardware- oder Netzwerkzugriffe.
"""

from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_checks():
    for rel in (
        "core/release.py",
        "routes/release.py",
        "app.py",
        "auth/policy.py",
    ):
        ast.parse(read(rel), filename=rel)
        print("✅ Python-Syntax", rel)

    release = read("core/release.py")
    route = read("routes/release.py")
    app = read("app.py")
    policy = read("auth/policy.py")
    base = read("templates/base.html")
    notes = read("templates/patch_notes.html")

    require(
        '"version": "3.6.2"' in release
        and 'GROWSTAR_VERSION = RELEASES[0]["version"]' in release,
        "Growstar 3.6.2 wird aus genau einer zentralen Release-Quelle abgeleitet",
    )
    require(
        '"version": "3.6.1"' in release
        and '"phase": "4P"' in release,
        "Vorheriger Universal-Aktor-Patch bleibt in der Release-Historie",
    )
    require(
        '"phase": "4Q"' in release
        and 'GROWSTAR_INTERNAL_PHASE = RELEASES[0]["phase"]' in release,
        "Interne Build-Kennung 4Q wird zentral geführt",
    )
    require(
        '"/system/patch-notes"' in route
        and '"/api/system/version"' in route,
        "Patch-Seite und read-only Versions-API sind vorhanden",
    )
    require(
        "@app.context_processor" in route
        and '"growstar_release": release_summary()' in route,
        "base.html erhält die Version zentral über einen Context Processor",
    )
    require(
        "register_release_routes(app)" in app
        and "GROWSTAR_VERSION=GROWSTAR_VERSION" in app,
        "Flask-App registriert Release-Routen und übernimmt die zentrale Version",
    )
    require(
        "v3.6 Alpha" not in app
        and 'Growstar v{GROWSTAR_VERSION} Backend wird gestartet' in app,
        "Alte doppelte Versionsangabe wurde entfernt; Startlog nutzt Source of Truth",
    )
    require(
        '"/system/patch-notes": require("dashboard.view")' in policy
        and '"/api/system/version": require("dashboard.view")' in policy,
        "Patch-Information ist read-only für normale angemeldete Dashboard-Rollen sichtbar",
    )
    require(
        'id="growstar-release-chip"' in base
        and "Growstar v{{ growstar_release.version }}" in base,
        "Dezente globale Versionsanzeige ist in base.html vorhanden",
    )
    require(
        '"growstar_last_seen_version"' in base
        and "has-new" in base
        and ">NEU<" in base,
        "NEU-Markierung wird pro Browser lokal verwaltet",
    )
    require(
        "Was wurde geändert?" in notes
        and "Was sollte nach dem Update getestet werden?" in notes,
        "Patch-Seite trennt Änderungen und konkrete Testhinweise",
    )
    require(
        "growstar_release_tests_${version}" in notes
        and "localStorage.setItem(storageKey" in notes,
        "Test-Checkliste wird pro Version ausschließlich lokal im Browser gespeichert",
    )
    require(
        "Vorherige Änderungen" in notes
        and "releases[1:]" in notes,
        "Release-Historie zeigt ältere Patches getrennt an",
    )

    forbidden = (
        "core.actuators",
        "core.control",
        "core.safety",
        "services.shelly",
        "services.safety",
        "requests.",
        "switch_shelly",
        "set_device",
    )
    release_stack = release + "\n" + route
    require(
        not any(token in release_stack for token in forbidden),
        "Release-System besitzt keinerlei Hardware-, Safety- oder Regelungszugriff",
    )


def dynamic_checks():
    release = load_module("phase4q_release", "core/release.py")

    require(
        release.GROWSTAR_VERSION == "3.6.2",
        "Zentrale Runtime-Version ist 3.6.2",
    )
    require(
        release.release_summary() == {
            "version": "3.6.2",
            "release_date": "2026-08-16",
            "phase": "4Q",
            "title": "Versions- und Patch-Informationssystem",
        },
        "Versions-Zusammenfassung ist stabil und diagnosegeeignet",
    )
    require(
        release.current_release()["date_label"] == "16.08.2026",
        "Patch-Seite erhält ein deutsches Anzeigedatum ohne das ISO-API-Datum zu verändern",
    )
    require(
        [item["version"] for item in release.release_history()[:2]]
        == ["3.6.2", "3.6.1"],
        "Release-Historie ist neueste Version zuerst sortiert",
    )

    policy = load_module("phase4q_policy", "auth/policy.py")
    for path in ("/system/patch-notes", "/api/system/version"):
        req = policy.permission_requirement(path, "GET")
        require(
            req.permissions == ("dashboard.view",),
            f"{path} benötigt ausschließlich dashboard.view",
        )

    try:
        from flask import Flask
    except ModuleNotFoundError:
        print("ℹ️ Flask nicht installiert – dynamischer Routing-Test übersprungen")
        return

    # Route-Modul gegen das echte core.release aus diesem Testbaum laden.
    import sys
    old_path = list(sys.path)
    sys.path.insert(0, str(ROOT))
    try:
        from routes.release import register

        app = Flask(
            "phase4q-test",
            template_folder=str(ROOT / "templates"),
            static_folder=str(ROOT / "static"),
        )
        app.config.update(TESTING=True, SECRET_KEY="phase4q-test")
        app.jinja_env.globals["csrf_token"] = lambda: "test-token"
        register(app)

        client = app.test_client()

        api = client.get("/api/system/version")
        require(api.status_code == 200, "Versions-API antwortet mit HTTP 200")
        payload = api.get_json()
        require(
            payload["success"] is True
            and payload["version"] == "3.6.2"
            and payload["phase"] == "4Q",
            "Versions-API liefert die erwartete Version und Build-Kennung",
        )

        page = client.get("/system/patch-notes")
        html = page.get_data(as_text=True)
        require(page.status_code == 200, "Patch-Informationsseite rendert erfolgreich")
        require(
            "Growstar v3.6.2" in html
            and "Versions- und Patch-Informationssystem" in html,
            "Gerenderte Seite enthält globalen Versions-Chip und aktuelle Patch-Info",
        )
        require(
            "Universal-Aktoren" in html,
            "Gerenderte Seite enthält die vorherige Release-Historie",
        )
    finally:
        sys.path[:] = old_path


def main():
    static_checks()
    dynamic_checks()
    print("✅ Phase 4Q Release-/Patch-Informationssystem vollständig")


if __name__ == "__main__":
    main()
