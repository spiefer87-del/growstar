#!/usr/bin/env python3
"""Phase 4N.1 – Auth-Merge-Regressionsschutz.

Prüft, dass Phase 4N die bereits vorhandenen Energie-Rechte nicht verliert.
Keine Hardware- oder Netzwerkzugriffe.
"""
from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parent


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("✅", msg)


def main():
    policy_path = ROOT / "auth" / "policy.py"
    source = policy_path.read_text(encoding="utf-8")
    ast.parse(source, filename="auth/policy.py")
    print("✅ Python-Syntax auth/policy.py")

    require(
        '"/energie/diagramme": require("grow.view")' in source,
        "Energie-Diagrammseite behält grow.view",
    )
    require(
        'if "/energy/reset_" in path:' in source,
        "Stationsbezogene Energie-Reset-Regel ist vorhanden",
    )

    spec = importlib.util.spec_from_file_location("phase4n1_policy", policy_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    diag = mod.permission_requirement("/energie/diagramme", "GET")
    require(
        diag is not None
        and diag.permissions == ("grow.view",),
        "GET /energie/diagramme wird tatsächlich als grow.view ausgewertet",
    )

    reset = mod.permission_requirement(
        "/api/tents/tent_1/energy/reset_today",
        "POST",
    )
    require(
        reset is not None
        and reset.permissions == ("grow.configure",),
        "Stationsbezogener Energie-Reset wird tatsächlich als grow.configure ausgewertet",
    )

    design_read = mod.permission_requirement(
        "/grow-control/tents/tent_1/design",
        "GET",
    )
    require(
        design_read is not None
        and design_read.permissions == ("settings.view",),
        "Phase-4N-Designrecht settings.view bleibt erhalten",
    )

    print("✅ Phase 4N.1 Auth-Merge vollständig")


if __name__ == "__main__":
    main()
