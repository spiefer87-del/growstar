#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="growstar-spiderfarmer-network.service"
SERVICE_DEST="/etc/systemd/system/${SERVICE_NAME}"
HELPER_DEST="/usr/local/libexec/growstar-spiderfarmer-network"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
TEMPLATE="${SCRIPT_DIR}/growstar-spiderfarmer-network.service.in"
HELPER_SOURCE="${SCRIPT_DIR}/growstar_spiderfarmer_network.py"
NETWORK_DIR="${PROJECT_DIR}/instance/spiderfarmer_network"
CONFIG_PATH="${NETWORK_DIR}/config.json"
STATE_PATH="${NETWORK_DIR}/state.json"

if [[ "${EUID}" -ne 0 ]]; then
    echo "❌ Bitte mit sudo ausführen."
    exit 1
fi

for command in systemctl nmcli ip nft; do
    command -v "${command}" >/dev/null || {
        echo "❌ Benötigtes Programm fehlt: ${command}"
        exit 1
    }
done

[[ -x /usr/bin/python3 ]] || { echo "❌ /usr/bin/python3 fehlt"; exit 1; }
[[ -f "${TEMPLATE}" ]] || { echo "❌ Service-Vorlage fehlt"; exit 1; }
[[ -f "${HELPER_SOURCE}" ]] || { echo "❌ Netzwerk-Helper fehlt"; exit 1; }

install -d -o root -g root -m 0755 /usr/local/libexec
install -d -o root -g root -m 0700 "${NETWORK_DIR}"
install -o root -g root -m 0755 "${HELPER_SOURCE}" "${HELPER_DEST}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
    /usr/bin/python3 - "${CONFIG_PATH}" <<'PY'
from pathlib import Path
import json
import os
import secrets
import string
import sys
import tempfile
import time

path = Path(sys.argv[1])
alphabet = string.ascii_letters + string.digits
password = "".join(secrets.choice(alphabet) for _ in range(20))
config = {
    "schema": 1,
    "ssid": "Growstar-SF",
    "password": password,
    "wifi_device": "wlan0",
    "uplink_device": "eth0",
    "connection_name": "Growstar-SF",
    "address": "10.42.77.1/24",
    "channel": 6,
    "bridge_port": 18883,
    "upstream_host": "sf.mqtt.spider-farmer.com",
    "upstream_port": 8883,
    "created_at": int(time.time()),
}
path.parent.mkdir(parents=True, exist_ok=True)
fd, tmp = tempfile.mkstemp(prefix=".sf-network-", suffix=".tmp", dir=str(path.parent), text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
PY
else
    chmod 0600 "${CONFIG_PATH}"
    chown root:root "${CONFIG_PATH}"
fi

TMP_SERVICE="$(mktemp)"
trap 'rm -f "${TMP_SERVICE}"' EXIT

/usr/bin/python3 - "${TEMPLATE}" "${TMP_SERVICE}" \
    "${PROJECT_DIR}" "${NETWORK_DIR}" "${CONFIG_PATH}" "${STATE_PATH}" <<'PY'
from pathlib import Path
import sys

template, target, project, network_dir, config_path, state_path = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")
for key, value in {
    "__GROWSTAR_DIR__": project,
    "__SF_NETWORK_DIR__": network_dir,
    "__SF_NETWORK_CONFIG__": config_path,
    "__SF_NETWORK_STATE__": state_path,
}.items():
    if "\n" in value or "\r" in value:
        raise SystemExit(f"Ungültiger Wert für {key}")
    text = text.replace(key, value)
if "__" in text:
    unresolved = [line for line in text.splitlines() if "__" in line]
    if unresolved:
        raise SystemExit("Nicht ersetzter Platzhalter: " + " | ".join(unresolved))
Path(target).write_text(text, encoding="utf-8")
PY

install -o root -g root -m 0644 "${TMP_SERVICE}" "${SERVICE_DEST}"
systemctl daemon-reload

if command -v systemd-analyze >/dev/null; then
    systemd-analyze verify "${SERVICE_DEST}" >/dev/null
fi

echo "🔎 Prüfe Ethernet-Uplink, AP-Fähigkeit und Shelly-Provisionierungsziel ..."
if ! "${HELPER_DEST}" preflight \
    --config "${CONFIG_PATH}" \
    --state "${STATE_PATH}" \
    --project-dir "${PROJECT_DIR}"; then
    echo
    echo "❌ Preflight fehlgeschlagen. Es wurde kein Access Point aktiviert."
    exit 1
fi

cat <<EOF

✅ Growstar Spider Farmer Netzwerkgrenze SF.1N installiert

Dienst:      ${SERVICE_NAME}
SSID:        Growstar-SF
AP-Netz:     10.42.77.0/24
WLAN:        wlan0 (2.4 GHz / WPA2)
Uplink:      eth0
Redirect:    nur wlan0 TCP/8883 -> lokaler Bridge-Port 18883
LAN-Schutz:  private IPv4-Ziele werden vom Spider-Farmer-WLAN blockiert

Wichtig:
- Der Access Point wurde NICHT gestartet.
- Das bestehende Heim-WLAN-Profil wurde NICHT gelöscht oder verändert.
- Das Geräte-Provisionierungsziel für Shellys bleibt separat gespeichert.
- Das zufällige Spider-Farmer-WLAN-Passwort wird nicht hier ausgegeben.

Nur lokal anzeigen, wenn du den GGS-Controller einrichtest (nicht fotografieren/senden):
  sudo ${HELPER_DEST} credentials --config ${CONFIG_PATH} --project-dir ${PROJECT_DIR}

Preflight erneut:
  sudo ${HELPER_DEST} preflight --config ${CONFIG_PATH} --state ${STATE_PATH} --project-dir ${PROJECT_DIR}

AP später bewusst starten:
  sudo systemctl start ${SERVICE_NAME}
EOF
