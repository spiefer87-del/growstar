#!/usr/bin/env python3
"""Regression fuer Growstar 3.16.27 / PLANT.PHOTO.5."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    manager = (ROOT / "templates/plants/photos.html").read_text(encoding="utf-8")

    require(
        'name="plant_id"' in manager
        and 'name="stage"' in manager
        and 'name="batch_id"' in manager,
        "Pflanzen-, Phasen- und Durchgangsfilter bleiben Bestandteil der URL",
    )
    require(
        "history.pushState(" in manager
        and "pmPhotoLightbox: {index: currentIndex}" in manager
        and "window.location.href" in manager,
        "Das Oeffnen der Galerie erzeugt einen eigenen Verlaufseintrag auf derselben Filter-URL",
    )
    require(
        'window.addEventListener("popstate"' in manager
        and "const galleryState = event.state?.pmPhotoLightbox" in manager
        and "hide();" in manager,
        "Browser- und Android-Zurueck schliessen zuerst die Galerie",
    )
    require(
        "history.back();" in manager
        and 'closeButton.addEventListener("click", close)' in manager
        and 'if (event.key === "Escape") close();' in manager,
        "Schliessen-Schalter und Escape entfernen denselben Galerie-Verlaufseintrag",
    )
    require(
        "history.replaceState(" in manager
        and "function rememberIndex()" in manager
        and "function navigate(index)" in manager,
        "Der aktuelle Wischstand wird im Galerie-Verlauf aktualisiert",
    )
    require(
        'const items = Array.from(document.querySelectorAll("[data-lightbox-item]"));'
        in manager
        and "show(index, item, true)" in manager,
        "Die Verlaufskorrektur nutzt weiterhin nur die serverseitig gefilterten Bildkarten",
    )

    print("✅ Growstar 3.16.27 / PLANT.PHOTO.5 vollstaendig geprueft")


if __name__ == "__main__":
    main()
