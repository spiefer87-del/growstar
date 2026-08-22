#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="growstar-spiderfarmer.service"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
TEMPLATE="${SCRIPT_DIR}/growstar-spiderfarmer.service.in"
SOURCE_CERT_DIR="${PROJECT_DIR}/bridge/spiderfarmer/certs"
START_NOW=0

if [[ "${1:-}" == "--start" ]]; then
    START_NOW=1
elif [[ $# -gt 0 ]]; then
    echo "❌ Unbekannte Option: $1"
    echo "   Verwendung: sudo bash install/install_spiderfarmer_bridge.sh [--start]"
    exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen."
    exit 1
fi

command -v systemctl >/dev/null || { echo "❌ systemctl fehlt"; exit 1; }
[[ -x /usr/bin/python3 ]] || { echo "❌ /usr/bin/python3 fehlt"; exit 1; }
[[ -f "${TEMPLATE}" ]] || { echo "❌ Service-Vorlage fehlt"; exit 1; }
[[ -f "${PROJECT_DIR}/bridge/spiderfarmer/main.py" ]] || {
    echo "❌ Spider-Farmer-Bridge-Code fehlt"
    exit 1
}

SERVICE_USER="${GROWSTAR_SERVICE_USER:-$(stat -c '%U' "${PROJECT_DIR}")}"

if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
    echo "❌ Die Spider-Farmer-Bridge darf nicht als root laufen."
    exit 1
fi

id "${SERVICE_USER}" >/dev/null 2>&1 || {
    echo "❌ Dienstbenutzer existiert nicht: ${SERVICE_USER}"
    exit 1
}

SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"
STATE_DIR="${GROWSTAR_SF_STATE_DIR:-${PROJECT_DIR}/instance/spiderfarmer}"
CERT_DIR="${STATE_DIR}/certs"

install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0700 "${STATE_DIR}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0700 "${CERT_DIR}"

for cert in server.pem server_key.pem upstream_ca.pem; do
    [[ -f "${SOURCE_CERT_DIR}/${cert}" ]] || {
        echo "❌ Zertifikat fehlt: ${SOURCE_CERT_DIR}/${cert}"
        exit 1
    }
    install \
        -o "${SERVICE_USER}" \
        -g "${SERVICE_GROUP}" \
        -m 0600 \
        "${SOURCE_CERT_DIR}/${cert}" \
        "${CERT_DIR}/${cert}"
done

TMP_SERVICE="$(mktemp)"
trap 'rm -f "${TMP_SERVICE}"' EXIT

/usr/bin/python3 - "${TEMPLATE}" "${TMP_SERVICE}" \
    "${SERVICE_USER}" "${SERVICE_GROUP}" "${PROJECT_DIR}" \
    "${STATE_DIR}" "${CERT_DIR}" <<'PY'
from pathlib import Path
import sys

template, target, user, group, project, state_dir, cert_dir = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")

for key, value in {
    "__GROWSTAR_USER__": user,
    "__GROWSTAR_GROUP__": group,
    "__GROWSTAR_DIR__": project,
    "__SF_STATE_DIR__": state_dir,
    "__SF_CERT_DIR__": cert_dir,
}.items():
    if "\n" in value or "\r" in value:
        raise SystemExit(f"Ungültiger Wert für {key}")
    text = text.replace(key, value)

if "__" in text:
    unresolved = [
        line for line in text.splitlines()
        if "__" in line
    ]
    if unresolved:
        raise SystemExit(
            "Nicht ersetzter Platzhalter: " + " | ".join(unresolved)
        )

Path(target).write_text(text, encoding="utf-8")
PY

install -o root -g root -m 0644 "${TMP_SERVICE}" "${SERVICE_DEST}"
systemctl daemon-reload

if command -v systemd-analyze >/dev/null; then
    systemd-analyze verify "${SERVICE_DEST}" >/dev/null
fi

echo "🔎 Prüfe SF.1-Konfiguration ..."

sudo -u "${SERVICE_USER}" \
    env \
    GROWSTAR_SF_STATE_DIR="${STATE_DIR}" \
    GROWSTAR_SF_CERT_FILE="${CERT_DIR}/server.pem" \
    GROWSTAR_SF_KEY_FILE="${CERT_DIR}/server_key.pem" \
    GROWSTAR_SF_UPSTREAM_CA_FILE="${CERT_DIR}/upstream_ca.pem" \
    /usr/bin/python3 -m bridge.spiderfarmer.main --check

if [[ "${START_NOW}" -eq 1 ]]; then
    systemctl enable "${SERVICE_NAME}" >/dev/null
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl restart "${SERVICE_NAME}"
    else
        systemctl start "${SERVICE_NAME}"
    fi
fi

cat <<EOF2

✅ Growstar Spider Farmer SF.1 installiert

Dienst:       ${SERVICE_NAME}
Benutzer:     ${SERVICE_USER}
State:        ${STATE_DIR}
Listener:     TCP/TLS 18883
Upstream:     sf.mqtt.spider-farmer.com:8883
Modus:        READ-ONLY

Wichtig:
- Dieses Installationsskript selbst ändert KEIN NetworkManager-Profil.
- Es ändert KEIN DNS und KEIN Mosquitto.
- Die Netzwerkgrenze wird separat durch growstar-spiderfarmer-network.service verwaltet.
- Der Bridge-Dienst verlangt diese Netzwerkgrenze als systemd-Abhängigkeit.
EOF2

if [[ "${START_NOW}" -eq 0 ]]; then
    cat <<EOF2

Der Dienst wurde absichtlich NICHT aktiviert oder gestartet.
Zuerst die Netzwerkgrenze installieren und prüfen:
  sudo bash install/install_spiderfarmer_network.sh

Erst nach erfolgreichem AP-Test die Bridge starten:
  sudo systemctl start growstar-spiderfarmer.service
EOF2
fi
