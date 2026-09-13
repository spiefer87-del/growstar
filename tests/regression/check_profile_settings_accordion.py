#!/usr/bin/env python3
"""Regression für kompakte Profil- und Klima-Einstellungsseiten."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    profiles = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")
    settings = (ROOT / "templates/settings.html").read_text(encoding="utf-8")

    require(
        'data-profile-tab="classic"' in profiles
        and 'data-profile-tab="vpd"' in profiles
        and 'selectProfileSection("classic")' in profiles,
        "Profilverwaltung trennt klassische und VPD-Regelung in zwei Reiter",
    )
    require(
        profiles.count("data-profile-accordion") >= 6
        and "setupProfileAccordions()" in profiles
        and "closeProfileAccordions(opening ? card : null)" in profiles,
        "Profilbereiche starten als Klappmenüs und lassen nur einen Bereich offen",
    )
    require(
        settings.count("data-settings-accordion") >= 6
        and "setupSettingsAccordions()" in settings
        and "closeSettingsAccordions(opening ? card : null)" in settings,
        "Klima und Grenzwerte verwendet dieselbe kompakte Klappnavigation",
    )
    require(
        "settings-actions{margin-top:16px" in settings
        and ".settings-actions{position:sticky" not in settings,
        "Speicherbereich ist nicht mehr dauerhaft am Bildschirm fixiert",
    )
    require(
        'id="profile-help-modal"' in profiles
        and 'id="settings-help-modal"' in settings
        and profiles.count("help-copy") >= 5
        and settings.count("help-copy") >= 8,
        "Längere Hilfetexte öffnen sich über kompakte Info-Dialoge",
    )
    require(
        "DAY_TEMP" in profiles
        and "VPD_TARGET_DAY" in profiles
        and "LIGHT_SUN_ENABLED" in profiles
        and "DAY_TEMP" in settings
        and "VPD_CONTROL_MODE" in settings
        and "LIGHT_SUN_ENABLED" in settings,
        "Bestehende Klima-, VPD- und Sonnenverlauf-Felder bleiben erhalten",
    )
    for page_name, source in (("Profilverwaltung", profiles), ("Klima & Grenzwerte", settings)):
        require(
            source.count('id="RAMP_ENABLED"') == 1
            and source.count('id="RAMP_DURATION_MIN"') == 1,
            f"{page_name} enthält die Rampenfelder genau einmal",
        )
        require(
            source.index('data-accordion-title="💧 Luftfeuchtigkeit"')
            < source.index('data-accordion-title="⏱️ Temperaturrampe"')
            < source.index('data-accordion-title="☀️ Sonnenverlauf"'),
            f"{page_name} ordnet die Temperaturrampe zwischen Luftfeuchtigkeit und Sonnenverlauf ein",
        )
    require(
        'data-profile-panel="shared" data-accordion-title="⏱️ Temperaturrampe"' in profiles,
        "Profilrampe bleibt in klassischer und VPD-Ansicht erreichbar",
    )
    require(
        'id="vpd-ramp-settings" class="card" data-settings-accordion' in settings
        and 'class="card vpd-ramp-settings"' not in settings,
        "Temperaturrampe verwendet auf Klima & Grenzwerte das normale Kategorie-Layout",
    )
    require(
        'rampHeading.querySelector(".accordion-title")' in settings,
        "Dynamische Rampenbezeichnung erhält Pfeil und Bedienbarkeit des Klappmenüs",
    )

    print("✅ UI.PROFILE-ACCORDION.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
