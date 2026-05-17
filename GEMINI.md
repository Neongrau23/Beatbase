# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

## Sprache

Antworte standardmäßig auf **Deutsch**. Code, Dateinamen und CLI-Befehle bleiben Englisch.

## Befehle

Das Projekt wird mit `uv` verwaltet (kein `pip`, kein manuelles `venv`).

```powershell
# Setup
uv sync
uv run playwright install chromium

# Watcher (Orchestrator) – pollt Spotify und triggert alle Extraktoren bei Songwechsel
uv run python -m beatbase                # Startet den Watcher (Singleton via .beatbase.pid)
uv run python -m beatbase --stop         # Beendet einen laufenden Watcher
uv run python -m beatbase --headless     # Watcher ohne sichtbares Browser-Fenster

# Einzelne Extraktoren (alle fallen auf den IPC-Layer zurück, wenn keine Args)
uv run python -m beatbase.spotify.spotify_current
uv run python -m beatbase.songstats.songstats --song "Titel" --artist "Name" [--headless] [--track-id ID]
uv run python -m beatbase.genius.genius "Interpret Titel" [--headless]
uv run python -m beatbase.tunebat.tunebat --song "Titel" --artist "Name" [--headless] [--dev]
uv run python -m beatbase.songbpm.songbpm "Titel"

# Tunebat-Profil "warmlaufen" lassen (manuelle Aktivität gegen Bot-Detection)
uv run python -m beatbase.tunebat.browser.warm_profile

# Lint
uv run ruff check .
uv run ruff check . --fix

# Tests
uv run pytest                        # alle Tests (~0.4s)
uv run pytest tests/utils/           # nur ein Subtree
uv run pytest -k callcenter          # nach Namen filtern
uv run pytest -m "not integration"   # Integration-Tests ausschliessen
```

Pytest-Konfig in `pyproject.toml` (`[tool.pytest.ini_options]`, `--import-mode=importlib`). Struktur in `tests/` spiegelt `src/`; HTML-Fixtures unter `tests/fixtures/<modul>/`. Globaler Bus wird per autouse-Fixture in `tests/conftest.py` vor jedem Test gecleart. Marker `integration` für Netz-/Browser-Tests (aktuell nicht benutzt).

`--track-id` bei Songstats schreibt Audio-Features via `core/db.py::update_audio_features` direkt in eine **externe** SQLite-DB. Pfad steht in `BEATBASE_DB_PATH` (Default `C:/workspace/beatbase/spotify.db`, via Env-Var überschreibbar). Die DB gehört zu einem übergeordneten System, nicht zum Repo.

## Architektur

### Hotline / Callcenter-Muster
Zweistufiger Datenfluss, der Extraktoren von der finalen Datenstruktur entkoppelt:

- **Hotline** (`core/hotline.py`): Globaler Key-Value-Speicher `bus` (Singleton). Extraktoren legen Rohdaten unter ihrem Quellennamen ab (`bus.set("songstats", key, value)`). Keine Logik, kein Schema.
- **Callcenter** (`utils/callcenter.py`): Liest aus `bus.get_all()` und baut die strukturierte Master-View (`build_song_summary()`). Hier liegt die Priorisierungslogik — z. B. nimmt `release_date` bevorzugt aus Tunebat, dann Spotify, dann Songstats; mit `_determine_release_date()` als letztem Fallback (ältestes Datum aller Quellen).

Ein neuer Extraktor muss nur `bus.set(quelle, key, value)` aufrufen — die Aggregation passiert im Callcenter. Das Callcenter gibt ein **festes Schema** mit den Blöcken `meta`, `music_theory`, `audio_features`, `analysis`, `lyrics`, `album_tracklist`, `credits`, `links` aus. Neue Felder dort eintragen.

### Watcher-Loop (`core/watcher.py`)
Zentraler Polling-Loop. Pollt Spotify in `POLLING_INTERVAL` (Default 10s), erkennt Songwechsel über die Spotify-Track-ID. Die Pipeline ist als **deklarative `EXTRACTORS`-Liste** (`list[ExtractorSpec]`) definiert — neue Quellen werden durch Anhängen eines `ExtractorSpec` integriert, nicht durch If-Kaskaden.

Pro Songwechsel:

