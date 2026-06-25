# =========================================
# 🔌 GENERIC DEVICE CONTROL SYSTEM
# =========================================

def get_device_mode(device):
    modes = config.setdefault("DEVICE_MODES", {})
    return modes.get(device, "OFF")


def get_device_params(device):
    params = config.setdefault("DEVICE_PARAMS", {})
    return params.setdefault(device, {})
