#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Bitte als root ausführen:"
    echo "sudo bash install/install_shelly_ble_rpc.sh"
    exit 1
fi

echo "Growstar Phase 4W.5 – Shelly BLE-RPC-Abhängigkeit"

if /usr/bin/python3 -c 'import bleak' >/dev/null 2>&1; then
    echo "✅ python3-bleak ist bereits installiert"
else
    apt-get update
    apt-get install -y python3-bleak
    echo "✅ python3-bleak installiert"
fi

/usr/bin/python3 - <<'PY'
import bleak
print("✅ Bleak ist über /usr/bin/python3 importierbar")
PY

echo "✅ Growstar/Gunicorn bleibt unprivilegiert"
echo "✅ Keine neuen sudoers-Regeln installiert"
