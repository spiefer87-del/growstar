from auth.policy import permission_requirement


CASES = [
    ("/", "GET", ("dashboard.view",), "all"),
    ("/grow-control", "GET", ("grow.view",), "all"),
    (
        "/pflanzenmanagement",
        "GET",
        ("plants.view", "diary.view"),
        "any",
    ),
    ("/pflanzendaten", "GET", ("plants.view",), "all"),
    ("/tagebuch", "GET", ("diary.view",), "all"),
]


for path, method, permissions, mode in CASES:
    requirement = permission_requirement(path, method)

    assert requirement is not None, (path, "missing requirement")
    assert requirement.permissions == permissions, (
        path,
        requirement.permissions,
        permissions,
    )
    assert requirement.mode == mode, (
        path,
        requirement.mode,
        mode,
    )


print("✅ Dashboard-/Modul-Navigation OK")
