# Spotify-Extraktor

Quelle: `src/beatbase/spotify/spotify_current.py`

Reiner API-Extraktor — kein Browser, kein Scraping. Nutzt
[`spotipy`](https://spotipy.readthedocs.io/) als Wrapper über die Spotify
Web API.

## Funktionsweise

```python
get_current_spotify_track() -> dict | None
```

1. Lädt `.env` via `python-dotenv`.
2. Liest `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, optional
   `SPOTIPY_REDIRECT_URI` (Default `http://localhost:8888/callback`).
3. Initialisiert `spotipy.Spotify` mit `SpotifyOAuth`.
4. Ruft `sp.current_user_playing_track()` auf.
5. Wenn `is_playing` und `item` vorhanden → gibt Dict zurück; sonst `None`.

### Return-Schema

```python
{
    "id":            "abc123xyz",                      # Spotify-Track-ID
    "song":          "Blinding Lights",                # Titel
    "artists":       ["The Weeknd"],                   # Liste
    "isrc":          "USUG11904206",                   # International Standard Recording Code
    "release_date":  "2019-11-29",                     # ISO oder "YYYY"
    "spotify_url":   "https://open.spotify.com/...",   # Public URL
}
```

`release_date` kann je nach Album-Granularität nur das Jahr enthalten
(z. B. `"1985"`).

## OAuth-Flow

### Scope

```python
SCOPE = "user-read-currently-playing"
```

Minimaler Scope — Beatbase braucht keinen Schreibzugriff.

### Token-Cache

```python
cache_path = os.path.join(os.path.dirname(__file__), ".spotify_cache")
```

Der Cache liegt **neben dem Modul** (`src/beatbase/spotify/.spotify_cache`),
nicht im CWD. Das stellt sicher, dass derselbe Token gefunden wird, egal aus
welchem Verzeichnis Beatbase gestartet wird.

`.spotify_cache` enthält `access_token` und `refresh_token`. Bei Ablauf
refresht `spotipy` automatisch.

### Erstaufruf

Beim ersten Start öffnet sich ein Browserfenster mit der Spotify-Login-Seite.
Nach Bestätigung wird man auf `SPOTIPY_REDIRECT_URI` weitergeleitet — die
URL enthält den `code`-Parameter, den `spotipy` aus der Adresszeile parst.
Das passende Setup im Spotify Developer Dashboard ist erforderlich.

## CLI

```powershell
uv run python -m beatbase.spotify.spotify_current
```

Schreibt den Songstring (`"Title von Artists"`) via `write_now_playing` in
den IPC-Layer und gibt ihn zusätzlich auf stdout aus.

Wenn nichts läuft:

```powershell
⏸️ Aktuell wird kein Song auf Spotify abgespielt.
```

Und `clear_now_playing()` wird aufgerufen.

## Fehlerquellen

| Fehlerbild | Ursache | Lösung |
|------------|---------|--------|
| `Fehler: Spotify API Credentials fehlen` | `.env` fehlt / leere Env-Vars | `.env` anlegen, `SPOTIPY_CLIENT_ID` + `_SECRET` setzen |
| `INVALID_CLIENT: Invalid redirect URI` | Redirect URI nicht im Dashboard hinterlegt | URI ergänzen unter [dashboard](https://developer.spotify.com/dashboard) → App → Edit Settings |
| `Fehler beim Abrufen des Spotify-Tracks: 401` | Token abgelaufen, Refresh fehlgeschlagen | `.spotify_cache` löschen, neu einloggen |
| Hängt im Browser nach Login | Redirect URI zeigt auf einen anderen Port | URI in `.env` an Dashboard-Eintrag angleichen |

## Watcher-Integration

Der Watcher importiert `get_current_spotify_track` direkt und ruft sie alle
`POLLING_INTERVAL` Sekunden auf. Die Spotify-Rohdaten landen via
`_push_spotify(track)` in der Hotline:

```python
bus.set("spotify", "id", ...)
bus.set("spotify", "name", ...)
bus.set("spotify", "artists", ...)
bus.set("spotify", "isrc", ...)
bus.set("spotify", "release_date", ...)
bus.set("spotify", "url", ...)
```
