# Growstar current release nodes.
#
# New patches are added here at the top. Once this file becomes large enough,
# an older group can be rolled into another history module without changing
# core.release's public API.

CURRENT_RELEASES = (
    {
        "version": "3.11.7",
        "date": "2026-08-23",
        "phase": "SF.3B.1",
        "title": "Spider-Farmer Konfiguration über Bridge-Neustarts erhalten",
        "summary": (
            "Growstar trennt beim Spider-Farmer-Neustart jetzt bewusst zwischen "
            "flüchtigem Live-State und bereits beobachteter normalisierter "
            "Controller-Konfiguration. Live-Werte werden weiterhin ausschließlich "
            "aus frischem getDevSta-Traffic aufgebaut. Konfigurationswerte wie "
            "Run-Level, Standby-Level, Oszillation, Natural Wind und Zyklus bleiben "
            "dagegen über einen Bridge-Neustart erhalten, weil Spider Farmer "
            "setConfigField nicht zwingend nach jedem Reconnect erneut sendet."
        ),
        "changes": (
            "BridgeDiagnostics restauriert beim Start ausschließlich normalisierte config-Blöcke aus der privaten spiderfarmer_state.json.",
            "Persistierte live-Blöcke werden absichtlich nicht restauriert und last_seen wird auf None gesetzt, damit alte Messwerte niemals als frisch erscheinen.",
            "Controller-PID und Prefix dürfen zusammen mit der Config wiederhergestellt werden, ohne einen Online- oder Frischezustand vorzutäuschen.",
            "Neue getDevSta-Pakete füllen den Live-State nach dem Neustart wie bisher neu auf und lassen die restaurierte Config unangetastet.",
            "Neue setConfigField-Pakete aktualisieren die restaurierte Config weiterhin über den bestehenden normalisierten Deep-Merge.",
            "Nicht lesbare, ungültige oder nicht read-only markierte Persistenzdateien werden nicht vertraut; in diesem Fall startet Growstar mit einem leeren SF.2-State.",
            "Der Fix fügt keinen Spider-Farmer-Schreib-, MQTT-Publish- oder Netzwerkpfad hinzu.",
        ),
        "tests": (
            "check_spiderfarmer_state.py simuliert jetzt explizit einen Bridge-Neustart mit vorher beobachtetem Live- und Config-State.",
            "Die Regression verlangt, dass Live-State und last_seen nach dem Neustart leer beziehungsweise None sind.",
            "Run-Level 8, Standby-Level 2, Oszillation 5, Natural Wind und der 90/270-Sekunden-Zyklus müssen den Neustart dagegen vollständig überstehen.",
            "Frischer getDevSta-Traffic muss nach dem Neustart den Live-State neu befüllen, ohne die restaurierte Config zu löschen.",
            "Ein nicht-read-only Persistenz-State darf nicht übernommen werden.",
            "Statische Guards bestätigen weiterhin das Fehlen von Command- und Transportpfaden.",
        ),
    },
    {
        "version": "3.11.6",
        "date": "2026-08-22",
        "phase": "SF.3B",
        "title": "Spider-Farmer Controller-Realitätscheck",
        "summary": (
            "Growstar erhält einen strikt read-only Diagnose-Layer für den "
            "normalisierten Spider-Farmer-Gerätestand. Damit kann das in SF.3A "
            "eingeführte Geräte- und Konfigurationsmodell auf dem echten GGS-"
            "Controller kontrolliert werden, bevor irgendein Schreibpfad "
            "hinzukommt. Die Ausgabe ist bewusst kompakt und für die Nutzung "
            "über ein Mobiltelefon-Terminal geeignet."
        ),
        "changes": (
            "bridge/spiderfarmer/readout.py erzeugt aus services.spiderfarmer einen kompakten Controller-/Geräte-Readout ohne Raw-MQTT oder Command-Transport.",
            "Der Readout zeigt Controller-ID, PID, Online-Status, Zeitstempel, Device-Count, Capabilities und alle bereits normalisierten effective-Werte.",
            "Ventilator-Konfigurationen wie run_level, standby_level, oscillation_level, natural_wind und cycle werden im echten Controller-Readout sichtbar.",
            "Power-Strip-Kanäle werden einschließlich ihrer stabilen outlet:O*-IDs getrennt dargestellt.",
            "bridge/spiderfarmer/readout_cli.py stellt eine telefonfreundliche Textausgabe sowie optional JSON bereit.",
            "SF.3B öffnet keine Netzwerkverbindung, erzeugt kein MQTT-Paket, schreibt keinen Controller-State und führt keinen setConfigField-Befehl aus.",
        ),
        "tests": (
            "check_spiderfarmer_readout.py prüft einen vollständigen Testcontroller mit Sensor, Licht, Ventilator, Gebläse und zwei Outlet-Kanälen.",
            "Die Regression verlangt Run-Level 8, Standby-Level 2, Oszillation 5, Natural Wind und den 90/270-Sekunden-Zyklus im Readout.",
            "Controller-Lookup über PID sowie die telefonfreundliche Textausgabe werden geprüft.",
            "Statische Guards verbieten Socket-, MQTT-Publish-, writer.write- und setConfigField-Pfade im SF.3B-Layer.",
            "Bestehende Repository-, Release-Split-, SF.2A- und SF.3A-Regressionen bleiben zusätzlich auszuführen.",
        ),
    },
    {
        "version": "3.11.5",
        "date": "2026-08-22",
        "phase": "SF.3A",
        "title": "Spider-Farmer Geräte- und Konfigurationsmodell",
        "summary": (
            "Growstar bildet den bereits normalisierten Spider-Farmer-State jetzt "
            "als stabiles read-only Geräteinventar ab. Licht, Ventilator, Gebläse, "
            "optionale Klima-Geräte und Steckdosenkanäle erhalten eine gemeinsame "
            "Growstar-Darstellung aus Live-State und beobachteter Controller-"
            "Konfiguration. Der Ventilator stellt dabei unter anderem Run-Level, "
            "Standby-Level, Oszillation, Natural Wind und Zyklusparameter bereit. "
            "Es wird weiterhin kein Spider-Farmer-Schreibbefehl erzeugt oder gesendet."
        ),
        "changes": (
            "bridge/spiderfarmer/device_model.py führt ein reines read-only Projektionsmodell für Spider-Farmer-Geräte ein.",
            "Umweltsensor, Licht 1/2, Ventilator, Gebläse, Heizung, Luftbe-/entfeuchter und Power-Strip-Kanäle werden nur dann modelliert, wenn dafür bereits normalisierte Live- oder Config-Daten beobachtet wurden.",
            "Ventilator und Gebläse kombinieren Live-Werte für on/level/mode_type mit beobachteten Config-Werten für standby_level, run_level, oscillation_level, natural_wind, cycle und schedule.",
            "shakeLevel bleibt ausschließlich als normalisiertes oscillation_level sichtbar; SF.3A führt noch keinen Encoder und keinen setConfigField-Schreibpfad ein.",
            "services/spiderfarmer.py ergänzt Controller um devices/device_count sowie list_devices() und device() für zukünftige Growstar-API/UI-Nutzung.",
            "public_snapshot() meldet SF.3A als Projektionsphase und hält gleichzeitig die zugrunde liegende SF.2-Bridge-Phase als source_phase fest.",
            "Die bestehende SF.2A Sensorquellen-Synchronisierung bleibt unverändert stale-safe und read-only.",
        ),
        "tests": (
            "check_spiderfarmer_devices.py simuliert einen realistischen GGS-State mit Sensor, Licht, Ventilator, Gebläse und Power-Strip.",
            "Die Regression verlangt Run-Level 8, Standby-Level 2, oscillation_level 5, Natural Wind sowie den beobachteten 90/270-Sekunden-Zyklus.",
            "Outlet-Kanäle erhalten stabile IDs wie outlet:O1 und können einzeln über den Growstar-Service gelesen werden.",
            "Statische Guards verbieten Socket-, MQTT-Publish-, writer.write- und setConfigField-Commandpfade in SF.3A.",
            "Bestehende Repository-, Release-Split- und SF.2A-Regressionen bleiben zusätzlich auszuführen.",
        ),
    },
    {
        "version": "3.11.4",
        "date": "2026-08-22",
        "phase": "CORE.R2",
        "title": "Repository-Baseline an Release-Paketstruktur angepasst",
        "summary": (
            "Der Repository-Baseline-Test lädt core.release nach dem CORE.R1-"
            "Split jetzt als reguläres Python-Paketmodul. Dadurch funktionieren "
            "die relativen Importe aus core.release auch im Regressionstest, "
            "ohne die neue Release-Struktur zurückzubauen oder Runtime-Code zu "
            "verändern."
        ),
        "changes": (
            "check_repository_baseline.py lädt core.release nicht länger über ein anonymes spec_from_file_location-Modul, sondern package-aware über importlib.import_module.",
            "Vor dem Import werden eventuell zwischengespeicherte core.release/core.releases-Module entfernt, damit der Test den aktuellen Repository-Stand prüft.",
            "Der Repository-Root wird vor dem Import explizit in sys.path gehalten; relative Importe aus core.release funktionieren dadurch wie im normalen Growstar-Prozess.",
            "core/releases/current.py erhält den neuen Release-Node 3.11.4 / CORE.R2; 3.11.3 / CORE.R1 bleibt direkter Vorgänger.",
            "Keine Runtime-, Hardware-, Sensor-, Shelly-, MQTT-, Netzwerk- oder Spider-Farmer-Datei wird geändert.",
        ),
        "tests": (
            "check_repository_baseline.py muss nach dem Patch ohne ImportError vollständig durchlaufen.",
            "check_release_split.py muss weiterhin die getrennte Release-Historie und die öffentliche core.release-Schnittstelle bestätigen.",
            "check_spiderfarmer_growstar_adapter.py muss weiterhin vollständig grün bleiben.",
            "Ein Syntax-/AST-Check bestätigt beide geänderten Python-Dateien vor dem Schreiben.",
        ),
    },
    {
        "version": "3.11.3",
        "date": "2026-08-22",
        "phase": "CORE.R1",
        "title": "Release-Historie aus core/release.py ausgelagert",
        "summary": (
            "Growstars inzwischen sehr große Release-Historie wird aus der "
            "öffentlichen core.release-Schnittstelle ausgelagert. Die bisherige "
            "Historie bleibt vollständig und unverändert erhalten, während neue "
            "Patch-Einträge künftig in kleinen, separat verwaltbaren Release-"
            "Modulen liegen. Runtime-, Hardware-, Sensor-, Netzwerk- und "
            "Spider-Farmer-Verhalten werden durch diesen Strukturpatch nicht "
            "verändert."
        ),
        "changes": (
            "Die bisherige vollständige core/release.py wird bytegleich als core/releases/legacy.py erhalten; kein historischer Release-Eintrag wird neu geschrieben, gekürzt oder gelöscht.",
            "core/releases/current.py enthält ab 3.11.3 ausschließlich neue Release-Nodes und bleibt dadurch für zukünftige mobile GitHub-Patches klein.",
            "core/releases/__init__.py setzt CURRENT_RELEASES und die unveränderte LEGACY_RELEASES-Historie zu genau einem RELEASES-Tupel zusammen.",
            "core/release.py bleibt die stabile öffentliche Schnittstelle mit RELEASES, current_release(), release_history(), release_summary(), GROWSTAR_VERSION, GROWSTAR_RELEASE_DATE und GROWSTAR_INTERNAL_PHASE.",
            "Bestehende Importe aus core.release sowie routes/release.py müssen dadurch nicht angepasst werden.",
            "Der direkte Vorgänger des Strukturpatches bleibt Growstar 3.11.2 / SF.2A; dessen vollständige Patch-Note liegt unverändert im Legacy-Modul.",
            "Der Patch verändert keine Growstar-Konfiguration, keine Sensorzuordnung, keine Shelly-Funktion, keinen MQTT-Pfad, keine Netzwerkgrenze und keine Spider-Farmer-Bridge.",
        ),
        "tests": (
            "check_release_split.py verlangt die getrennte aktuelle/historische Release-Struktur und prüft die öffentliche core.release-Schnittstelle versionsunabhängig.",
            "Die Regression bestätigt, dass RELEASES exakt aus CURRENT_RELEASES plus LEGACY_RELEASES besteht und keine Versions-/Phasen-Duplikate enthält.",
            "Der vollständige Legacy-Bestand muss weiterhin 3.11.2 / SF.2A als ersten Eintrag besitzen.",
            "Die öffentliche core.release-API wird auf defensive Kopien, deutsches Datumslabel und unveränderte Summary-Felder geprüft.",
            "Die alte monolithische Historie wurde bei der Migration vor jedem Schreibzugriff über ihren Git-Blob-SHA verifiziert.",
        ),
    },
)
