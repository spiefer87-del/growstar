"""Growstar Spider Farmer bridge.

Phase SF.1 is deliberately read-only from Growstar's point of view:
the proxy only relays the controller's existing TLS/MQTT traffic and records
diagnostics. It contains no command builder and injects no MQTT PUBLISH frames.
"""

PHASE = "SF.1"
