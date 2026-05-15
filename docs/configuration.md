# Konfiguration

Beatbase trennt die Konfiguration nach Verantwortungsbereich.

| Datei | Inhalt |
|-------|--------|
| `.env` (Projektroot) | Secrets: Spotify-Credentials |
| `src/beatbase/core/config.py` | Watcher- und IPC-Defaults |
| `src/beatbase/songstats/config.py` | Songstats-Konstanten |
| `src/beatbase/genius/config.py` | Genius-Konstanten |

## `.env`

```env
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback   # optional
```

Geladen über `python-dotenv` in `spotify_current.py`. Der Redirect-URI muss
zusätzlich im [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
hinterlegt sein.

## Watcher (`core/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `IPC_MODE` | `"file"` | `"file"` schreibt/liest `now_playing.txt`, `"env"` nutzt die Windows-User-Env. |
| `IPC_FILE_PATH` | `"now_playing.txt"` | Pfad relativ zum CWD. Nur bei `IPC_MODE = "file"`. |
| `ENV_VAR_NOW_PLAY` | `"NOW_PLAY"` | Name der Env-Variable. Nur bei `IPC_MODE = "env"`. |
| `SENTINEL_NONE` | `"nothing..."` | Markiert "kein Song aktiv". Konsistent zwischen allen Modulen halten. |
| `POLLING_INTERVAL` | `15` | Sekunden zwischen Spotify-Polls im Watcher. |
| `WATCHER_HEADLESS` | `True` | Ob die Browser-Extraktoren im Watcher-Modus headless laufen. |

### IPC-Mode wählen

- **`"file"`** ist plattformunabhängig und schneller (kein PowerShell-Roundtrip).
  Wenn ein Konsument im selben CWD läuft → erste Wahl.
- **`"env"`** ist nützlich, wenn Konsumenten in anderen Arbeitsverzeichnissen
  laufen (z. B. Stream-Deck-Plugin, OBS-Source-Script). Die Env-Variable ist
  systemweit lesbar.

## Songstats (`songstats/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `MATCH_THRESHOLD` | `0.8` | Mindest-Score, ab dem ein Suchtreffer akzeptiert wird. |
| `ARTIST_BONUS` | `0.2` | Score-Bonus pro Künstler, der im Treffer vorkommt. |
| `SEARCH_TIMEOUT` | `1` | Wartezeit (s) für initiales Suchergebnis. |
| `RELOAD_TIMEOUT` | `30000` | Playwright-Reload-Timeout in ms. |

Profilverzeichnis: `songstats_profile/` im Projektroot (wird automatisch
angelegt, ist in `.gitignore`). Nicht löschen.

## Genius (`genius/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `BASE_URL` | `"https://genius.com"` | API-Endpoint-Wurzel. |
| `PROFILE_DIR` | `"genius_profile_selenium"` | Verzeichnis im CWD für persistentes Selenium-Profil. |
| `USER_AGENT` | Chrome 123 UA | Wird beim Selenium-Start gesetzt. |
| `WEBDRIVER_TIMEOUT` | `15` | Sekunden für `WebDriverWait`. |
| `PAGE_LOAD_SLEEP` | `1` | Sekunde Pause nach Seitenwechsel (für JS-Rendering). |
| `HEADLESS` | `True` | Selenium ohne sichtbares Fenster. |

## Datenbank (`core/db.py`)

Hartkodiert:

```python
DB_PATH = "C:/workspace/beatbase/spotify.db"
```

Dieser Pfad zeigt auf eine **externe** SQLite-DB, die nicht zum Repo gehört.
Wird nur verwendet, wenn `--track-id` an die Songstats-CLI übergeben wird.
Schema-Anforderung: Eine Tabelle `tracks` mit Spalten `track_id`,
`danceability`, `acousticness`, `energy`, `instrumentalness`, `liveness`,
`speechiness`, `valence`, `loudness`.

## Linting (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
```

Ruff ist der einzige konfigurierte Linter. Aufruf: `uv run ruff check .`
