#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="growstar.service"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
TEMPLATE="${SCRIPT_DIR}/growstar.service.in"
START_NOW=0

if [[ "${1:-}" == "--start" ]]; then
    START_NOW=1
elif [[ $# -gt 0 ]]; then
    echo "❌ Unbekannte Option: $1"
    echo "   Verwendung: sudo bash install/install_growstar_service.sh [--start]"
    exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen."
    exit 1
fi

command -v systemctl >/dev/null || { echo "❌ systemctl fehlt"; exit 1; }
command -v python3 >/dev/null || { echo "❌ python3 fehlt"; exit 1; }
[[ -f "${TEMPLATE}" ]] || { echo "❌ Service-Vorlage fehlt"; exit 1; }
[[ -f "${PROJECT_DIR}/app.py" ]] || { echo "❌ app.py fehlt"; exit 1; }
[[ -f "${PROJECT_DIR}/gunicorn.conf.py" ]] || { echo "❌ gunicorn.conf.py fehlt"; exit 1; }

SERVICE_USER="${GROWSTAR_SERVICE_USER:-$(stat -c '%U' "${PROJECT_DIR}")}" 

if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
    echo "❌ Growstar darf nicht als root laufen."
    echo "   Setze bei Bedarf GROWSTAR_SERVICE_USER auf einen vorhandenen Benutzer."
    exit 1
fi

id "${SERVICE_USER}" >/dev/null 2>&1 || {
    echo "❌ Dienstbenutzer existiert nicht: ${SERVICE_USER}"
    exit 1
}

SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

if [[ -n "${GROWSTAR_GUNICORN:-}" ]]; then
    GUNICORN_BIN="${GROWSTAR_GUNICORN}"
else
    GUNICORN_BIN="$(command -v gunicorn || true)"
fi

if [[ -z "${GUNICORN_BIN}" || ! -x "${GUNICORN_BIN}" ]]; then
    echo "❌ gunicorn wurde nicht gefunden."
    echo "   Die Growstar-Basisinstallation muss Gunicorn bereits bereitstellen."
    exit 1
fi

TMP_SERVICE="$(mktemp)"
trap 'rm -f "${TMP_SERVICE}"' EXIT

python3 - "${TEMPLATE}" "${TMP_SERVICE}" \
    "${SERVICE_USER}" "${SERVICE_GROUP}" "${PROJECT_DIR}" "${GUNICORN_BIN}" <<'PY'
from pathlib import Path
import sys

template, target, user, group, project, gunicorn = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")
for key, value in {
    "__GROWSTAR_USER__": user,
    "__GROWSTAR_GROUP__": group,
    "__GROWSTAR_DIR__": project,
    "__GUNICORN_BIN__": gunicorn,
}.items():
    if "\n" in value or "\r" in value:
        raise SystemExit(f"Ungültiger Wert für {key}")
    text = text.replace(key, value)

if "__GROWSTAR_" in text:
    raise SystemExit("Nicht ersetzter Platzhalter in growstar.service")

Path(target).write_text(text, encoding="utf-8")
PY

if [[ -f "${SERVICE_DEST}" && ! -f "${SERVICE_DEST}.pre-installer-backup" ]]; then
    cp -a "${SERVICE_DEST}" "${SERVICE_DEST}.pre-installer-backup"
fi

install -o root -g root -m 0644 "${TMP_SERVICE}" "${SERVICE_DEST}"

# Bestehende Drop-ins wie growstar.service.d/override.conf bleiben bewusst
# unangetastet, damit z. B. GROWSTAR_HTTPS_ONLY auf bestehenden Installationen
# erhalten bleibt.
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null

if command -v systemd-analyze >/dev/null; then
    systemd-analyze verify "${SERVICE_DEST}" >/dev/null
fi

if [[ "${START_NOW}" -eq 1 ]]; then
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl restart "${SERVICE_NAME}"
    else
        systemctl start "${SERVICE_NAME}"
    fi
fi

cat <<EOF2
✅ Growstar-Systemdienst installiert

Dienst:        ${SERVICE_NAME}
Benutzer:      ${SERVICE_USER}
Gruppe:        ${SERVICE_GROUP}
Arbeitsordner: ${PROJECT_DIR}
Gunicorn:      ${GUNICORN_BIN}

Die Unit ist für den Systemstart aktiviert.
Bestehende Drop-ins wurden nicht verändert.
EOF2

if [[ "${START_NOW}" -eq 0 ]]; then
    echo
    echo "Der laufende Dienst wurde noch nicht neu gestartet."
    echo "Kontrollierter Neustart: sudo systemctl restart growstar"
fi
