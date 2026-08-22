import time

from core.hardware.manager import manager
from services.actuator_health import poll_assigned_actuators
from services.hardware import hardware
from services.spiderfarmer import sync_sensor_sources


HARDWARE_REFRESH_INTERVAL = 30


def hardware_loop():
    print("Hardware Thread gestartet")

    while True:
        try:
            hardware.refresh()

            # Phase SF.2A:
            # Der bereits von der separaten read-only Spider-Farmer-Bridge
            # normalisierte GGS-Umweltsensor wird als controller-weite
            # Growstar-Sensorquelle veröffentlicht. Die Funktion sendet keine
            # Netzwerk-/MQTT-Befehle und aktualisiert eine Quelle nur, wenn der
            # Bridge-Zeitstempel tatsächlich fortgeschritten ist.
            try:
                sf_result = sync_sensor_sources()
                if sf_result.get("published"):
                    print(
                        "🌿 Spider Farmer Sensorquelle aktualisiert: "
                        f"{len(sf_result.get('published') or [])}"
                    )
            except Exception as exc:
                print("⚠️ Spider-Farmer-State-Sync Fehler:", exc)

            # Phase 4G: Ein zentraler read-only Poll prüft alle tatsächlich
            # zugeordneten Shelly-Aktor-Endpunkte über alle lokalen Stationen.
            # Der Regelkreis und der Watchdog selbst senden dadurch keine
            # zusätzlichen Reachability-Anfragen.
            try:
                result = poll_assigned_actuators()
                if result.get("endpoints"):
                    print(
                        "🔌 Aktor-Health: "
                        f"{result.get('online', 0)}/{result.get('endpoints', 0)} erreichbar"
                    )
            except Exception as exc:
                print("⚠️ Aktor-Health-Poll Fehler:", exc)

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
