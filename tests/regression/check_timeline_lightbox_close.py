#!/usr/bin/env python3
"""Regression für den erreichbaren unteren Timeline-Galerieschalter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    timeline = (ROOT / "templates/plants/timeline.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/plant-management.css").read_text(encoding="utf-8")

    footer_start = timeline.index('<div class="pm-timeline-lightbox-footer">')
    footer_end = timeline.index("</div>\n</div>\n</main>", footer_start)
    footer = timeline[footer_start:footer_end]

    require(
        'id="pm-timeline-lightbox-close"' in footer
        and "pm-lightbox-close-bottom" in footer
        and "✕ Schließen" in footer,
        "Timeline-Galerie besitzt unten einen beschrifteten Schließen-Schalter",
    )
    require(
        "z-index: 10050" in css,
        "Vollbildgalerie liegt sichtbar über der festen Growstar-Kopfzeile",
    )
    require(
        ".pm-timeline-lightbox-footer" in css
        and "grid-row: 3" in css
        and ".pm-lightbox-close-bottom" in css,
        "Der untere Bedienbereich bleibt Teil des sichtbaren Vollbildrasters",
    )
    require(
        "width: min(100%, 280px)" in css
        and "height: 48px" in css
        and "touch-action: manipulation" in css,
        "Der Schließen-Schalter bietet eine große mobile Touch-Fläche",
    )
    require(
        'const closeButton = document.getElementById("pm-timeline-lightbox-close")' in timeline
        and 'closeButton.addEventListener("click", close)' in timeline,
        "Der verlegte Schalter verwendet weiterhin die getestete Schließlogik",
    )
    print("✅ Unterer Timeline-Galerieschalter vollständig geprüft")


if __name__ == "__main__":
    main()