1. `bus.clear()` (Hotline-Reset)
2. IPC-Layer aktualisieren (`write_now_playing`)
3. Spotify-Rohdaten in Hotline pushen
4. **Ein gemeinsamer Playwright-Browser-Kontext** wird geöffnet und an alle Extraktoren weitergereicht
5. Reihenfolge: Tunebat → Songstats → Genius → SongBPM. Jeder Schritt in eigenem try/except — Fehler eines Extraktors stoppen den Watcher nicht
6. **Cross-Extractor-Optimierung** über `ExtractorSpec.direct_url_from`: Tunebat findet einen `songstats_url`-Direktlink und legt ihn in der Hotline ab. Der Songstats-Spec deklariert `direct_url_from=("tunebat", "songstats_url")`; der Watcher reicht den Wert als `direct_url`-Kwarg durch, Songstats überspringt damit seine eigene Suche
7. `get_summary_json()` ausgeben, nach `JSON_EXPORT_DIR/{track_id}.json` archivieren **und** zusätzlich via `core/songs_db.py::save_song_summary` in die lokale SQLite-DB `data/songs.db` schreiben (eine flache Tabelle mit Track-ID als Primary Key)
8. Browser-Kontext schließen

**Wichtig:** Der Watcher steuert den Browser-Lifecycle zentral. Die `search_on_*`-Funktionen akzeptieren ein optionales `page`-Argument; wird es gesetzt, verwalten sie keinen eigenen Browser. Standalone-CLI-Aufrufe öffnen weiterhin ihren eigenen Kontext über das jeweilige `browser/context.py`.

Welche Extraktoren laufen, wird in `core/config.py` per Toggle gesteuert (`ENABLE_GENIUS`, `ENABLE_SONGSTATS`, `ENABLE_TUNEBAT`, `ENABLE_SONGBPM`).

Der Watcher schreibt eine **PID-Datei** (`.beatbase.pid`) zum Singleton-Schutz und um `--stop` zu ermöglichen.

### Persistenz-Stellen (drei verschiedene DBs/Pfade — nicht verwechseln!)
- **`data/json/{track_id}.json`** — JSON-Archiv pro Song, Default-Output des Watchers.
- **`data/songs.db`** (`core/songs_db.py`) — lokale SQLite, vom Watcher pro Song befüllt. Flache Tabelle mit allen Summary-Feldern (Lyrics/Tracklist/Credits als JSON-Strings).
- **`data/tunebat_searches.db`** (`tunebat/db.py`) — lokale SQLite mit rohen Tunebat-Suchergebnissen (eine Zeile pro Treffer, mit `searched_at`). Append-only.
- **`BEATBASE_DB_PATH`** (Default `C:/workspace/beatbase/spotify.db`) — **externe** DB für `core/db.py::update_audio_features`, nur über den `--track-id`-Workflow geschrieben. Gehört zu einem übergeordneten System.

### IPC-Layer (`utils/now_playing.py`)
Entkoppelt Extraktoren, die standalone laufen können. Modus in `core/config.py::IPC_MODE`:

- `"file"` (Default): `now_playing.txt` im CWD, **atomar geschrieben** (temp + `os.replace`) gegen Partial-Reads.
- `"env"`: Windows-User-Env `NOW_PLAY`, gelesen/geschrieben über PowerShell-Subprozesse.

Sentinel `"nothing..."` (`SENTINEL_NONE`) bedeutet "kein Track aktiv". Format des Songstrings: `"<Title> von <Artist1>, <Artist2>"`. Standalone-Extraktoren nutzen ihn als Suchbegriff-Fallback, wenn keine CLI-Args mitgegeben werden.

### Extraktor-Typen
Alle Browser-Extraktoren nutzen **Playwright Chromium** mit persistenten Profilen unter `.profiles/`. Die Profile-Verzeichnisse werden beim ersten Start angelegt, sind in `.gitignore` und **dürfen nicht gelöscht werden** (Cookies, Login-State, Anti-Bot-Reputation).

- **Spotify** (`spotify/`): Reine HTTP-Requests via `spotipy`, OAuth-Token in `.spotify_cache` neben dem Modul.
- **Songstats** (`songstats/`): Playwright + BeautifulSoup. Extrahiert Highcharts-SVG-Daten via Mausbewegungen auf Koordinaten, da die SVGs keine semantischen Klassen haben. Fokus liegt aktuell auf der `Overview`-Sektion (`scraper/overview.py`).
- **Genius** (`genius/`): **Playwright** (nicht mehr Selenium) + BeautifulSoup. Extrahiert Lyrics, Album-Tracklist und Credits.
- **Tunebat** (`tunebat/`): Playwright + **`playwright-stealth`** für Bot-Detection-Umgehung. Liefert BPM, Key, Camelot, Audio-Features. Findet zusätzlich Direktlinks zu Songstats und legt sie für den nächsten Extraktor ab. Bei hartnäckiger Bot-Detection: `python -m beatbase.tunebat.browser.warm_profile` ausführen, um das Profil mit Klick- und Scroll-Aktivität anzureichern.
- **SongBPM** (`songbpm/`): Playwright + BeautifulSoup. Liefert die "Vibe"-Beschreibung des Tracks.

