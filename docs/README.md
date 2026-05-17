# Beatbase — Dokumentation

Willkommen in der technischen Dokumentation von **Beatbase**, einem Aggregator für
Musik-Metadaten. Beatbase erkennt den aktuell spielenden Spotify-Track und sammelt
parallel Daten aus **Spotify** (API), **Tunebat**, **Songstats**, **Genius** und
**SongBPM** (alle Playwright-Scraper).

## Übersicht

```
Spotify API ─┐
Tunebat ─────┤
Songstats ───┼─► Hotline (bus) ──► Callcenter ──► Strukturierte Song-Daten
Genius ──────┤
SongBPM ─────┘
```

Ein zentraler **Watcher** pollt Spotify in einem festen Intervall, erkennt
Songwechsel über die Track-ID und triggert die Browser-Extraktoren in einer
deklarativen Pipeline (`EXTRACTORS` in `core/watcher.py`). Rohdaten landen im
**Hotline**-Bus; das **Callcenter** baut daraus eine strukturierte Zusammenfassung
nach einem festen Master-Schema. Standalone-Aufrufe der Extraktoren sind ebenfalls
möglich, sie greifen über einen **IPC-Layer** auf den aktuell spielenden Song zu.

## Inhaltsverzeichnis

### Einstieg

- [Getting Started](getting-started.md) — Installation, `.env`, erste Ausführung
- [CLI-Referenz](cli.md) — Alle Aufrufe von Watcher und Extraktoren
- [Konfiguration](configuration.md) — Einstellbare Parameter

### Architektur

- [Architekturüberblick](architecture.md) — Designentscheidungen, Datenfluss
- [Watcher](modules/watcher.md) — Zentraler Polling-Loop & Pipeline
- [Hotline & Callcenter](modules/hotline-callcenter.md) — Bus-Pattern + Schema
- [IPC-Layer](modules/ipc.md) — Datei- oder Env-basierte Kommunikation

### Extraktoren

- [Spotify](modules/spotify.md) — API-Zugriff via `spotipy`
- [Tunebat](modules/tunebat.md) — Playwright + Stealth, BPM/Key/Audio-Features
- [Songstats](modules/songstats.md) — Playwright + BS4, Overview-Daten
- [Genius](modules/genius.md) — Playwright + BS4, Lyrics & Credits
  - [Genius-Suche (Deep Dive)](genius_suche.md) — technischer Ablauf der Songsuche
- SongBPM — Playwright + BS4, Vibe-Beschreibung (siehe [CLI](cli.md))

### Mitwirken

- [Entwicklung](development.md) — Coding-Konventionen, Linting, Tests
- [Troubleshooting](troubleshooting.md) — Bekannte Probleme und Lösungen

## Projektstruktur (Quellbaum)

```
src/beatbase/
├── __main__.py              # CLI: extract / process / batch / (default beides)
├── extractor/               # 🏭 STANDORT 1: BESCHAFFUNG
│   ├── orchestrator.py      # Watcher + deklarative EXTRACTORS-Pipeline
│   ├── hotline.py           # Globaler Daten-Bus (Hotline)
│   ├── callcenter.py        # Daten-Aggregation mit deklarativem Schema
│   ├── queue.py             # write_to_queue() Helper
│   ├── spotify/             # Spotify-API-Extraktor
│   ├── tunebat/             # Playwright + Stealth
│   ├── songstats/           # Playwright + BS4, Overview-Extraktion
│   ├── genius/              # Playwright + BS4, Lyrics & Credits
│   └── songbpm/             # Playwright + BS4, Vibe-Beschreibung
├── processor/               # 🏢 STANDORT 2: VERARBEITUNG
│   ├── importer.py          # process_queue() liest data/queue/ → DBs
│   ├── songs_db.py          # Lokale SQLite (data/songs.db)
│   └── external_db.py       # Schreibzugriff auf externe SQLite-DB (BEATBASE_DB_PATH)
└── shared/                  # 🚚 LOGISTIK
    ├── config.py            # Pfade, IPC, Polling, ENABLE_*-Toggles
    ├── now_playing.py       # IPC-Layer (file oder env)
    └── utils/
        ├── log.py               # Stderr-Logger
        ├── validator.py         # Zentrales Fuzzy-Match-Scoring
        ├── search_variations.py # Generierung von Suchbegriff-Variationen
        └── cookie_manager.py    # Zentrales Cookie-Banner-Handling
```

## Persistenz-Stellen (drei lokale DBs/Pfade + eine externe)

Nicht verwechseln — Beatbase schreibt an mehrere Stellen parallel:

- **`data/json/{track_id}.json`** — JSON-Archiv pro Song, Default-Output des Watchers.
- **`data/songs.db`** (`core/songs_db.py`) — lokale SQLite, vom Watcher pro Songwechsel
  befüllt. Flache Tabelle mit allen Summary-Feldern (Lyrics/Tracklist/Credits als
  JSON-Strings). Track-ID ist Primärschlüssel; bestehende Einträge werden überschrieben.
- **`data/tunebat_searches.db`** (`tunebat/db.py`) — lokale SQLite mit rohen
  Tunebat-Suchergebnissen. Append-only: eine Zeile pro Treffer, mit
  `searched_at`-Zeitstempel.
- **`data/tunebat_searches/<query>.html`** — optionale Roh-HTML-Dumps der
  Tunebat-Suchergebnisseite. Toggle: `SAVE_TUNEBAT_HTML` in `core/config.py`.
- **`BEATBASE_DB_PATH`** (Default `C:/workspace/beatbase/spotify.db`) — **externe**
  SQLite, nur über den `--track-id`-Workflow bei Songstats geschrieben
  (`core/db.py::update_audio_features`). Gehört nicht zum Repo, sondern zu einem
  übergeordneten System.

Alle `data/`-Pfade sind in `.gitignore`.

## Schnellstart

```powershell
# Setup
uv sync
uv run playwright install chromium

# .env mit SPOTIPY_CLIENT_ID und SPOTIPY_CLIENT_SECRET anlegen

# Watcher starten
uv run python -m beatbase

# Watcher beenden (von woanders)
uv run python -m beatbase --stop
```

Mehr Details findest du in [Getting Started](getting-started.md).
