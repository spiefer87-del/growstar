# services/shelly.py

import requests

from core.runtime import resolve_runtime
from core.actuators import switch_shelly, get_shelly_relay_state


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


def run_failsafe(runtime=None):
    rt = resolve_runtime(runtime)

    # Shadow-Runtimes dürfen niemals physische Shellys prüfen/korrigieren.
    if not rt.control_enabled:
        return

    for device, ip_key, relay_key in FAILSAFE_DEVICES:
        failsafe_check(
            device,
            ip_key,
            relay_key,
            runtime=rt,
        )


def shelly_set(ip, relay, on):
    try:
        url = f"http://{ip}/relay/{relay}?turn={'on' if on else 'off'}"
        requests.get(url, timeout=3)
        return True
    except Exception as exc:
        print(f"❌ Shelly SET Fehler {ip} R{relay}: {exc}")
        return False


def failsafe_check(device, ip_key, relay_key, runtime=None):
    rt = resolve_runtime(runtime)
    if not rt.control_enabled:
        return

    cfg = rt.config
    st = rt.state

    ip = cfg.get(ip_key)
    relay = cfg.get(relay_key)

    if not ip or relay is None:
        return

    should_on = st.live_state.get(device)
    if should_on is None:
        return

    actual = get_shelly_relay_state(ip, relay)

    if actual is None:
        print(f"🚨 [{rt.tent_id}] FAILSAFE {device}: Shelly nicht erreichbar")
        return

    if actual != should_on:
        print(f"🛡️ [{rt.tent_id}] FAILSAFE {device}: korrigiere Zustand")
        switch_shelly(ip, relay, should_on)


def sync_relay(
    name,
    ip,
    relay,
    state_var,
    live_key,
    runtime=None,
):
    rt = resolve_runtime(runtime)
    st = rt.state

    if not rt.control_enabled:
        return

    if not ip or relay is None:
        setattr(st, state_var, None)
        st.live_state[live_key] = None
        return

    relay_state = get_shelly_relay_state(ip, relay)

    if relay_state is None:
        setattr(st, state_var, None)
        st.live_state[live_key] = None

        print(
            f"❌ [{rt.tent_id}] {name}: KEINE VERBINDUNG "
            f"(IP {ip}, Relay {relay})"
        )
        return

    setattr(st, state_var, relay_state)
    st.live_state[live_key] = relay_state

    print(
        f"✅ [{rt.tent_id}] {name}: "
        f"{'EIN' if relay_state else 'AUS'} "
        f"(IP {ip}, Relay {relay})"
    )