Jeder Browser-Extraktor folgt dem Submodul-Pattern:
- `browser/context.py` — Playwright-Kontext-Setup mit persistentem Profil
- `browser/navigator.py` — Suche & Resultatsauswahl
- `scraper/extractor.py` (oder `scraper/overview.py`/`scraper/coordinator.py`) — Datenextraktion aus dem geladenen DOM
- `<modul>.py` — `search_on_<modul>()`-Orchestrator + CLI-Einsprung

### Gemeinsame Utilities
- `utils/search_variations.py::generate_variations()`: Generische Variations-Generierung (Reihenfolge, Klammern, Featured-Artists, Remix/Edit-Tags, Unicode-Normalisierung). Wird von Songstats, Genius und Tunebat verwendet.
- `utils/search_variations.py::extract_featured_artists()`: Zieht versteckte Künstler aus dem Titel (`feat.`, `ft.`, `with`, `von`).
- `utils/cookie_manager.py::wait_for_and_dismiss_cookies()`: Zentrales Cookie-Banner-Handling für alle Browser-Extraktoren (OneTrust, deutsche/englische Buttons).
- `utils/validator.py::calculate_validation_score()`: Zentrales Fuzzy-Matching-Scoring (`difflib` + Artist-Bonus + Remix-Bonus) für Suchergebnisbewertung.
- `utils/log.py::log_status()`: Schreibt nach **stderr**. Stdout bleibt frei für die strukturierten JSON-Ausgaben der CLIs — wichtig, wenn die CLIs gepiped werden. Nutze `log_status()`, kein `print()`, für Statusmeldungen.

## Code-Konventionen

- **`# DEF: Kurztext`** (max ~40 Zeichen) markiert wichtige Funktionen/Sektionen und erscheint in der VSCode-Minimap. Auch `# SECTION:`, `# ENTRY:`, `# CONFIG:`, `# BRIDGE:`, `# STATE:`, `# WHY:`, `# HELP:`, `# MARK:` werden im Codebase verwendet.
- Type Hints überall. Google-Style-Docstrings. f-Strings. `pathlib.Path` (wo möglich — der Bestandscode nutzt teils `os.path`).
- Spezifische Exceptions fangen, kein nacktes `except:`. **Ausnahme:** `_run_extractor` in `core/watcher.py` — dort ist `except Exception` bewusst breit, damit ein Scraper-Crash die Pipeline nicht killt.
- `search_on_*`-Funktionen liefern **`dict | None`** — `None` bei Fehler oder leerem Ergebnis. Keine `{}`-Sentinels.
- Zeilenlänge 100, `target-version = "py311"`, Linter ist Ruff (`select = ["E", "F", "I"]`).
- Commit-Konvention: `type(scope): kurze beschreibung` auf Deutsch. Aufbau:

  ```
  type(scope): kurze zusammenfassung (Imperativ, Deutsch, max ~72 Zeichen)
  <Leerzeile>
  Erklaerung WARUM die Aenderung noetig war und was sich konkret
  aendert. Kein Nacherzaehlen des Diffs — der steht im Code.

  datei/oder/modul.py           (optionale Sektion pro Datei/Gruppe)
  -------------------
  - Was geaendert wurde und warum (max ~60 Zeichen pro Zeile).
  - Umlaute ausschreiben: ae / oe / ue / ss.
  ```

  Erlaubte Typen: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
  Scope ist der Modulname (z. B. `tunebat`, `core`, `utils`) oder leer.

## Konfiguration

- `.env` im Projektroot: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, optional `SPOTIPY_REDIRECT_URI`.
- `src/beatbase/core/config.py`: Watcher- und IPC-Defaults (`POLLING_INTERVAL`, `IPC_MODE`, `WATCHER_HEADLESS`, `SENTINEL_NONE`, `ENABLE_*`-Toggles, `JSON_EXPORT_DIR`, `SAVE_TUNEBAT_HTML`, Quellen-URLs).
- `src/beatbase/{songstats,genius,tunebat}/config.py`: Quellen-spezifische Konstanten (`MATCH_THRESHOLD`, `PROFILE_DIR`, `USER_AGENT`, Timeouts, Headless-Default).
- `BEATBASE_DB_PATH` (Env-Var oder `core/config.py`-Default) → externer SQLite-Pfad für den `--track-id`-Workflow. Default `C:/workspace/beatbase/spotify.db`.