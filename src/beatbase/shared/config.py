# CONFIG: Zentrale Watcher- und IPC-Konfiguration

import os
from pathlib import Path

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

# URLs
SONGBPM_URL = "https://songbpm.com/"
GENIUS_URL = "https://genius.com/"
TUNEBAT_URL = "https://tunebat.com/"
SONGSTATS_URL = "https://songstats.com/"

# SECTION: Pfade — alle Daten- und Laufzeit-Pfade an einer Stelle.
# WHY: Vorher waren diese Pfade über mehrere Module verstreut. Zentralisiert
# erlaubt das Override per Env-Var (BEATBASE_DATA_DIR) und macht Tests einfacher.
DATA_DIR = Path(os.getenv("BEATBASE_DATA_DIR", "data"))
JSON_EXPORT_DIR = DATA_DIR / "json"
QUEUE_DIR = DATA_DIR / "queue"
SONGS_DB_PATH = DATA_DIR / "songs.db"
SEARCH_QUEUE_DB_PATH = DATA_DIR / "search_queue.db"
TUNEBAT_SEARCHES_DB_PATH = DATA_DIR / "tunebat_searches.db"
GENIUS_DB_PATH = DATA_DIR / "genius.db"
TUNEBAT_SEARCHES_HTML_DIR = DATA_DIR / "tunebat_searches"
SPOTIFY_CACHE_PATH = DATA_DIR / ".spotify_cache"
PID_FILE_PATH = Path(".beatbase.pid")

# Externe Beatbase-SQLite-DB für update_audio_features (processor/external_db.py).
# Default ist der bisherige Pfad; über die Env-Var BEATBASE_DB_PATH überschreibbar.
BEATBASE_DB_PATH = os.getenv("BEATBASE_DB_PATH", "C:/workspace/beatbase/spotify.db")
