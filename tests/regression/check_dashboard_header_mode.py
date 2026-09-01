#!/usr/bin/env python3
"""Regression für Tag/Nacht im Stationskopf und eine reine Profilkachel."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    dashboard = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")

    ids = re.findall(r'\bid="([^"]+)"', dashboard)
    require(
        len(ids) == len(set(ids)),
        "Verschobener Klimamodus erzeugt keine doppelten HTML-IDs",
    )

    heading_start = dashboard.find('<div class="topline">')
    heading_end = dashboard.find('<div id="safety-banner"')
    mode_position = dashboard.find('id="climate-mode"')
    require(
        heading_start >= 0
        and heading_start < mode_position < heading_end,
        "Sonnen-/Mondsymbol liegt im Stationskopf vor den Umgebungswerten",
    )
    require(
        'class="header-climate-mode"' in dashboard
        and 'class="header-climate-mode-icon"' in dashboard
        and 'role="img"' in dashboard
        and 'aria-live="polite"' in dashboard,
        "Kopf-Indikator ist kompakt und zugänglich ausgezeichnet",
    )

    mode_css = re.search(
        r"\.header-climate-mode\s*\{(?P<body>.*?)\n\}",
        dashboard,
        re.DOTALL,
    )
    require(
        mode_css is not None
        and "width: 42px" in mode_css.group("body")
        and "height: 42px" in mode_css.group("body")
        and "border-radius: 50%" in mode_css.group("body"),
        "Tag/Nacht erscheint als dezenter runder Indikator",
    )
    require(
        ".header-climate-mode.tag" in dashboard
        and ".header-climate-mode.nacht" in dashboard
        and 'mode === "TAG" ? "☀️"' in dashboard
        and 'mode === "NACHT" ? "🌙"' in dashboard,
        "Tag und Nacht erhalten weiterhin eindeutige Symbole und Verläufe",
    )

    profile_match = re.search(
        r'<div class="card env" id="profile-card">(?P<body>.*?)\n\s*</div>\n\s*</a>',
        dashboard,
        re.DOTALL,
    )
    require(profile_match is not None, "Profilkachel wurde gefunden")
    profile_card = profile_match.group("body")
    require(
        "<h2>Profil</h2>" in profile_card
        and 'id="profile-badge"' in profile_card
        and "Klima &amp; Grenzwerte" in profile_card,
        "Profilkachel priorisiert Phase und Zielseite",
    )
    require(
        'id="climate-mode"' not in profile_card
        and 'id="climate-mode-icon"' not in profile_card
        and 'id="profile-phase"' not in profile_card
        and "<h2>Klimamodus</h2>" not in profile_card,
        "Tag/Nacht wurde vollständig aus der Profilkachel entfernt",
    )
    require(
        'profileBadge.className = `phase-badge ${activeProfile}`' in dashboard
        and 'climateMode.className = `header-climate-mode ${modeClass}`.trim()' in dashboard
        and 'safeText("profile-phase", state.profile' in dashboard,
        "State aktualisiert Kopf-Indikator und Profilphase weiterhin getrennt",
    )
    require(
        "grow_control_tent_settings" in dashboard,
        "Vereinfachte Profilkachel öffnet weiterhin Klima & Grenzwerte",
    )

    print("✅ Growstar 3.15.13 / DASHBOARD.MODE.1 vollständig geprüft")


if __name__ == "__main__":
    main()
