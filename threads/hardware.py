import time

from core.hardware.manager import manager
from services.hardware import hardware


HARDWARE_REFRESH_INTERVAL = 30


def hardware_loop():
    print("Hardware Thread gestartet")

    while True:
        try:
            hardware.refresh()

            # Der normale Hardware-Poll hält gleichzeitig die persistente
            # Recovery-Kopie aktuell. Merge schützt gegen temporäre Scanner-
            # Clears während einer Discovery.
            try:
                manager.save_inventory(merge=True)
            except Exception as exc:
                print("⚠️ Hardware-Inventar konnte nicht gespeichert werden:", exc)

        except Exception as exc:
            # Ein einzelner Refresh-Fehler darf den Hardware-Thread nicht
            # dauerhaft beenden. Auto-Recovery versucht parallel weiter.
            print("⚠️ Hardware Refresh Fehler:", exc)

        time.sleep(HARDWARE_REFRESH_INTERVAL)
