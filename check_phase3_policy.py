from auth.policy import permission_requirement

CASES = [
    ("/", "GET", ("dashboard.view",)),
    ("/api/state", "GET", ("grow.view",)),
    ("/heizung", "GET", ("grow.view",)),
    ("/api/config", "POST", ("grow.configure", "settings.manage")),
    ("/api/plants", "POST", ("plants.edit",)),
    ("/api/diary/1", "DELETE", ("diary.edit",)),
    ("/devices/blu/abc", "GET", ("hardware.view",)),
    ("/api/device/abc", "PATCH", ("hardware.configure",)),
    ("/api/unknown-control", "POST", ("grow.control",)),
]

for path, method, expected in CASES:
    requirement = permission_requirement(path, method)
    assert requirement is not None, (path, method, "missing requirement")
    assert requirement.permissions == expected, (
        path,
        method,
        requirement.permissions,
        expected,
    )

print("✅ Phase-3-Rechtematrix OK")
