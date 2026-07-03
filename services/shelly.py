import requests

import core.state as state

from core.config import config
from core.actuators import (
    switch_shelly,
    get_shelly_relay_state,
)

from core.shelly.discovery import ShellyDiscovery

class ShellyService:

    def __init__(self):

        self.discovery = ShellyDiscovery()

    def add_gateway(self, ip):

        gateway = self.discovery.add(ip)

        if gateway:

            print(f"[Shelly] {gateway.model} gefunden")

        return gateway

    def gateways(self):

        return self.discovery.all()


FAILSAFE_DEVICES = [
    ("heating", "IP_HEATING", "RELAY_HEATING"),
    ("fan", "IP_FAN", "RELAY_FAN"),
    ("light", "IP_LIGHT", "RELAY_LIGHT"),
    ("vent", "IP_VENT", "RELAY_VENT"),
    # ("irrigation", "IP_IRRIGATION", "RELAY_IRRIGATION"),
    # ("humidifier", "IP_HUMIDIFIER", "RELAY_HUMIDIFIER"),
    # ("dehumidifier", "IP_DEHUMIDIFIER", "RELAY_DEHUMIDIFIER"),
    # ("light2", "IP_LIGHT2", "RELAY_LIGHT2"),
    # ("vent2", "IP_VENT2", "RELAY_VENT2"),
]

def run_failsafe():

    for device, ip_key, relay_key in FAILSAFE_DEVICES:
        failsafe_check(
            device,
            ip_key,
            relay_key
        )

def shelly_set(ip, relay, on):

    try:
        url = f"http://{ip}/relay/{relay}?turn={'on' if on else 'off'}"
        requests.get(url, timeout=3)
        return True

    except Exception as e:
        print(f"❌ Shelly SET Fehler {ip} R{relay}: {e}")
        return False

def failsafe_check(device, ip_key, relay_key):

    ip = config.get(ip_key)
    relay = config.get(relay_key)

    if not ip or relay is None:
        return

    should_on = state.live_state.get(device)

    if should_on is None:
        return

    actual = get_shelly_relay_state(ip, relay)

    if actual is None:
        print(f"🚨 FAILSAFE {device}: Shelly nicht erreichbar")
        return

    if actual != should_on:
        print(f"🛡️ FAILSAFE {device}: korrigiere Zustand")
        switch_shelly(ip, relay, should_on)

def sync_relay(name, ip, relay, state_var, live_key):

    if not ip or relay is None:

        setattr(state, state_var, None)
        state.live_state[live_key] = None
        return

    relay_state = get_shelly_relay_state(ip, relay)

    if relay_state is None:

        setattr(state, state_var, None)
        state.live_state[live_key] = None

        print(
            f"❌ {name}: KEINE VERBINDUNG "
            f"(IP {ip}, Relay {relay})"
        )

        return

    setattr(state, state_var, relay_state)
    state.live_state[live_key] = relay_state

    print(
        f"✅ {name}: "
        f"{'EIN' if relay_state else 'AUS'} "
        f"(IP {ip}, Relay {relay})"
    )


  
