# CLI-Referenz

Alle Beatbase-Komponenten lassen sich als Modul via `uv run python -m …`
starten. Stdout liefert JSON / Daten, stderr enthält Status-Logs
(siehe [Logging-Konvention](architecture.md#logging-konvention)).

## Watcher

Der Orchestrator. Pollt Spotify in einem festen Intervall und triggert die
Extraktoren der Pipeline bei jedem Songwechsel.

```powershell
uv run python -m beatbase                # Watcher starten
uv run python -m beatbase --stop         # Laufenden Watcher beenden
uv run python -m beatbase --headless     # Browser unsichtbar starten
```

Der Watcher schreibt eine **PID-Datei** (`.beatbase.pid`). Ein zweiter Start
verweigert mit Hinweis; mit `--stop` wird der Prozess per `SIGTERM` beendet.
Manuelles Abbrechen per `Ctrl+C` ist ebenfalls möglich.

Konfiguration: [`configuration.md#watcher--ipc-coreconfigpy`](configuration.md#watcher--ipc-coreconfigpy).

## Spotify

Holt den aktuell spielenden Track und schreibt ihn als JSON
(`{"song": "...", "artists": [...]}`) in `now_playing.txt` bzw. in die
Env-Variable `NOW_PLAY`.

```powershell
uv run python -m beatbase.spotify.spotify_current
```

**Ausgabe (stdout):**

```
🎵 Aktuell spielt: Blinding Lights von The Weeknd
```

Beim ersten Aufruf startet der OAuth-Flow im Browser. Der Token landet in
`src/beatbase/spotify/.spotify_cache`.

**Wenn kein Track läuft**, wird der Sentinel `"nothing..."` in den IPC-Layer
geschrieben.

## Tunebat

Scrapet BPM, Key, Camelot, Audio-Features, Release-Daten und einen direkten
Songstats-Link. Gibt das Ergebnis als JSON auf stdout aus.

```powershell
# Mit expliziten Argumenten
uv run python -m beatbase.tunebat.tunebat `
  --song "Blinding Lights" `
  --artist "The Weeknd" `
  [--headless]

# Mit positionalem Query (Format "Titel von Artist")
uv run python -m beatbase.tunebat.tunebat "Blinding Lights von The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.tunebat.tunebat
```

### Argumente

| Flag | Typ | Default | Beschreibung |
|------|-----|---------|--------------|
| `query` | string (positional) | IPC-Wert | Suchbegriff (Titel + Künstler). Erkennt `" von "`. |
| `--song` | string | — | Expliziter Titel (Vorrang vor `query`). |
| `--artist` | string (mehrfach) | `[]` | Künstler. Kann mehrfach angegeben werden. |
| `--headless` | flag | aus `tunebat/config.py::HEADLESS` | Browser unsichtbar starten. |
| `--no-headless` | flag | — | Browser sichtbar starten. |
| `--dev` | flag | False | Browser nach Suche offen lassen (für manuelle Cloudflare-Lösung). |

### Profil-Warmup

Bei hartnäckiger Cloudflare-Bot-Detection kann das Tunebat-Profil mit
menschlicher Aktivität "warmgelaufen" werden:

```powershell
uv run python -m beatbase.tunebat.browser.warm_profile
```

Das Skript öffnet sichtbar Google, YouTube und Tunebat, scrollt etwas und
wartet auf `ENTER`. Cookies und Reputations-State bleiben im Profil.

## Songstats

Scrapet die Overview-Sektion: Artists, Collaborators, Record Labels,
Distributors, Release Date, ISRCs, Genres und Music Info (Duration, Key,
Tempo, Time Signature).

```powershell
# Mit expliziten Argumenten
uv run python -m beatbase.songstats.songstats `
  --song "Blinding Lights" `
  --artist "The Weeknd" `
  [--headless]

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.songstats.songstats
```

### Argumente

| Flag | Typ | Default | Beschreibung |
|------|-----|---------|--------------|
| `--song` | string | — | Titel. Wenn weggelassen → IPC-Fallback. |
| `--artist` | string (mehrfach) | `[]` | Künstler. Kann mehrfach angegeben werden. |
| `--track-id` | string | — | Wenn gesetzt: schreibt Audio-Features in die externe SQLite-DB (siehe unten). |
| `--headless` | flag | False | Browser unsichtbar starten. |

### `--track-id` und externe DB

> ⚠️ Hinweis: Der aktuelle `_extract_overview` liefert **keine** Audio-Features
> mehr (Highcharts-Trick wurde entfernt). Audio-Features kommen jetzt aus
> **Tunebat**. Der `--track-id`-Pfad bleibt aktiv, wird aber nur dann
> tatsächlich in die DB schreiben, wenn ein Feld `"Energy"` im Ergebnis ist.
> Konkret: aktuell ein No-Op solange das Songstats-Schema audio_features nicht
> wieder bedient.

Wenn `--track-id` gesetzt ist und das Ergebnis ein `Energy`-Feld enthält,
schreibt Songstats die acht Audio-Features
(`danceability`, `acousticness`, `energy`, `instrumentalness`, `liveness`,
`speechiness`, `valence`, `loudness`) per `UPDATE` in die SQLite-DB unter
`BEATBASE_DB_PATH` (Default `C:/workspace/beatbase/spotify.db`),
Spalten gleichen Namens, Tabelle `tracks`.

> Diese DB gehört nicht zum Repo. Sie ist Teil eines übergeordneten Systems.
> Pfad kann via `BEATBASE_DB_PATH`-Env-Var überschrieben werden.

## Genius

Scrapet Lyrics, Credits, Album-Tracklist via Playwright + BeautifulSoup.

```powershell
# Mit explizitem Suchbegriff
uv run python -m beatbase.genius.genius "Blinding Lights The Weeknd" [--headless]

# Über --song/--artist
uv run python -m beatbase.genius.genius --song "Blinding Lights" --artist "The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.genius.genius
```

### Argumente

| Argument | Typ | Default | Beschreibung |
|----------|-----|---------|--------------|
| `query` | string (positional, optional) | IPC-Wert | Suchbegriff (Titel + Künstler). Erkennt `" von "`. |
| `--song` | string | — | Expliziter Titel. |
| `--artist` | string (mehrfach) | `[]` | Expliziter Künstler. |
| `--headless` | flag | aus `genius/config.py::HEADLESS` | Browser unsichtbar starten. |

### Output-Schema (gekürzt)

```json
{
  "lyrics": [
    {"section": "[Verse 1]", "lines": ["..."]},
    {"section": "[Chorus]", "lines": ["..."]}
  ],
  "url": "https://genius.com/...",
  "album_tracklist": [
    {"number": "1", "title": "...", "link": "https://genius.com/..."}
  ],
  "credits": {
    "producers": ["..."],
    "writers": ["..."]
  }
}
```

## SongBPM

Scrapet die Vibe-Beschreibung des Tracks von [songbpm.com](https://songbpm.com).

```powershell
uv run python -m beatbase.songbpm.songbpm "Blinding Lights The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.songbpm.songbpm
```

### Argumente

| Argument | Typ | Default | Beschreibung |
|----------|-----|---------|--------------|
| `query` | string (positional, optional) | IPC-Wert | Suchbegriff. |
| `--headless` | flag | True | Browser unsichtbar starten. |

## Linting

Ruff ist als einziger Linter konfiguriert (`pyproject.toml`).

```powershell
uv run ruff check .
uv run ruff check . --fix
```

## Tests

Aktuell keine Test-Suite (`tests/` ist leer). Beim Hinzufügen die `src/`-Struktur
spiegeln (z. B. `tests/utils/test_callcenter.py` für
`src/beatbase/utils/callcenter.py`).
