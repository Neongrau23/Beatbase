# CONFIG: Zentrale Watcher- und IPC-Konfiguration

# IPC-Modus: "file" schreibt/liest now_playing.txt, "env" nutzt die Windows-User-Env NOW_PLAY.
IPC_MODE = "file"

# Pfad der IPC-Datei (relativ zum Arbeitsverzeichnis). Nur relevant bei IPC_MODE = "file".
IPC_FILE_PATH = "now_playing.txt"

# Name der Umgebungsvariable. Nur relevant bei IPC_MODE = "env".
ENV_VAR_NOW_PLAY = "NOW_PLAY"

# Sentinel-Wert für "kein Song aktiv".
SENTINEL_NONE = "nothing..."

# Polling-Intervall des Watchers in Sekunden.
POLLING_INTERVAL = 10

# Headless-Default für Extraktoren im Watcher-Loop.
WATCHER_HEADLESS = False

# Welche Extraktoren sollen ausgeführt werden?
ENABLE_GENIUS = False
ENABLE_SONGSTATS = False
ENABLE_TUNEBAT = True
ENABLE_SONGBPM = True

# JSON-Archivierung
JSON_EXPORT_DIR = "data/json"

# URLs
SONGBPM_URL = "https://songbpm.com/"
GENIUS_URL = "https://genius.com/"
TUNEBAT_URL = "https://tunebat.com/"
SONGSTATS_URL = "https://songstats.com/"
