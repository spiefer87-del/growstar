#!/usr/bin/env python3
"""Overview API exposes fresh outside measurements and derives VPD safely."""

import ast
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.helpers import calculate_target_vpd

source = ast.parse((ROOT / "routes/tents.py").read_text())
function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "_tent_list_payload")
scope = {"calculate_target_vpd": calculate_target_vpd}
exec(compile(ast.Module(body=[function], type_ignores=[]), "routes/tents.py", "exec"), scope)


def payload(outside_temp, outside_hum):
    runtime = SimpleNamespace(
        tent_id="tent_1", name="Zelt 1", loop_mode="live", last_loop_ts=100,
        enabled=True, shadow_enabled=False, control_enabled=True,
        live_requested=True, arming=False, state_lock=nullcontext(),
        state=SimpleNamespace(live_state={
            "temp": 26.2, "hum": 66.9, "vpd": 1.13,
            "outside_temp": outside_temp, "outside_hum": outside_hum,
            "outside_temp_source": {"label": "Außenthermometer"} if outside_temp is not None else None,
            "outside_hum_source": {"label": "Außenfeuchte-Sensor"} if outside_hum is not None else None,
        }),
    )
    scope["_runtime_map"] = lambda: {"tent_1": runtime}
    scope["tent_manager"] = SimpleNamespace(
        list_tents=lambda: [{"id": "tent_1", "name": "Zelt 1"}, {"id": "tent_2", "name": "Zelt 2"}],
        default_tent_id=lambda: "tent_1",
    )
    return scope["_tent_list_payload"]()["tents"]


ready, offline = payload(19.1, 67.3)
assert ready["outside_temp"] == 19.1 and ready["outside_hum"] == 67.3
assert ready["outside_vpd"] == calculate_target_vpd(19.1, 67.3)
assert ready["outside_temp_label"] == "Außenthermometer"
assert ready["outside_hum_label"] == "Außenfeuchte-Sensor"
assert offline["runtime_loaded"] is False and "outside_vpd" not in offline
print("✅ Außenwerte und abgeleiteter VPD stammen von der richtigen Station")

for temp, hum in ((None, 67.3), (19.1, None), (19.1, 101), (float("nan"), 60)):
    missing = payload(temp, hum)[0]
    assert missing["outside_vpd"] is None
print("✅ Fehlende und ungültige Außenwerte erzeugen keinen erfundenen VPD")
