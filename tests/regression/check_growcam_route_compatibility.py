"""Keep the deployed media route's legacy GrowCam imports available."""

import ast
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services import growcam


LEGACY_IMPORTS = (
    "next_timelapse_capture_label",
    "timelapse_frame_days",
    "timelapse_download_filename",
)


def main():
    import_names = {
        alias.name for node in ast.walk(ast.parse((ROOT / "routes/camera.py").read_text()))
        if isinstance(node, ast.ImportFrom) and node.module == "services.growcam"
        for alias in node.names
    }
    for name in import_names | set(LEGACY_IMPORTS):
        assert hasattr(growcam, name), name

    config = {"camera_id": "camera_1", "enabled": True, "host": "192.168.1.10",
              "batch_id": 1, "timelapse_enabled": True}
    with patch.object(growcam, "timelapse_schedule_snapshot", return_value={"next_capture_at": 1000000}):
        assert growcam.next_timelapse_capture_label(config)
    assert growcam.next_timelapse_capture_label({**config, "enabled": False}) is None
    print("GrowCam route imports and legacy helpers OK")


if __name__ == "__main__":
    main()
