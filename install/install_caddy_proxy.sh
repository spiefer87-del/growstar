#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TEMPLATE="${SCRIPT_DIR}/Caddyfile.growstar.in"
CADDY_DIR="/etc/caddy"
CADDYFILE="${CADDY_DIR}/Caddyfile"
FIRST_BACKUP="${CADDYFILE}.pre-growstar-anyhost-backup"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen."
    exit 1
fi

CADDY_BIN="$(command -v caddy || true)"
if [[ -z "${CADDY_BIN}" || ! -x "${CADDY_BIN}" ]]; then
    echo "❌ Caddy ist nicht installiert."
    exit 1
fi

if [[ ! -f "${TEMPLATE}" ]]; then
    echo "❌ Growstar-Caddy-Vorlage fehlt: ${TEMPLATE}"
    exit 1
fi

install -d -o root -g root -m 0755 "${CADDY_DIR}"

TMP_NEW="$(mktemp)"
TMP_OLD="$(mktemp)"
HAD_OLD=0

cleanup() {
    rm -f "${TMP_NEW}" "${TMP_OLD}"
}
trap cleanup EXIT

install -o root -g root -m 0644 "${TEMPLATE}" "${TMP_NEW}"

echo "🔎 Prüfe neue Caddy-Konfiguration ..."
"${CADDY_BIN}" validate --config "${TMP_NEW}" >/dev/null

if [[ -f "${CADDYFILE}" ]]; then
    HAD_OLD=1
    cp -a "${CADDYFILE}" "${TMP_OLD}"

    if [[ ! -e "${FIRST_BACKUP}" ]]; then
        cp -a "${CADDYFILE}" "${FIRST_BACKUP}"
        chmod 0644 "${FIRST_BACKUP}" || true
    fi
fi

install -o root -g root -m 0644 "${TMP_NEW}" "${CADDYFILE}"

rollback() {
    echo "⚠️  Caddy-Reload fehlgeschlagen – vorherige Konfiguration wird wiederhergestellt."

    if [[ "${HAD_OLD}" -eq 1 ]]; then
        install -o root -g root -m 0644 "${TMP_OLD}" "${CADDYFILE}"
    else
        rm -f "${CADDYFILE}"
    fi

    if systemctl is-active --quiet caddy.service; then
        systemctl reload caddy.service >/dev/null 2>&1 || true
    fi
}

if systemctl is-active --quiet caddy.service; then
    if ! systemctl reload caddy.service; then
        rollback
        exit 1
    fi
else
    echo "ℹ️  caddy.service ist momentan nicht aktiv; Konfiguration wurde nur installiert."
fi

echo
echo "✅ Growstar-Caddy-Proxy aktualisiert"
echo
echo "Listener:     HTTP :80 auf allen Heimnetz-Adressen"
echo "Upstream:     127.0.0.1:8000"
echo "Konfiguration: ${CADDYFILE}"
if [[ -e "${FIRST_BACKUP}" ]]; then
    echo "Erst-Backup:  ${FIRST_BACKUP}"
fi
echo
echo "Damit ist Growstar nicht mehr an eine einzelne Raspberry-IP gebunden."
echo "Die Spider-Farmer-Firewall gibt Port 80 auf Growstar-SF weiterhin NICHT frei."
