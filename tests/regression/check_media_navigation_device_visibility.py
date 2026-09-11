#!/usr/bin/env python3
"""Regression für Medienaufnahme, Menüreihenfolge und Gerätesichtbarkeit."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    batch_form = (ROOT / "templates/plants/batch_photo_form.html").read_text(encoding="utf-8")
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")

    batch_route = routes[routes.index("def batch_photo_new") : routes.index("def batch_photo_file")]
    require(
        "growcam_camera_id" in batch_route
        and "growcam_capture_snapshot" in batch_route
        and "growcam_latest_image_path" in batch_route
        and "growcams=[" in batch_route,
        "Durchgangsfotos können serverseitig direkt von einer GrowCam aufgenommen werden",
    )
    require(
        'id="batch-growcam-select"' in batch_form
        and 'name="growcam_camera_id"' in batch_form
        and "GrowCam nimmt Foto auf" in batch_form,
        "Durchgangsfoto-Formular bietet die GrowCam als eigene Bildquelle an",
    )
    require(
        base.index('growstar-nav-section-plants')
        < base.index('growstar-nav-section-media')
        < base.index('growstar-nav-section-hardware'),
        "Pflanzenmanagement und Medien stehen vor Hardware & Setup",
    )
    require(
        'id="growstar-admin-submenu"' in base
        and "growstar_admin_active" in base
        and 'aria-controls="growstar-admin-submenu"' in base,
        "Administrator besitzt dieselbe Klappnavigation wie die Hauptmodule",
    )
    print("✅ Medien-, Navigations- und Gerätesichtbarkeit vollständig geprüft")


if __name__ == "__main__":
    main()
