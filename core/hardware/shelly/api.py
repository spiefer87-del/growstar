import requests


class ShellyAPI:

    def __init__(self, ip):

        self.base = f"http://{ip}/rpc"

    def call(self, method, params=None, timeout=3):

        url = f"{self.base}/{method}"

        try:

            r = requests.post(
                url,
                json=params or {},
                timeout=timeout
            )

            r.raise_for_status()

            return r.json()

        except Exception as e:

            print(f"RPC Fehler: {e}")

            return None
