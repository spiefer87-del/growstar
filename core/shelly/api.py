import requests


class ShellyAPI:
    def __init__(self, host, timeout=5):
        self.host = host
        self.timeout = timeout

    def call(self, method, params=None):
        url = f"http://{self.host}/rpc/{method}"

        try:
            if params:
                r = requests.post(url, json=params, timeout=self.timeout)
            else:
                r = requests.get(url, timeout=self.timeout)

            r.raise_for_status()
            return r.json()

        except requests.RequestException as e:
            print(f"[Shelly] RPC Fehler {self.host}: {e}")
            return None

    def get_device_info(self):
        return self.call("Shelly.GetDeviceInfo")

    def get_config(self):
        return self.call("Shelly.GetConfig")

    def get_status(self):
        return self.call("Shelly.GetStatus")
