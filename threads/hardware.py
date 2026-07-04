import time

from services.hardware import hardware


def hardware_loop():

    print("Hardware Thread gestartet")

    while True:

        hardware.refresh()

        time.sleep(30)
