#!/usr/bin/env bash
set -euo pipefail
RULE_DEST="/etc/polkit-1/rules.d/49-growstar-network.rules"
if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen: sudo bash install/remove_network_permissions.sh"
    exit 1
fi
rm -f "${RULE_DEST}"
echo "✅ Growstar-NetworkManager-Polkit-Regel entfernt."
