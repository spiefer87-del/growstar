#!/usr/bin/env bash
set -euo pipefail

HELPER_DEST="/usr/local/libexec/growstar-network-helper"
SUDOERS_DEST="/etc/sudoers.d/growstar-network"
OLD_POLKIT_RULE="/etc/polkit-1/rules.d/49-growstar-network.rules"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen: sudo bash install/remove_network_permissions.sh"
    exit 1
fi

rm -f "${SUDOERS_DEST}"
rm -f "${HELPER_DEST}"
rm -f "${OLD_POLKIT_RULE}"

echo "✅ Growstar-Netzwerk-Helper, sudoers-Regel und alte Polkit-Regel entfernt."
