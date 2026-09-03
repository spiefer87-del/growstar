"""Fast, read-only synchronization of Spider Farmer sensor samples."""

import time

from services.spiderfarmer import sync_sensor_sources


SPIDERFARMER_SYNC_INTERVAL = 2.0


def sync_spiderfarmer_sensor_sources_once():
    """Publish new bridge samples without touching transport or assignments."""

    result = sync_sensor_sources()
    if result.get("published"):
        print(
            "🌿 Spider Farmer Sensorquelle aktualisiert: "
            f"{len(result.get('published') or [])}"
        )
    return result


def spiderfarmer_sensor_loop():
    """Observe the bridge state independently from the slow hardware scan."""

    print("🌿 Spider Farmer Sensor-Sync gestartet")

    while True:
        try:
            sync_spiderfarmer_sensor_sources_once()
        except Exception as exc:
            # Eine beschädigte oder gerade atomar ausgetauschte State-Datei darf
            # den Thread nicht beenden. Der nächste kurze Zyklus versucht erneut.
            print("⚠️ Spider-Farmer-State-Sync Fehler:", exc)

        time.sleep(SPIDERFARMER_SYNC_INTERVAL)
