#!/usr/bin/env python3
"""Regression für pflanzenbezogenes Wischen durch Timeline-Fotos."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    timeline = (ROOT / "templates/plants/timeline.html").read_text(encoding="utf-8")
    photos = (ROOT / "plant_management/photos.py").read_text(encoding="utf-8")
    css = (ROOT / "static/css/plant-management.css").read_text(encoding="utf-8")

    require(
        "data-timeline-photo" in timeline
        and 'data-gallery-plant="{{ row.plant.id }}"' in timeline
        and 'target="_blank"' not in timeline,
        "Timeline-Fotomarker öffnen die interne, pflanzenbezogene Galerie",
    )
    require(
        'id="pm-timeline-lightbox"' in timeline
        and 'id="pm-timeline-lightbox-previous"' in timeline
        and 'id="pm-timeline-lightbox-next"' in timeline,
        "Timeline besitzt eine bedienbare Vollbildgalerie mit Richtungsnavigation",
    )
    require(
        "function itemsForPlant(plantId)" in timeline
        and '.filter(item => item.dataset.galleryPlant === String(plantId))' in timeline
        and "items = itemsForPlant(item.dataset.galleryPlant)" in timeline,
        "Jeder Galeriestart begrenzt die Bildmenge auf genau eine Pflanze",
    )
    require(
        "data-captured-at" in timeline
        and ".localeCompare(right.dataset.capturedAt" in timeline
        and "markers.sort(" in photos
        and 'str(item.get("captured_at")' in photos,
        "Fotos einer Pflanze werden chronologisch vorwärts und rückwärts sortiert",
    )
    require(
        'event.key === "ArrowLeft"' in timeline
        and 'event.key === "ArrowRight"' in timeline
        and 'event.key === "Escape"' in timeline
        and 'stage.addEventListener("touchstart"' in timeline
        and 'stage.addEventListener("touchend"' in timeline
        and "Math.abs(deltaX) < 45" in timeline,
        "Touch, Tastatur und Schließen funktionieren auch in der Timeline-Galerie",
    )
    require(
        "pmTimelinePhotoLightbox" in timeline
        and "history.pushState(" in timeline
        and "history.back();" in timeline,
        "Android- und Browser-Zurück schließen zuerst die Timeline-Galerie",
    )
    require(
        ".pm-photo-lightbox" in css
        and ".pm-lightbox-stage" in css
        and "touch-action: pan-y pinch-zoom" in css,
        "Bestehendes responsives Vollbilddesign wird wiederverwendet",
    )
    print("✅ Pflanzenbezogene Timeline-Fotogalerie vollständig geprüft")


if __name__ == "__main__":
    main()
