#!/usr/bin/env python3
"""Regression fuer Foto-Galerie und eigenständige Mediennavigation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    plant_nav = (ROOT / "templates/plants/_nav.html").read_text(encoding="utf-8")
    media_nav = (ROOT / "templates/media/_nav.html").read_text(encoding="utf-8")
    manager = (ROOT / "templates/plants/photos.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    css = (ROOT / "static/css/plant-management.css").read_text(encoding="utf-8")

    require(
        "growstar_photo_endpoints" in base
        and "growstar_media_active" in base
        and "url_for('plant_photo_manager')" in base
        and "<div class=\"growstar-nav-section-title\">Medien</div>" in base
        and "<span>Foto-Manager</span><small>Pflanzen & Durchgänge</small>" in base,
        "Der Foto-Manager ist im eigenständigen Medienmodul vorhanden",
    )
    require(
        "not growstar_media_active" in base
        and "growstar_endpoint in growstar_photo_endpoints" in base
        and "plant_photo_manager" not in plant_nav
        and "growcam_page" not in plant_nav
        and "plant_media_explorer" not in plant_nav
        and "plant_photo_manager" in media_nav
        and "growcam_page" in media_nav,
        "Foto- und Kamerarouten aktivieren nur das Medienmodul",
    )
    require(
        '{% include "media/_nav.html" %}' in manager,
        "Der Foto-Manager verwendet die eigene Mediennavigation",
    )

    require(
        manager.count("data-lightbox-item") == 3
        and 'id="pm-photo-lightbox"' in manager
        and 'role="dialog"' in manager
        and 'aria-modal="true"' in manager,
        "Pflanzen- und Durchgangsfotos oeffnen dieselbe interne Vollbildgalerie",
    )
    require(
        'target="_blank"' not in manager
        and 'id="pm-lightbox-previous"' in manager
        and 'id="pm-lightbox-next"' in manager
        and 'id="pm-lightbox-close"' in manager,
        "Rohbild-Tabs sind durch bedienbare Vor-, Zurueck- und Schliessen-Schalter ersetzt",
    )

    require(
        'const items = Array.from(document.querySelectorAll("[data-lightbox-item]"));'
        in manager
        and "items.forEach((item, index)" in manager
        and "currentIndex = (index + items.length) % items.length" in manager,
        "Die Galerie verwendet ausschliesslich die aktuell gerenderten Filtertreffer und blaettert zyklisch",
    )
    require(
        'name="plant_id"' in manager
        and 'name="stage"' in manager
        and 'name="batch_id"' in manager
        and "list_plant_photos(" in routes
        and "plant_id=selected_plant_id" in routes
        and "stage=selected_stage" in routes
        and "list_batch_photos(batch_id=selected_batch_id)" in routes,
        "Pflanzen-, Phasen- und Durchgangsfilter begrenzen die serverseitige Galeriemenge",
    )

    require(
        'event.key === "ArrowLeft"' in manager
        and 'event.key === "ArrowRight"' in manager
        and 'event.key === "Escape"' in manager,
        "Tastatursteuerung fuer vorheriges, naechstes und Schliessen ist vorhanden",
    )
    require(
        'stage.addEventListener("touchstart"' in manager
        and 'stage.addEventListener("touchend"' in manager
        and "Math.abs(deltaX) < 45" in manager
        and "Math.abs(deltaX) <= Math.abs(deltaY)" in manager,
        "Horizontale Daumen-Wischgesten besitzen einen sicheren Mindestweg",
    )
    require(
        ".pm-photo-lightbox" in css
        and "position: fixed" in css
        and "object-fit: contain" in css
        and "@media (max-width: 480px)" in css,
        "Die Vollbildgalerie ist fuer Desktop und Mobilansicht gestaltet",
    )

    print("✅ Foto-Galerie und Mediennavigation vollstaendig geprueft")


if __name__ == "__main__":
    main()
