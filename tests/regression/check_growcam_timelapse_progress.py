#!/usr/bin/env python3
"""Regression für echten Fortschritt der Zeitraffer-Erstellung."""

from pathlib import Path
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.growcam as growcam


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    status = growcam._new_status()
    growcam._update_timelapse_progress(status, 100, 37)
    require(
        status["timelapse_processed_frames"] == 37
        and 37 <= status["timelapse_progress"] <= 40
        and status["timelapse_stage"] == "Video wird kodiert",
        "Verarbeitete FFmpeg-Frames werden in einen echten Prozentwert umgerechnet",
    )

    with tempfile.TemporaryDirectory(prefix="growstar-progress-") as temp_dir:
        progress_file = Path(temp_dir) / "render.progress"
        stop = threading.Event()
        thread = threading.Thread(
            target=growcam._monitor_timelapse_progress,
            args=(progress_file, status, 100, stop),
        )
        thread.start()
        progress_file.write_text("frame=62\nprogress=continue\n", encoding="utf-8")
        thread.join(timeout=.4)
        stop.set()
        thread.join(timeout=1)
        require(
            status["timelapse_processed_frames"] == 62
            and status["timelapse_progress"] >= 60,
            "Growstar liest den laufenden Framezähler aus der FFmpeg-Fortschrittsdatei",
        )

    template = (ROOT / "templates/plants/timelapse.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/plant-management.css").read_text(encoding="utf-8")
    require(
        'id="timelapse-progress"' in template
        and 'role="progressbar"' in template
        and "timelapse_progress" in template
        and "timelapse_processed_frames" in template,
        "Zeitraffer-Seite zeigt Prozentbalken, Arbeitsschritt und Bildfortschritt",
    )
    require(
        "growcam_status_api" in template
        and "fetch(statusUrl" in template
        and "window.setTimeout(pollProgress,1000)" in template
        and "window.location.reload()" in template,
        "Die Seite fragt den Kamerastatus live ab und lädt das fertige Video nach Abschluss",
    )
    require(
        ".pm-timelapse-progress-track" in css
        and "transition: width .35s ease" in css,
        "Der Fortschritt ist als kompakter responsiver Ladebalken gestaltet",
    )

    print("✅ GROWCAM.TIMELAPSE-PROGRESS.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
