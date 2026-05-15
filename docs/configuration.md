# Konfiguration

Beatbase trennt die Konfiguration nach Verantwortungsbereich.

| Datei / Mechanismus | Inhalt |
|---------------------|--------|
| `.env` (Projektroot) | Secrets: Spotify-Credentials, optional `BEATBASE_DB_PATH` |
| `src/beatbase/core/config.py` | Watcher-, IPC- und DB-Defaults |
| `src/beatbase/tunebat/config.py` | Tunebat-Konstanten |
| `src/beatbase/songstats/config.py` | Songstats-Konstanten |
| `src/beatbase/genius/config.py` | Genius-Konstanten |

## `.env`

```env
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback   # optional

# Optional: alternativer DB-Pfad für update_audio_features
BEATBASE_DB_PATH=D:/eigener/pfad/spotify.db
```

Geladen über `python-dotenv` in `spotify_current.py`. Der Redirect-URI muss
zusätzlich im [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
hinterlegt sein.

## Watcher & IPC (`core/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `IPC_MODE` | `"file"` | `"file"` schreibt/liest `now_playing.txt`, `"env"` nutzt die Windows-User-Env. |
| `IPC_FILE_PATH` | `"now_playing.txt"` | Pfad relativ zum CWD. Nur bei `IPC_MODE = "file"`. |
| `ENV_VAR_NOW_PLAY` | `"NOW_PLAY"` | Name der Env-Variable. Nur bei `IPC_MODE = "env"`. |
| `SENTINEL_NONE` | `"nothing..."` | Markiert "kein Song aktiv". Konsistent zwischen allen Modulen halten. |
| `POLLING_INTERVAL` | `10` | Sekunden zwischen Spotify-Polls im Watcher. |
| `WATCHER_HEADLESS` | `False` | Ob die Browser-Extraktoren im Watcher-Modus headless laufen. |
| `ENABLE_TUNEBAT` | `True` | Tunebat in der Pipeline aktiv. |
| `ENABLE_SONGSTATS` | `True` | Songstats in der Pipeline aktiv. |
| `ENABLE_GENIUS` | `True` | Genius in der Pipeline aktiv. |
| `ENABLE_SONGBPM` | `True` | SongBPM in der Pipeline aktiv. |
| `JSON_EXPORT_DIR` | `"data/json"` | Verzeichnis für `{track_id}.json`-Archivierung. |
| `BEATBASE_DB_PATH` | `C:/workspace/beatbase/spotify.db` | Externe SQLite-DB für `--track-id`. Via Env-Var überschreibbar. |

### IPC-Mode wählen

- **`"file"`** ist plattformunabhängig und schneller (kein PowerShell-Roundtrip).
  Wenn ein Konsument im selben CWD läuft → erste Wahl.
- **`"env"`** ist nützlich, wenn Konsumenten in anderen Arbeitsverzeichnissen
  laufen (z. B. Stream-Deck-Plugin, OBS-Source-Script). Die Env-Variable ist
  systemweit lesbar.

### Extraktoren aus- oder anschalten

Die `ENABLE_*`-Flags steuern die Pipeline-Mitglieder. Reihenfolge bleibt
deterministisch: **Tunebat → Songstats → Genius → SongBPM**. Tunebat zuerst,
weil es Songstats einen Direktlink über `bus.set("tunebat",
"songstats_url", …)` liefern kann.

## URLs (`core/config.py`)

```python
SONGBPM_URL  = "https://songbpm.com/"
GENIUS_URL   = "https://genius.com/"
TUNEBAT_URL  = "https://tunebat.com/"
SONGSTATS_URL = "https://songstats.com/"
```

## Tunebat (`tunebat/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `PROFILE_DIR` | `"../.profiles/tunebat_profile"` | Relativ zu `src/`. Wird zu `<root>/.profiles/tunebat_profile/`. |
| `USER_AGENT` | Chrome 123 UA | Für `playwright_stealth`-Maskierung. |
| `HEADLESS` | `True` | Standalone-Default; im Watcher überschrieben durch `WATCHER_HEADLESS`. |
| `MATCH_THRESHOLD` | `0.8` | Mindest-Score, ab dem ein Suchtreffer akzeptiert wird. |

## Songstats (`songstats/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `MATCH_THRESHOLD` | `0.7` | Mindest-Score (etwas niedriger als andere — Songstats ist matchsensitiv). |
| `SEARCH_TIMEOUT` | `2` | Wartezeit (s) für initiales Suchergebnis. |
| `RELOAD_TIMEOUT` | `30000` | Playwright-Reload-Timeout in ms. |

Profil-Pfad ist im Modul fest verdrahtet: `<root>/.profiles/songstats_profile/`.

## Genius (`genius/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `BASE_URL` | `"https://genius.com"` | API-Endpoint-Wurzel. |
| `PROFILE_DIR` | `"../.profiles/genius_profile_playwright"` | Relativ zu `src/`. Wird zu `<root>/.profiles/genius_profile_playwright/`. |
| `USER_AGENT` | Chrome 123 UA | Wird beim Playwright-Start gesetzt. |
| `WEBDRIVER_TIMEOUT` | `15` | Sekunden für Wait-Operationen. |
| `PAGE_LOAD_SLEEP` | `0.5` | Sekunde Pause nach Seitenwechsel (für JS-Rendering). |
| `HEADLESS` | `True` | Standalone-Default; im Watcher überschrieben. |
| `MATCH_THRESHOLD` | `0.8` | Mindest-Score für Suchergebnisse. |

## Datenbank-Pfad

`BEATBASE_DB_PATH` (in `core/config.py`) zeigt auf eine **externe** SQLite-DB,
die nicht zum Repo gehört. Wird nur verwendet, wenn `--track-id` an die
Songstats-CLI übergeben wird. Schema-Anforderung: Eine Tabelle `tracks` mit
Spalten `track_id`, `danceability`, `acousticness`, `energy`,
`instrumentalness`, `liveness`, `speechiness`, `valence`, `loudness`.

Überschreibbar via Env-Var:

```powershell
$env:BEATBASE_DB_PATH = "D:/eigener/pfad/spotify.db"
uv run python -m beatbase.songstats.songstats --song "X" --track-id "abc"
```

## Linting (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

Ruff ist der einzige konfigurierte Linter. Aufruf: `uv run ruff check .`
