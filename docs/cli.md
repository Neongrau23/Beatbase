# CLI-Referenz

Alle Beatbase-Komponenten lassen sich als Modul via `uv run python -m …`
starten. Stdout liefert JSON / Daten, stderr enthält Status-Logs
(siehe [Logging-Konvention](architecture.md#logging-konvention)).

## Watcher

Der Orchestrator. Pollt Spotify in einem festen Intervall und triggert die
Extraktoren bei jedem Songwechsel.

```powershell
uv run python -m beatbase
```

Beendet wird er mit `Ctrl+C` (sauber via `KeyboardInterrupt`).

Konfiguration: [`configuration.md#watcher`](configuration.md#watcher).

## Spotify

Holt den aktuell spielenden Track und schreibt ihn als IPC-Wert
(`"<Title> von <Artists>"`) in `now_playing.txt` bzw. die Env-Variable.

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

## Songstats

Scrapet Plattform-Stats, Audio-Features und Performance-Daten. Gibt das
Ergebnis als JSON auf stdout aus.

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
| `--track-id` | string | — | Wenn gesetzt: schreibt Audio-Features in externe SQLite-DB (siehe unten). |
| `--headless` | flag | False | Browser unsichtbar starten. |

### `--track-id` und externe DB

Wenn `--track-id` gesetzt ist und die Extraktion ein `Energy`-Feld liefert,
schreibt Songstats die acht Audio-Features
(`danceability`, `acousticness`, `energy`, `instrumentalness`, `liveness`,
`speechiness`, `valence`, `loudness`) per `UPDATE` in die SQLite-DB unter
`C:/workspace/beatbase/spotify.db`, Spalten gleichen Namens, Tabelle `tracks`.

> Diese DB gehört nicht zum Repo. Sie ist Teil eines übergeordneten Systems.

### Beispiel

```powershell
uv run python -m beatbase.songstats.songstats `
  --song "Blinding Lights" `
  --artist "The Weeknd" `
  --track-id "abc123" `
  --headless `
  | jq '{energy: .Energy, key: .Key, tempo: .Tempo}'
```

## Genius

Scrapet Lyrics und Credits via Selenium + BeautifulSoup.

```powershell
# Mit explizitem Suchbegriff
uv run python -m beatbase.genius.genius "Blinding Lights The Weeknd" [--headless]

# Fallback: aktueller Song aus dem IPC-Layer
uv run python -m beatbase.genius.genius
```

### Argumente

| Argument | Typ | Default | Beschreibung |
|----------|-----|---------|--------------|
| `query` | string (positional, optional) | IPC-Wert | Suchbegriff (Titel + Künstler). |
| `--headless` | flag | False | Browser unsichtbar starten. |

### Output-Schema (gekürzt)

```json
{
  "track_info": {
    "title": "Blinding Lights",
    "artist": "The Weeknd",
    "views": "1.2M views",
    "release_date": "Nov. 29, 2019"
  },
  "credits": {
    "producers": ["Max Martin", "Oscar Holter"],
    "writers": ["Abel Tesfaye", "..."]
  },
  "about": {"bio": "...", "q_and_a": []},
  "lyrics": [
    {"section": "[Verse 1]", "lines": ["..."]},
    {"section": "[Chorus]", "lines": ["..."]}
  ],
  "album_tracklist": [
    {"number": "1", "title": "...", "link": "https://genius.com/..."}
  ]
}
```

## Linting

Ruff ist als einziger Linter konfiguriert (`pyproject.toml`).

```powershell
uv run ruff check .
```

## Tests

Aktuell keine Test-Suite (`tests/` ist leer). Beim Hinzufügen die `src/`-Struktur
spiegeln (z. B. `tests/songstats/test_validator.py` für
`src/beatbase/songstats/validator.py`).
