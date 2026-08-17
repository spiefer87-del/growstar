# Gunicorn-Konfiguration für Growstar
# WICHTIG: workers muss 1 bleiben, da jeder Worker sonst eine eigene
# Hardware-, MQTT-, Shelly- und Regelungsinstanz starten würde.

# Lokal bleibt Gunicorn über 127.0.0.1:8000 für Caddy erreichbar.
# Port 8001 lauscht netzwerkneutral auf allen Interfaces. Dadurch startet
# Growstar auch dann, wenn sich die LAN-/WLAN-IP nach einem Netzwerkwechsel
# oder bei einer späteren Erstinbetriebnahme geändert hat.
bind = [
    "127.0.0.1:8000",
    "0.0.0.0:8001",
]

workers = 1
worker_class = "gthread"
threads = 4

# Kein Preload: Hardware und Hintergrundthreads dürfen nicht im Masterprozess
# vor dem Fork gestartet werden.
preload_app = False

# Für langsamere lokale Geräte/API-Aufrufe etwas großzügiger.
timeout = 120
graceful_timeout = 30
keepalive = 5

# Regelmäßiges Worker-Recycling bleibt deaktiviert, damit die Regelung nicht
# ohne Grund neu gestartet wird.
max_requests = 0

accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = "info"


def post_worker_init(worker):
    """Wird ausgeführt, nachdem genau ein Worker die Flask-App geladen hat."""
    worker.log.info("Starte Growstar-Hintergrunddienste")

    from app import start_backend

    start_backend()


def worker_exit(server, worker):
    """Geordneter Hardware-Shutdown beim Beenden des Workers."""
    worker.log.info("Beende Growstar-Hintergrunddienste")

    from app import shutdown_backend

    shutdown_backend()


def worker_abort(worker):
    """Not-Aus, falls Gunicorn den Worker wegen eines Timeouts beendet."""
    worker.log.error("Growstar-Worker wurde abgebrochen")

    from app import shutdown_backend

    shutdown_backend()
