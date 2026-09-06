#!/usr/bin/env python3
"""Regression fuer Growstar 3.16.26 / PLANT.PHOTO.4."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    manager = (ROOT / "templates/plants/photos.html").read_text(encoding="utf-8")
    routes = (ROOT / "routes/plant_management.py").read_text(encoding="utf-8")
    css = (ROOT / "static/css/plant-management.css").read_text(encoding="utf-8")

    require(
        "growstar_photo_endpoints" in base
        and "url_for('plant_photo_manager')" in base
        and "<span>Fotos</span><small>Foto-Manager</small>" in base,
        "Der Foto-Manager ist als eigener Eintrag in der Pflanzen-Navigation vorhanden",
    )
    require(
        "growstar_endpoint not in growstar_photo_endpoints" in base
        and "growstar_endpoint in growstar_photo_endpoints" in base,
        "Foto-Routen aktivieren nur den Foto-Menuepunkt",
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

    print("✅ Growstar 3.16.26 / PLANT.PHOTO.4 vollstaendig geprueft")


if __name__ == "__main__":
    main()
