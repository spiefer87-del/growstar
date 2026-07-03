import requests


class ShellyAPI:

    def __init__(self, ip):
        self.ip = ip

    def rpc(self, method, params=None, timeout=5):

        url = f"http://{self.ip}/rpc/{method}"

        try:

            if params:
                r = requests.post(url, json=params, timeout=timeout)
            else:
                r = requests.get(url, timeout=timeout)

            r.raise_for_status()

            return r.json()

        except Exception as e:

            print(f"Shelly RPC Fehler ({self.ip}): {e}")

            return None
