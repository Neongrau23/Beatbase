# CONFIG: Zentrale Watcher- und IPC-Konfiguration

import os

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
ENABLE_GENIUS = True
ENABLE_SONGSTATS = True
ENABLE_TUNEBAT = True
ENABLE_SONGBPM = True

# Tunebat-Suchergebnisse: HTML-Dateien speichern?
SAVE_TUNEBAT_HTML = True

# JSON-Archivierung
JSON_EXPORT_DIR = "data/json"

# URLs
SONGBPM_URL = "https://songbpm.com/"
GENIUS_URL = "https://genius.com/"
TUNEBAT_URL = "https://tunebat.com/"
SONGSTATS_URL = "https://songstats.com/"

# Externe Beatbase-SQLite-DB für update_audio_features (core/db.py).
# Default ist der bisherige Pfad; über die Env-Var BEATBASE_DB_PATH überschreibbar.
BEATBASE_DB_PATH = os.getenv("BEATBASE_DB_PATH", "C:/workspace/beatbase/spotify.db")
