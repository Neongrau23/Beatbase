# CLI-Referenz

Alle Beatbase-Komponenten lassen sich als Modul via `uv run python -m …`
starten. Stdout liefert JSON / Daten, stderr enthält Status-Logs
(siehe [Logging-Konvention](architecture.md#logging-konvention)).

## Watcher

Der Orchestrator. Pollt Spotify in einem festen Intervall und triggert die
Extraktoren der Pipeline bei jedem Songwechsel.

```powershell
uv run python -m beatbase                # Watcher starten
uv run python -m beatbase process --stop         # Laufenden Watcher beenden
uv run python -m beatbase process --headless     # Browser unsichtbar starten
```

Der Watcher schreibt eine **PID-Datei** (`.beatbase.pid`). Ein zweiter Start
verweigert mit Hinweis; mit `--stop` wird der Prozess per `SIGTERM` beendet.
Manuelles Abbrechen per `Ctrl+C` ist ebenfalls möglich.

Konfiguration: [`configuration.md#watcher--ipc-coreconfigpy`](configuration.md#watcher--ipc-coreconfigpy).

## Batch-Modus

Erlaubt das gezielte Abarbeiten einer Liste von Tracks (z. B. aus einer CSV-Datei) unabhängig vom Spotify-Watcher. Der Zustand wird in einer eigenen SQLite-Datenbank (`data/search_queue.db`) protokolliert.

```powershell
uv run python -m beatbase batch add tracks.csv          # CSV (id, song, artist, ...) einlesen
uv run python -m beatbase batch run [--limit N]         # Ausstehende Tracks scrapen
uv run python -m beatbase batch retry [--source NAME]   # Fehlgeschlagene Tracks zurücksetzen
uv run python -m beatbase batch status                  # Statusübersicht anzeigen
```

Argumente der Subbefehle:
- `add`: Erwartet eine CSV-Datei. Benötigt mindestens Spalten `song` und `artist`. Generiert eine Track-ID falls fehlend. Semikolon-getrennte Künstler (`Artist1; Artist2`) werden unterstützt.
- `run`: `--limit` beschränkt die Anzahl an bearbeiteten Tracks pro Lauf. `--headless` läuft im Hintergrund. Setzt fehlschlagende Quellen auf `fail: <msg>` und erfolgreiche auf `ok`.
- `retry`: `--source` beschränkt den Retry auf einen bestimmten Extraktor (z.B. `tunebat`). Setzt `fail:`-Stati wieder auf `NULL` (pending).
- `status`: Gibt eine Zählung (`ok`, `no_match`, `fail`, `pending`) pro Quelle aus.

## Spotify

Holt den aktuell spielenden Track und schreibt ihn in den IPC-Layer
(`now_playing.txt` bzw. Env-Variable `NOW_PLAY`).

```powershell
uv run python -m beatbase.extractor.spotify.spotify_current
```

**Ausgabe (stdout):**

```
🎵 Aktuell spielt: Blinding Lights von The Weeknd
```

Beim ersten Aufruf startet der OAuth-Flow im Browser. Der Token landet in
`data/.spotify_cache`.

**Wenn kein Track läuft**, wird der Sentinel `"nothing..."` in den IPC-Layer
geschrieben.

> ⚠️ **IPC-Format:** Im Gegensatz zum Watcher (der sauber strukturiertes JSON
> `{"song": ..., "artists": [...]}` schreibt) schreibt das Standalone-CLI das
> **Legacy-Format** als einen String — konkret landet
> `{"song": "Blinding Lights von The Weeknd", "artists": []}` im IPC. Der
> Reader in `shared/now_playing.py::read_now_playing_data()` fängt das ab und
> splittet den String an `" von "` wieder zurück, sodass nachgelagerte
> Extraktoren `song` und `artists` korrekt getrennt sehen. Wer auf das saubere
> JSON-Format angewiesen ist, sollte den Watcher als Schreiber nutzen.

## Tunebat

Scrapet BPM, Key, Camelot, Audio-Features, Release-Daten und einen direkten
Songstats-Link. Gibt das Ergebnis als JSON auf stdout aus.

```powershell
# Mit expliziten Argumenten
uv run python -m beatbase.extractor.tunebat.tunebat `
  --song "Blinding Lights" `
  --artist "The Weeknd" `
  [--headless]

# Mit positionalem Query (Format "Titel von Artist")
uv run python -m beatbase.extractor.tunebat.tunebat "Blinding Lights von The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.extractor.tunebat.tunebat
```

### Argumente

| Flag | Typ | Default | Beschreibung |
|------|-----|---------|--------------|
| `query` | string (positional) | IPC-Wert | Suchbegriff (Titel + Künstler). Erkennt `" von "`. |
| `--song` | string | — | Expliziter Titel (Vorrang vor `query`). |
| `--artist` | string (mehrfach) | `[]` | Künstler. Kann mehrfach angegeben werden. |
| `--headless` | flag | aus `beatbase/extractor/tunebat/config.py::HEADLESS` | Browser unsichtbar starten. |
| `--no-headless` | flag | — | Browser sichtbar starten. |
| `--dev` | flag | False | Browser nach Suche offen lassen (für manuelle Cloudflare-Lösung). |

### Profil-Warmup

Bei hartnäckiger Cloudflare-Bot-Detection kann das Tunebat-Profil mit
menschlicher Aktivität "warmgelaufen" werden:

```powershell
uv run python -m beatbase.extractor.tunebat.browser.warm_profile
```

Das Skript öffnet sichtbar Google, YouTube und Tunebat, scrollt etwas und
wartet auf `ENTER`. Cookies und Reputations-State bleiben im Profil.

## Songstats

Scrapet die Overview-Sektion: Artists, Collaborators, Record Labels,
Distributors, Release Date, ISRCs, Genres und Music Info (Duration, Key,
Tempo, Time Signature).

```powershell
# Mit expliziten Argumenten
uv run python -m beatbase.extractor.songstats.songstats `
  --song "Blinding Lights" `
  --artist "The Weeknd" `
  [--headless]

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.extractor.songstats.songstats
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
uv run python -m beatbase.extractor.genius.genius "Blinding Lights The Weeknd" [--headless]

# Über --song/--artist
uv run python -m beatbase.extractor.genius.genius --song "Blinding Lights" --artist "The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.extractor.genius.genius
```

### Argumente

| Argument | Typ | Default | Beschreibung |
|----------|-----|---------|--------------|
| `query` | string (positional, optional) | IPC-Wert | Suchbegriff (Titel + Künstler). Erkennt `" von "`. |
| `--song` | string | — | Expliziter Titel. |
| `--artist` | string (mehrfach) | `[]` | Expliziter Künstler. |
| `--headless` | flag | aus `beatbase/extractor/genius/config.py::HEADLESS` | Browser unsichtbar starten. |

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
uv run python -m beatbase.extractor.songbpm.songbpm "Blinding Lights The Weeknd"

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.extractor.songbpm.songbpm
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

```powershell
uv run pytest                        # alle Tests
uv run pytest tests/shared/utils/           # nur ein Subtree
uv run pytest -k callcenter          # nach Namen filtern
uv run pytest -m "not integration"   # Integration-Tests ausschliessen
```

Die Suite besteht aus Unit-Tests (Hotline, Callcenter-Schema,
Search-Variations, Validator, IPC-Layer) und Extraktor-Tests gegen
HTML-Fixtures unter `tests/fixtures/<modul>/`. Browser-/Playwright-Pfade
sind bewusst nicht abgedeckt — fuer e2e-Tests wuerden echte HTML-Dumps
oder Playwright-Mocks benoetigt.
