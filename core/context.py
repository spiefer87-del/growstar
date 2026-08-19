# core/context.py

import threading

# ============================
# Locks
# ============================

state_lock = threading.Lock()
energy_lock = threading.Lock()

# Phase 4V.4:
# Alle regulären Shelly-HTTP-Zugriffe teilen sich diesen reentranten
# Transport-Lock. RLock ist absichtlich nötig, weil der bestehende
# Shelly-Background-Thread bereits einen äußeren Lock hält und darunter
# Funktionen wie get_shelly_relay_state()/switch_shelly() erneut eintreten.
shelly_lock = threading.RLock()

# ============================
# Energy
# ============================

energy_state = {}

last_energy_poll = 0
last_failsafe_poll = 0

# ============================
# MQTT
# ============================

MQTT_LAST_MSG = 0

# ============================
# Logging
# ============================

LOG_FILE = "logs/infolog.txt"
