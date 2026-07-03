import requests


class ShellyAPI:

    def __init__(self, ip):

        self.ip = ip

    def rpc(self, method, params=None, timeout=5):

        url = f"http://{self.ip}/rpc/{method}"

        try:

            if params:
                response = requests.post(
                    url,
                    json=params,
                    timeout=timeout
                )
            else:
                response = requests.get(
                    url,
                    timeout=timeout
                )

            response.raise_for_status()

            return response.json()

        except Exception as e:

            print(f"[Shelly] {self.ip}: {e}")

            return None

    def device_info(self):

        return self.rpc("Shelly.GetDeviceInfo")

    def config(self):

        return self.rpc("Shelly.GetConfig")

    def status(self):

        return self.rpc("Shelly.GetStatus")
