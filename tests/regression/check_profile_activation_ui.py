#!/usr/bin/env python3
"""Regression für sichtbare und serverbestätigte Profilaktivierung."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print("✅", message)


def main():
    template = (ROOT / "templates/profiles.html").read_text(encoding="utf-8")

    selection = template.index('id="profile-selection-card"')
    activation = template.index('id="activate-profile-button"')
    editor = template.index("Regelung bearbeiten")
    require(
        template.count('id="activate-profile-button"') == 1
        and selection < activation < editor,
        "Aktivierungsbutton steht einmalig direkt bei Auswahl und aktivem Profil",
    )
    require(
        template.count('id="profile-feedback"') == 1
        and template.index('id="profile-feedback"') < editor
        and 'aria-live="polite"' in template,
        "Rückmeldung ist ohne Scrollen sichtbar und wird barrierearm angekündigt",
    )
    require(
        "Ungespeicherte Änderungen an ${profileLabel(selectedProfile)} verwerfen" in template
        and "Profilwechsel abgebrochen. Der aktuelle Entwurf bleibt erhalten." in template
        and "dirty = false;" in template,
        "Eine offene Bearbeitung blockiert die Profilauswahl nicht mehr kommentarlos",
    )
    require(
        "const targetProfile = selectedProfile;" in template
        and "payload.active_profile !== targetProfile" in template
        and "activeProfile = payload.active_profile;" in template,
        "Die Oberfläche meldet Erfolg nur für das vom Backend bestätigte aktive Profil",
    )
    require(
        "PROFILE_ACTIVATE_URL(targetProfile)" in template
        and "renderProfileButtons();" in template
        and 'id="activate-profile-button" type="button" class="activate-button" disabled' in template
        and 'el("activate-profile-button")?.addEventListener("click",activateProfile);' in template,
        "Aktivierung verwendet einen zuverlässig registrierten Event-Listener",
    )
    require(
        "requestInFlight || unavailable || dirty;" in template
        and "requestInFlight || unavailable || dirty || activationBlocked" not in template
        and 'id="profile-controller-link"' in template
        and "grow_control_connections" in template,
        "Fehlende Licht-Zuordnung bleibt erklärbar anklickbar und führt direkt zur Lösung",
    )
    require(
        "verwendet den Sonnenverlauf und benötigt vor der Aktivierung" in template
        and "if(savedProfileNeedsLightController())" in template,
        "Die Profilauswahl überschreibt den echten Sperrgrund nicht mehr mit einer Erfolgsmeldung",
    )
    activation_function = template[
        template.index("async function activateProfile()"):
        template.index("async function loadProfiles()")
    ]
    require(
        "confirm(" not in activation_function
        and "Profil wird aktiviert" not in activation_function
        and "wird aktiviert …" in activation_function,
        "Der bewusste Auswahl-plus-Aktivieren-Weg startet ohne blockierenden Browserdialog",
    )

    print("✅ PROFILE.ACTIVATION-UI.1 vollständig erfolgreich")


if __name__ == "__main__":
    main()
