#!/usr/bin/env bash
set -euo pipefail

SERVICE="growstar.service"
RULE_DEST="/etc/polkit-1/rules.d/49-growstar-network.rules"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RULE_TEMPLATE="${SCRIPT_DIR}/49-growstar-network.rules.in"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen: sudo bash install/install_network_permissions.sh"
    exit 1
fi

command -v systemctl >/dev/null || { echo "❌ systemctl fehlt"; exit 1; }
command -v nmcli >/dev/null || { echo "❌ nmcli fehlt"; exit 1; }
[[ -f "${RULE_TEMPLATE}" ]] || { echo "❌ Regelvorlage fehlt: ${RULE_TEMPLATE}"; exit 1; }

SERVICE_USER="$(systemctl show "${SERVICE}" -p User --value | tr -d '[:space:]')"

if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
    echo "❌ Der Growstar-Dienstbenutzer konnte nicht sicher ermittelt werden."
    exit 1
fi

if [[ ! "${SERVICE_USER}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    echo "❌ Unerwarteter Dienstbenutzer: ${SERVICE_USER}"
    exit 1
fi

install -d -m 0755 /etc/polkit-1/rules.d
sed "s/__GROWSTAR_SERVICE_USER__/${SERVICE_USER}/g" "${RULE_TEMPLATE}" > "${RULE_DEST}.tmp"
install -m 0644 "${RULE_DEST}.tmp" "${RULE_DEST}"
rm -f "${RULE_DEST}.tmp"

cat <<EOF
✅ Growstar-NetworkManager-Regel installiert
   Dienst: ${SERVICE}
   Benutzer: ${SERVICE_USER}
   Datei: ${RULE_DEST}

Freigegeben werden ausschließlich:
- NetworkManager network-control
- benutzereigene NetworkManager-Profile (settings.modify.own)
- geschützte WLAN-Hotspots (wifi.share.protected)

Polkit überwacht rules.d automatisch. Danach Growstar neu starten und
auf der Netzwerkseite "Aktualisieren" drücken.
EOF
