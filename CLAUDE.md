# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sprache

Antworte standardmäßig auf **Deutsch**. Code, Dateinamen und CLI-Befehle bleiben Englisch.

## Befehle

Das Projekt wird mit `uv` verwaltet (kein `pip`, kein manuelles `venv`).

```powershell
# Setup
uv sync
uv run playwright install chromium

# Watcher (Orchestrator) – pollt Spotify und triggert Extraktoren bei Songwechsel
uv run python -m beatbase

# Einzelne Extraktoren (jeweils mit Fallback auf den IPC-Layer wenn keine Args)
uv run python -m beatbase.spotify.spotify_current
uv run python -m beatbase.songstats.songstats --song "Titel" --artist "Name" [--headless] [--track-id ID]
uv run python -m beatbase.genius.genius "Interpret Titel" [--headless]

# Lint
uv run ruff check .
```

Es gibt aktuell **keine Test-Suite** (`tests/` ist leer). Wenn du Tests hinzufügst, spiegle die `src/`-Struktur.

`--track-id` bei Songstats schreibt Audio-Features direkt in eine **externe** SQLite-DB unter `C:/workspace/beatbase/spotify.db` (gehört zu einem übergeordneten System, nicht zum Repo).

## Architektur

### Hotline / Callcenter Muster
Zweistufiger Datenfluss, der Extraktoren von der finalen Datenstruktur entkoppelt:

- **Hotline** (`core/hotline.py`): Globaler Key-Value-Speicher `bus` (Singleton). Extraktoren legen Rohdaten unter ihrem Quellennamen ab (`bus.set("songstats", key, value)`). Keine Logik, kein Schema.
- **Callcenter** (`utils/callcenter.py`): Liest aus `bus.get_all()` und baut strukturierte Views. Hier liegt die Priorisierungslogik (z. B. `build_song_summary()` nimmt ältestes Release-Datum aus allen Quellen).

Ein neuer Extraktor muss nur `bus.set(quelle, key, value)` aufrufen — die Aggregation passiert im Callcenter.

### Watcher-Loop (`core/watcher.py`)
Zentraler Polling-Loop. Pollt Spotify in `POLLING_INTERVAL` (Default 15s), erkennt Songwechsel über die Spotify-Track-ID, dann pro Songwechsel:

1. `bus.clear()` (Hotline-Reset)
2. IPC-Layer aktualisieren (`write_now_playing`)
3. Spotify-Rohdaten in Hotline pushen
4. Songstats- und Genius-Extraktoren laufen lassen (jeder in seinem eigenen try/except — Fehler eines Extraktors stoppen den Watcher nicht)
5. `build_song_summary()` ausgeben

**Wichtig:** Pro Song wird ein frischer Browser-Kontext geöffnet und am Ende geschlossen (`search_on_songstats` / `search_on_genius` verwalten den Lifecycle selbst). Browser werden nicht zwischen Songs wiederverwendet.

### IPC-Layer (`utils/now_playing.py`)
Entkoppelt Extraktoren, die standalone laufen können. Modus in `core/config.py::IPC_MODE`:

- `"file"` (Default): `now_playing.txt` im CWD, **atomar geschrieben** (temp + `os.replace`) gegen Partial-Reads.
- `"env"`: Windows-User-Env `NOW_PLAY`, gelesen/geschrieben über PowerShell-Subprozesse.

Sentinel `"nothing..."` (`SENTINEL_NONE`) bedeutet "kein Track aktiv". Format des Songstrings: `"<Title> von <Artist1>, <Artist2>"` — Songstats/Genius nutzen diesen als Suchbegriff-Fallback wenn keine CLI-Args.

### Extraktor-Typen
- **API** (`spotify/`): Reine HTTP-Requests via `spotipy`, OAuth-Token in `.spotify_cache` neben dem Modul.
- **Browser** (`songstats/`, `genius/`):
  - **Songstats** = **Playwright** (Chromium). Besonderheit: extrahiert Highcharts-SVG-Daten durch physische Mausbewegungen auf Koordinaten, da die SVGs keine semantischen Klassen haben. Eigene aggressivere Suchbegriff-Generierung inline in `songstats.py` (Permutationen) — Songstats ist sensitiv auf Wortreihenfolge.
  - **Genius** = **Selenium** (Chrome) + BeautifulSoup für Lyrics/Credits-Extraktion.

Beide Browser-Extraktoren nutzen **persistente Browser-Profile** in `songstats_profile/` bzw. `genius_profile_selenium/`. Die Verzeichnisse werden beim ersten Start angelegt, sind in `.gitignore` und **dürfen nicht gelöscht werden** (Login-State, Cookies).

### Suchlogik
- `utils/search_variations.py::generate_variations()`: Generische Variations-Generierung (Reihenfolge, Klammern, Featured-Artists), wiederverwendbar.
- `utils/search_variations.py::extract_featured_artists()`: Zieht versteckte Künstler aus dem Titel (`feat.`, `ft.`, `with`, `von`).
- Songstats hat zusätzlich eine eigene, aggressivere Inline-Variante (Permutations).

### Logging-Konvention
`utils/log.py::log_status()` schreibt nach **stderr**. Stdout bleibt frei für strukturierte JSON-Ausgaben der CLIs. Das ist wichtig wenn die CLIs gepiped werden — nutze `log_status()`, kein `print()`, für Statusmeldungen.

## Code-Konventionen

- **`# DEF: Kurztext`** (max ~40 Zeichen) markiert wichtige Funktionen/Sektionen und erscheint in der VSCode-Minimap. Auch `# SECTION:`, `# ENTRY:`, `# CONFIG:`, `# BRIDGE:`, `# STATE:`, `# WHY:`, `# HELP:` werden im Codebase verwendet.
- Type Hints überall. Google-Style-Docstrings. f-Strings. `pathlib.Path` (wo möglich — der Bestandscode nutzt teils `os.path`).
- Spezifische Exceptions fangen, kein nacktes `except:`.
- Zeilenlänge 100, `target-version = "py311"`, Linter ist Ruff.

## Konfiguration

- `.env` im Projektroot: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, optional `SPOTIPY_REDIRECT_URI`.
- `src/beatbase/core/config.py`: Watcher- und IPC-Defaults (`POLLING_INTERVAL`, `IPC_MODE`, `WATCHER_HEADLESS`, `SENTINEL_NONE`).
- `src/beatbase/songstats/config.py`, `src/beatbase/genius/config.py`: Quellen-spezifische Konstanten (Match-Threshold, Timeouts, User-Agent).
