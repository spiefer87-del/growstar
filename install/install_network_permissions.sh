#!/usr/bin/env bash
set -euo pipefail

SERVICE="growstar.service"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HELPER_SOURCE="${SCRIPT_DIR}/growstar_network_helper.py"
HELPER_DEST="/usr/local/libexec/growstar-network-helper"
SUDOERS_DEST="/etc/sudoers.d/growstar-network"
OLD_POLKIT_RULE="/etc/polkit-1/rules.d/49-growstar-network.rules"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen: sudo bash install/install_network_permissions.sh"
    exit 1
fi

command -v systemctl >/dev/null || { echo "❌ systemctl fehlt"; exit 1; }
command -v nmcli >/dev/null || { echo "❌ nmcli fehlt"; exit 1; }
command -v sudo >/dev/null || { echo "❌ sudo fehlt"; exit 1; }
command -v visudo >/dev/null || { echo "❌ visudo fehlt"; exit 1; }
[[ -f "${HELPER_SOURCE}" ]] || { echo "❌ Netzwerk-Helper fehlt: ${HELPER_SOURCE}"; exit 1; }

SERVICE_USER="$(systemctl show "${SERVICE}" -p User --value | tr -d '[:space:]')"

if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
    echo "❌ Der Growstar-Dienstbenutzer konnte nicht sicher ermittelt werden."
    exit 1
fi

if [[ ! "${SERVICE_USER}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    echo "❌ Unerwarteter Dienstbenutzer: ${SERVICE_USER}"
    exit 1
fi

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 "${HELPER_SOURCE}" "${HELPER_DEST}"

install -d -o root -g root -m 0750 /etc/sudoers.d

TMP_SUDOERS="$(mktemp)"
trap 'rm -f "${TMP_SUDOERS}"' EXIT

printf '%s ALL=(root) NOPASSWD: %s\n' "${SERVICE_USER}" "${HELPER_DEST}" > "${TMP_SUDOERS}"

visudo -cf "${TMP_SUDOERS}" >/dev/null
install -o root -g root -m 0440 "${TMP_SUDOERS}" "${SUDOERS_DEST}"

# Phase 4S.3 verwendete eine Polkit-Regel. Der neue Helper ersetzt diesen
# Mechanismus vollständig, damit der Webprozess nicht von Polkit-Subject-
# Erkennung abhängt.
rm -f "${OLD_POLKIT_RULE}"

cat <<EOF
✅ Growstar-Netzwerk-Helper installiert

Dienst:       ${SERVICE}
Benutzer:     ${SERVICE_USER}
Helper:       ${HELPER_DEST}
sudoers:      ${SUDOERS_DEST}

Sicherheitsmodell:
- Flask/Gunicorn bleibt unprivilegiert.
- sudo darf nur den root-eigenen Growstar-Netzwerk-Helper starten.
- Der Helper verweigert Aufrufe außerhalb von growstar.service.
- Der Helper akzeptiert nur fest implementierte Netzwerk-Aktionen.
- WLAN-Passwörter werden weiterhin nicht als Prozessargument übergeben.
- Die alte Phase-4S.3-Polkit-Regel wurde entfernt.

Danach Growstar neu starten.
EOF
