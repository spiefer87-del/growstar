import time

from core.hardware.manager import manager


def hardware_loop():

    while True:

        for gateway in manager.gateways_list():

            try:

                gateway.refresh()

            except Exception as e:

                print(e)

        time.sleep(30)
