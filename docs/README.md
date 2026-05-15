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
- SongBPM — Playwright + BS4, Vibe-Beschreibung (siehe [CLI](cli.md))

### Mitwirken

- [Entwicklung](development.md) — Coding-Konventionen, Linting, Tests
- [Troubleshooting](troubleshooting.md) — Bekannte Probleme und Lösungen

## Projektstruktur (Quellbaum)

```
src/beatbase/
├── __main__.py              # Entry Point → Watcher mit PID-File-Singleton
├── core/
│   ├── config.py            # IPC, Polling, ENABLE_*-Toggles, BEATBASE_DB_PATH
│   ├── watcher.py           # Polling-Loop + deklarative EXTRACTORS-Pipeline
│   ├── hotline.py           # Globaler Daten-Bus (Hotline)
│   └── db.py                # Schreibzugriff auf externe SQLite-DB
├── spotify/
│   └── spotify_current.py   # Spotify-API-Extraktor
├── tunebat/
│   ├── tunebat.py           # CLI + search_on_tunebat()
│   ├── config.py            # Tunebat-Konstanten
│   ├── browser/             # Playwright + Stealth, Navigation, Profile-Warmup
│   └── scraper/             # Datenextraktion von der Song-Seite
├── songstats/
│   ├── songstats.py         # CLI + search_on_songstats()
│   ├── config.py            # Songstats-Konstanten
│   ├── browser/             # Playwright-Kontext, Navigation
│   └── scraper/             # Overview-Extraktion
├── genius/
│   ├── genius.py            # CLI + search_on_genius()
│   ├── config.py            # Genius-Konstanten
│   ├── browser/             # Playwright-Kontext, Navigation
│   └── scraper/             # BeautifulSoup-Extraktion (Lyrics, Credits)
├── songbpm/
│   ├── songbpm.py           # CLI + search_on_songbpm()
│   └── scraper/             # Vibe-Beschreibung
└── utils/
    ├── callcenter.py        # Daten-Aggregation mit deklarativem Schema
    ├── now_playing.py       # IPC-Layer (file oder env)
    ├── log.py               # Stderr-Logger
    ├── cookie_manager.py    # Zentrales Cookie-Banner-Handling
    ├── validator.py         # Zentrales Fuzzy-Match-Scoring
    └── search_variations.py # Generierung von Suchbegriff-Variationen
```

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
