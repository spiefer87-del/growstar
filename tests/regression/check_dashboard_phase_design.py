#!/usr/bin/env python3
"""Regression für feste Profilreihenfolge und phasenbezogenes Dashboard-Design."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    dashboard = (ROOT / "templates/grow_control.html").read_text(encoding="utf-8")
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")

    dashboard_ids = re.findall(r'\bid="([^"]+)"', dashboard)
    require(
        len(dashboard_ids) == len(set(dashboard_ids)),
        "Dashboard besitzt weiterhin keine doppelten HTML-IDs",
    )

    order_match = re.search(
        r"const PROFILE_ORDER\s*=\s*Object\.freeze\((\[[^;]+\])\);",
        profiles,
    )
    require(
        order_match is not None
        and json.loads(order_match.group(1)) == ["veg", "bloom", "dry"],
        "Profilverwaltung erzwingt Vegetation, Blüte, Trocknung",
    )
    require(
        "orderedProfileNames().forEach" in profiles
        and "orderedProfileNames()[0] || null" in profiles,
        "Feste Reihenfolge gilt für Schaltflächen und sicheren Startwert",
    )
    require(
        all(
            f'.profile-btn[data-profile="{name}"]' in profiles
            for name in ("veg", "bloom", "dry")
        )
        and "linear-gradient" in profiles,
        "Profilauswahl verwendet die drei zugehörigen Phasenfarben",
    )

    hierarchy = (
        dashboard.find('id="climate-mode"'),
        dashboard.find('id="profile-card"'),
        dashboard.find('id="profile-badge"'),
        dashboard.find("Klima &amp; Grenzwerte"),
    )
    require(
        all(position >= 0 for position in hierarchy)
        and list(hierarchy) == sorted(hierarchy),
        "Stationskopf zeigt Tag/Nacht vor Profilkarte, Wachstumsphase und Zielseite",
    )
    require(
        'safeText("profile-phase", state.profile' in dashboard
        and "PROFILE_LABELS[state.active_profile]" in dashboard
        and 'veg: "🌱"' in dashboard
        and 'bloom: "🌸"' in dashboard
        and 'dry: "🍂"' in dashboard,
        "Klimamodus und aktive Phase werden unabhängig aus dem State gerendert",
    )
    require(
        'mode === "TAG" ? "☀️"' in dashboard
        and 'mode === "NACHT" ? "🌙"' in dashboard
        and 'class="header-climate-mode"' in dashboard,
        "Tag und Nacht besitzen einen eigenen Indikator im Stationskopf",
    )
    require(
        "background: linear-gradient(135deg, #fde047, #fb923c)" in dashboard
        and "background: linear-gradient(135deg, #0369a1, #4338ca)" in dashboard,
        "Tag- und Nachtverläufe bleiben kontrastreich lesbar",
    )

    phase_colors = {
        "veg": "34,197,94",
        "bloom": "167,139,250",
        "dry": "217,119,6",
    }
    require(
        all(
            f'body[data-growth-phase="{name}"]' in dashboard
            and f"--phase-accent-rgb: {rgb}" in dashboard
            for name, rgb in phase_colors.items()
        )
        and "document.body.dataset.growthPhase = activeProfile" in dashboard,
        "Dashboard-Thema folgt Grün, Lila oder Dunkelorange der aktiven Phase",
    )
    card_css = re.search(r"\.card\s*\{(?P<body>.*?)\n\}", dashboard, re.DOTALL)
    require(
        card_css is not None
        and "linear-gradient" in card_css.group("body")
        and "border: 1px solid rgba(var(--phase-accent-rgb),.34)" in card_css.group("body")
        and "0 0 18px rgba(var(--phase-accent-rgb),.07)" in card_css.group("body"),
        "Alle Dashboard-Kacheln erhalten einen dezenten Phasenrand und Verlauf",
    )
    require(
        all(
            marker in dashboard
            for marker in (
                ".device.on { background: linear-gradient",
                ".device.off { background: linear-gradient",
                ".device.disabled { background: linear-gradient",
                ".device.safety { background: linear-gradient",
            )
        ),
        "Semantische Gerätezustandsfarben bleiben unverändert erhalten",
    )
    require(
        "grow_control_tent_settings" in dashboard
        and 'id="profile-card"' in dashboard,
        "Neu gestaltete Profilkarte öffnet weiterhin Klima & Grenzwerte",
    )

    print("✅ Growstar 3.15.11 / DASHBOARD.PROFILE.1 vollständig geprüft")


if __name__ == "__main__":
    main()
