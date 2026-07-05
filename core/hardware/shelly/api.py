import requests


class ShellyAPI:

    def __init__(self, ip):

        self.base = f"http://{ip}/rpc"

    def call(self, method, params=None):

        try:
    
            response = requests.post(
                f"{self.base}/{method}",
                json=params or {},
                timeout=5
            )
    
            print("RPC:", method)
            print("Status:", response.status_code)
            print("Antwort:", response.text)
    
            response.raise_for_status()
    
            return response.json()
    
        except Exception as e:
    
            print("RPC Fehler:", e)
    
            return None


    def list_methods(self):

        return self.call(
            "Shelly.ListMethods"
        )
