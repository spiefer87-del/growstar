from auth.policy import permission_requirement


CASES = [
    # Lesen
    ("/", "GET", ("dashboard.view",), "all"),
    ("/api/state", "GET", ("grow.view",), "all"),
    ("/api/config", "GET", ("grow.view", "settings.view"), "any"),
    ("/energie/settings", "GET", ("settings.view",), "all"),
    ("/devices/blu/abc", "GET", ("hardware.view",), "all"),

    # Grow bedienen / konfigurieren
    ("/api/device/mode/heating", "POST", ("grow.control",), "all"),
    ("/api/device/heating", "POST", ("grow.configure",), "all"),
    ("/api/config", "POST", ("grow.configure", "settings.manage"), "any"),
    ("/api/profile/TAG", "POST", ("grow.configure", "settings.manage"), "any"),
    ("/api/diagrams/import", "POST", ("grow.configure",), "all"),
    ("/api/reset_history", "POST", ("settings.manage",), "all"),

    # Pflanzen / Tagebuch
    ("/api/plants/data", "POST", ("plants.edit",), "all"),
    ("/api/diary/1", "DELETE", ("diary.edit",), "all"),

    # Hardware steuern vs. konfigurieren
    ("/api/hardware/scan", "POST", ("hardware.control",), "all"),
    ("/api/hardware/gw1/refresh", "POST", ("hardware.control",), "all"),
    ("/api/hardware/device/dev1/read-values", "POST", ("hardware.control",), "all"),
    ("/api/hardware/gw1/ble/scan", "POST", ("hardware.control",), "all"),
    ("/api/hardware/device/dev1/pair", "POST", ("hardware.configure",), "all"),
    ("/api/hardware/device/dev1/setup-sensors", "POST", ("hardware.configure",), "all"),
    ("/api/sensors/assignments", "POST", ("hardware.configure",), "all"),

    # Fail-closed
    ("/api/unknown-control", "POST", ("grow.control",), "all"),
]


for path, method, expected_permissions, expected_mode in CASES:
    requirement = permission_requirement(path, method)
    assert requirement is not None, (path, method, "missing requirement")
    assert requirement.permissions == expected_permissions, (
        path,
        method,
        requirement.permissions,
        expected_permissions,
    )
    assert requirement.mode == expected_mode, (
        path,
        method,
        requirement.mode,
        expected_mode,
    )

assert permission_requirement("/static/app.js", "GET") is None

print("✅ Phase-3-Rechtematrix OK")
