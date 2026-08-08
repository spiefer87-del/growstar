from app import flask_app
from auth.policy import permission_requirement


def describe(requirement):
    if requirement is None:
        return "eigene Route/Decorator"

    joiner = " ODER " if requirement.mode == "any" else " UND "
    return joiner.join(requirement.permissions)


print("Growstar Phase 3 – registrierte Routen und Rechte\n")

for rule in sorted(flask_app.url_map.iter_rules(), key=lambda item: item.rule):
    methods = sorted(
        method
        for method in rule.methods
        if method not in {"HEAD", "OPTIONS"}
    )

    for method in methods:
        requirement = permission_requirement(rule.rule, method)
        print(
            f"{method:7} {rule.rule:42} "
            f"{rule.endpoint:30} -> {describe(requirement)}"
        )
