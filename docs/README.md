# Beatbase — Dokumentation

Willkommen in der technischen Dokumentation von **Beatbase**, einem Aggregator für
Musik-Metadaten. Beatbase erkennt den aktuell spielenden Spotify-Track und sammelt
parallel Daten aus **Spotify** (API), **Songstats** (Playwright-Scraper) und
**Genius** (Selenium-Scraper).

## Übersicht

```
Spotify API ─┐
             ├─► Hotline (bus) ──► Callcenter ──► Strukturierte Song-Daten
Songstats ───┤
Genius ──────┘
```

Ein zentraler **Watcher** pollt Spotify in einem festen Intervall, erkennt
Songwechsel über die Track-ID und triggert die Browser-Extraktoren. Rohdaten
landen im **Hotline**-Bus; das **Callcenter** baut daraus eine strukturierte
Zusammenfassung. Standalone-Aufrufe der Extraktoren sind ebenfalls möglich,
sie greifen über einen **IPC-Layer** auf den aktuell spielenden Song zu.

## Inhaltsverzeichnis

### Einstieg

- [Getting Started](getting-started.md) — Installation, `.env`, erste Ausführung
- [CLI-Referenz](cli.md) — Alle Aufrufe von Watcher und Extraktoren
- [Konfiguration](configuration.md) — Einstellbare Parameter

### Architektur

- [Architekturüberblick](architecture.md) — Designentscheidungen, Datenfluss
- [Watcher](modules/watcher.md) — Zentraler Polling-Loop
- [Hotline & Callcenter](modules/hotline-callcenter.md) — Bus-Pattern
- [IPC-Layer](modules/ipc.md) — Datei- oder Env-basierte Kommunikation

### Extraktoren

- [Spotify](modules/spotify.md) — API-Zugriff via `spotipy`
- [Songstats](modules/songstats.md) — Playwright-Scraper mit Highcharts-Maus-Trick
- [Genius](modules/genius.md) — Selenium-Scraper mit BeautifulSoup-Parsing

### Mitwirken

- [Entwicklung](development.md) — Coding-Konventionen, Linting, Tests
- [Troubleshooting](troubleshooting.md) — Bekannte Probleme und Lösungen

## Projektstruktur (Quellbaum)

```
src/beatbase/
├── __main__.py              # Entry Point → startet den Watcher
├── core/
│   ├── config.py            # IPC-Mode, Polling, Sentinel
│   ├── watcher.py           # Zentraler Polling-Loop
│   ├── hotline.py           # Globaler Daten-Bus
│   └── db.py                # Schreibzugriff auf externe SQLite-DB
├── spotify/
│   └── spotify_current.py   # Spotify-API-Extraktor
├── songstats/
│   ├── songstats.py         # CLI + search_on_songstats()
│   ├── config.py            # Songstats-Konstanten
│   ├── validator.py         # Match-Scoring
│   ├── browser/             # Playwright-Kontext & Navigation
│   └── scraper/             # DOM-Extraktion (Overview, Metrics, Platforms)
├── genius/
│   ├── genius.py            # CLI + search_on_genius()
│   ├── config.py            # Genius-Konstanten
│   ├── browser/             # Selenium-Kontext & Navigation
│   └── scraper/             # BeautifulSoup-Extraktion
└── utils/
    ├── callcenter.py        # Daten-Aggregation
    ├── now_playing.py       # IPC-Layer
    ├── log.py               # Stderr-Logger
    └── search_variations.py # Suchbegriff-Generierung
```

## Schnellstart

```powershell
# Setup
uv sync
uv run playwright install chromium

# .env mit SPOTIPY_CLIENT_ID und SPOTIPY_CLIENT_SECRET anlegen

# Watcher starten
uv run python -m beatbase
```

Mehr Details findest du in [Getting Started](getting-started.md).
