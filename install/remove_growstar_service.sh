#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="growstar.service"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen."
    exit 1
fi

systemctl disable --now "${SERVICE_NAME}" 2>/dev/null || true
rm -f "${SERVICE_DEST}"
systemctl daemon-reload

echo "✅ Growstar-Systemdienst entfernt."
echo "Hinweis: bestehende Drop-ins unter ${SERVICE_DEST}.d wurden nicht gelöscht."
