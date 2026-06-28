# core/context.py

import threading

# ============================
# Locks
# ============================

state_lock = threading.Lock()
energy_lock = threading.Lock()
shelly_lock = threading.Lock()

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
