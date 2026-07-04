import requests


class ShellyAPI:

    def __init__(self, ip):

        self.ip = ip

        self.base = f"http://{ip}/rpc"

    def call(self, method, params=None, timeout=3):

        url = f"{self.base}/{method}"

        try:

            response = requests.post(
                url,
                json=params or {},
                timeout=timeout
            )

            response.raise_for_status()

            return response.json()

        except Exception as e:

            print(f"Shelly RPC Fehler {self.ip}: {e}")

            return None
