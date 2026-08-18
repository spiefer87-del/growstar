#!/usr/bin/env bash
set -euo pipefail

SERVICE="growstar.service"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen:"
    echo "   sudo bash install/activate_phase4t_without_old_shutdown.sh"
    exit 1
fi

command -v systemctl >/dev/null || { echo "❌ systemctl fehlt"; exit 1; }

PROJECT_DIR="$(systemctl show "${SERVICE}" -p WorkingDirectory --value)"
SERVICE_USER="$(systemctl show "${SERVICE}" -p User --value)"

if [[ -z "${PROJECT_DIR}" || ! -d "${PROJECT_DIR}" ]]; then
    echo "❌ Growstar-Arbeitsverzeichnis konnte nicht ermittelt werden"
    exit 1
fi

if [[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]]; then
    echo "❌ Growstar-Dienstbenutzer konnte nicht sicher ermittelt werden"
    exit 1
fi

PREPARE="${PROJECT_DIR}/tools/prepare_phase4t_restart.py"
[[ -f "${PREPARE}" ]] || { echo "❌ Vorbereitungsskript fehlt: ${PREPARE}"; exit 1; }

echo "===== 1/4 GROWSTAR KURZ EINFRIEREN ====="
# SIGSTOP führt keinen Python-/Gunicorn-Shutdown aus. Damit kann die alte
# 3.7.8-Logik während der Policy-Vorbereitung keine Relais mehr zurückschalten.
systemctl kill --kill-whom=all --signal=SIGSTOP "${SERVICE}"

resume_old_service() {
    echo "⚠️ Vorbereitung fehlgeschlagen – alter Growstar-Prozess wird fortgesetzt"
    systemctl kill --kill-whom=all --signal=SIGCONT "${SERVICE}" 2>/dev/null || true
}
trap resume_old_service ERR

echo "===== 2/4 NEUE RESTART-POLICY PHYSISCH VORBEREITEN ====="
(
    cd "${PROJECT_DIR}"
    sudo -u "${SERVICE_USER}" python3 "${PREPARE}"
)

echo "===== 3/4 ALTEN WORKER OHNE ALTEN AEXIT-SHUTDOWN BEENDEN ====="
# Einmalig SIGKILL: Die alte Version darf jetzt gerade NICHT ihren historischen
# "alle Aktoren AUS"-Handler ausführen. systemd Restart=always startet danach
# die neue Version.
systemctl kill --kill-whom=all --signal=SIGKILL "${SERVICE}"
trap - ERR

echo "===== 4/4 AUF NEUEN GROWSTAR WARTEN ====="
for _ in $(seq 1 20); do
    sleep 1
    if systemctl is-active --quiet "${SERVICE}"; then
        echo "✅ Growstar läuft mit der neuen Version"
        systemctl status "${SERVICE}" --no-pager -l | head -25
        exit 0
    fi
done

echo "⚠️ Automatischer Restart wurde nicht rechtzeitig aktiv; starte Dienst jetzt"
systemctl start "${SERVICE}"
sleep 4
systemctl status "${SERVICE}" --no-pager -l | head -25
