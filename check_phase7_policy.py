from auth.policy import permission_requirement


CASES = [
    (
        "/pflanzenmanagement/genetik",
        "GET",
        ("plants.view",),
    ),
    (
        "/pflanzenmanagement/genetik/linien/1",
        "POST",
        ("plants.edit",),
    ),
    (
        "/pflanzenmanagement/vermehrung",
        "GET",
        ("plants.view",),
    ),
    (
        "/pflanzenmanagement/vermehrung/saatgut/1/bewegung",
        "POST",
        ("plants.edit",),
    ),
    (
        "/pflanzenmanagement/vermehrung/ansaetze/neu",
        "POST",
        ("plants.edit",),
    ),
    (
        "/pflanzenmanagement/tagebuch",
        "GET",
        ("diary.view",),
    ),
    (
        "/pflanzenmanagement/tagebuch/neu",
        "POST",
        ("diary.edit",),
    ),
]

for path, method, permissions in CASES:
    requirement = permission_requirement(path, method)
    assert requirement is not None, (path, method, "missing")
    assert requirement.permissions == permissions, (
        path,
        method,
        requirement.permissions,
        permissions,
    )

print("✅ Phase 7 Policy-Mapping OK")
