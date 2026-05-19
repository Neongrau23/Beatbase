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

# Watcher + Importer (Default-Modus): pollt Spotify, scrapet, schreibt in Queue
# und ruft den Importer synchron auf.
uv run python -m beatbase                # Watcher + Importer (Singleton via .beatbase.pid)
uv run python -m beatbase --stop         # Beendet einen laufenden Watcher
uv run python -m beatbase --headless     # Watcher ohne sichtbares Browser-Fenster

# Standorte einzeln starten
uv run python -m beatbase extract        # Nur Spotify-Watcher (schreibt in Queue)
uv run python -m beatbase process        # Nur Importer (Queue → DBs, einmaliger Lauf)

# Batch-Modus: Track-Liste ohne aktives Spotify abarbeiten
uv run python -m beatbase batch add tracks.csv          # CSV → data/search_queue.db
uv run python -m beatbase batch run [--limit N]         # alle pending Tracks scrapen
uv run python -m beatbase batch retry [--source NAME]   # 'fail:'-Statuus retryen
uv run python -m beatbase batch status                  # Zählung pro Quelle

# Einzelne Extraktoren (alle fallen auf den IPC-Layer zurück, wenn keine Args)
uv run python -m beatbase.extractor.spotify.spotify_current
uv run python -m beatbase.extractor.songstats.songstats --song "Titel" --artist "Name" [--headless]
uv run python -m beatbase.extractor.genius.genius "Interpret Titel" [--headless]
uv run python -m beatbase.extractor.tunebat.tunebat --song "Titel" --artist "Name" [--headless] [--dev]
uv run python -m beatbase.extractor.songbpm.songbpm "Titel"

# Tunebat-Profil "warmlaufen" lassen (manuelle Aktivität gegen Bot-Detection)
uv run python -m beatbase.extractor.tunebat.browser.warm_profile

# Lint
uv run ruff check .
uv run ruff check . --fix

# Tests
uv run pytest                        # alle Tests (~1s)
uv run pytest tests/shared/          # nur ein Subtree
uv run pytest -k callcenter          # nach Namen filtern
uv run pytest -m "not integration"   # Integration-Tests ausschliessen
```

Pytest-Konfig in `pyproject.toml` (`[tool.pytest.ini_options]`, `--import-mode=importlib`). Struktur in `tests/` spiegelt `src/` (`tests/extractor/`, `tests/processor/`, `tests/shared/`); HTML-Fixtures unter `tests/fixtures/<modul>/`. Globaler Bus wird per autouse-Fixture in `tests/conftest.py` vor jedem Test gecleart. Marker `integration` für Netz-/Browser-Tests (aktuell nicht benutzt).

## Architektur

Das Paket ist in drei **Standorte** geteilt — jeder Standort hat seine eigene Verantwortlichkeit, die Naht dazwischen ist die JSON-Queue.

### Standort 1: `extractor/` (Beschaffung)
Alles, was Daten von externen Quellen einsammelt und zu einer fertigen Master-View aggregiert.

- `extractor/orchestrator.py` — zentraler Polling-Loop. Pollt Spotify in `POLLING_INTERVAL` (Default 10s), erkennt Songwechsel über die Spotify-Track-ID. Die Pipeline ist als **deklarative `EXTRACTORS`-Liste** (`list[ExtractorSpec]`) definiert.
- `extractor/hotline.py` — interner Key-Value-Bus (`bus`-Singleton). Extraktoren legen Rohdaten unter ihrem Quellennamen ab (`bus.set("songstats", key, value)`). Keine Logik, kein Schema.
- `extractor/callcenter.py` — schema-getriebene Aggregation. Liest aus `bus.get_all()` und baut die strukturierte Master-View (`build_song_summary()`). Hier liegt die Priorisierungslogik — z. B. nimmt `release_date` bevorzugt aus Tunebat, dann Spotify, dann Songstats; mit `_determine_release_date()` als letztem Fallback (ältestes Datum aller Quellen).
- `extractor/queue.py` — `write_to_queue(track_id, summary)` legt das fertige JSON in `data/queue/` ab. Das ist die einzige Schnittstelle zu Standort 2.
- `extractor/{spotify,tunebat,songstats,genius,songbpm}/` — die einzelnen Quellen-Scraper.

**Watcher-Loop pro Songwechsel:**
1. `bus.clear()` (Hotline-Reset)
2. IPC-Layer aktualisieren (`write_now_playing`)
3. Spotify-Rohdaten in Hotline pushen
4. **Ein gemeinsamer Playwright-Browser-Kontext** wird geöffnet und an alle Extraktoren weitergereicht
5. Reihenfolge: Tunebat → Songstats → Genius → SongBPM. Jeder Schritt in eigenem try/except — Fehler eines Extraktors stoppen den Watcher nicht
6. **Cross-Extractor-Optimierung** über `ExtractorSpec.direct_url_from`: Tunebat findet einen `songstats_url`-Direktlink und legt ihn in der Hotline ab. Der Songstats-Spec deklariert `direct_url_from=("tunebat", "songstats_url")`; der Watcher reicht den Wert als `direct_url`-Kwarg durch, Songstats überspringt damit seine eigene Suche
7. `get_summary_json()` ausgeben → `write_to_queue(track_id, summary)` → `process_queue()` synchron aufrufen
8. Browser-Kontext schließen

**Wichtig:** Der Orchestrator steuert den Browser-Lifecycle zentral. Die `search_on_*`-Funktionen akzeptieren ein optionales `page`-Argument; wird es gesetzt, verwalten sie keinen eigenen Browser. Standalone-CLI-Aufrufe öffnen weiterhin ihren eigenen Kontext über das jeweilige `browser/context.py`.

### Batch-Modus: `extractor/batch.py` + `extractor/search_queue.py`

Alternative zum Spotify-Polling für Backfill-Szenarien (Playlist, DJ-Set, Bestands­anreicherung). Eigene Tracking-DB `data/search_queue.db` mit Status pro Quelle:

- `add`: CSV einlesen (`id,song,artist[,isrc,release_date]`, `;` trennt mehrere Künstler, leere `id` wird via `search_queue.generate_id` zu einem 22-stelligen MD5-Hash).
- `run`: alle Tracks mit mindestens einer `NULL`-Status-Spalte durch die Pipeline schicken (gleicher Queue/Importer-Pfad nach `songs.db` wie der Watcher).
- `retry [--source X]`: setzt `fail:%`-Statuus auf `NULL` zurück und ruft `run` auf. `no_match` bleibt unangetastet — Tracks, die in einer Quelle wirklich nicht existieren, werden nicht endlos retryed.

`_run_extractor()` in `orchestrator.py` liefert `"ok"` / `"no_match"` / `"fail: <Klasse>: <msg>"`; `handle_new_track()` / `handle_new_track_parallel()` geben `dict[str, str]` zurück. Der Spotify-Watcher ignoriert den Return einfach.

**Pipeline-Auswahl in `batch.run()`:**

- `BATCH_PARALLEL=True` (Default): nutzt `extractor/parallel.py::handle_new_track_parallel` mit 2-Phasen-Pipeline:
  1. **Phase 1** (sequenziell): Tunebat solo, damit `songstats_url` (Cross-Extractor-Optimierung via `direct_url_from`) in der Hotline landet.
  2. **Phase 2** (parallel, `ThreadPoolExecutor(max_workers=3)`): Songstats, Genius, SongBPM.
  3. Sammelstelle wie bisher (`callcenter.build_song_summary()` → `write_to_queue()` → `process_queue()`) — erst wenn alle Phase-2-Futures fertig sind.
- `BATCH_PARALLEL=False`: sequenziell wie der Watcher (`orchestrator.handle_new_track`).

**In-Process-Retry** in beiden Phasen: liefert ein Extraktor `"fail: ..."`, wird er einmal nach `BATCH_RETRY_DELAY_SECONDS` (Default 5s) erneut versucht. `"no_match"` und `"ok"` werden nicht wiederholt.

**Browser-Pool** (`BATCH_REUSE_BROWSERS=True`, Default an) in `extractor/browser_pool.py`:

- Pro Quelle laeuft ein dedizierter Worker-Thread mit eigener `sync_playwright()`-Instanz (Thread-Affinitaet). Der Browser bleibt ueber den ganzen Batch-Lauf offen — kein Browser-Startup pro Track.
- `ExtractorWorker.submit(track) -> Future`: Tasks werden FIFO in der Queue des Workers abgelegt, Ergebnis kommt via `Future` zurueck.
- `BrowserPool.recycle()` nach `BATCH_RECYCLE_AFTER` Tracks (Default 50): alle Browser sauber zu, neu hochziehen — Memory-Hygiene fuer lange Laeufe. `0` deaktiviert das Recycle.
- **Crash-Recovery**: Schmeisst ein Extraktor `TargetClosedError` (siehe `shared/utils/playwright_errors.py`), zieht der Worker den Browser bis zu `BATCH_CRASH_MAX_RETRIES` Mal (Default 3) neu hoch und wiederholt die Suche. Andere Exceptions werden weiterhin als `"fail:"` durchgereicht.
- Profile-Lock-Konflikt: Watcher und Batch duerfen **nicht gleichzeitig** dasselbe persistente Profil benutzen.

### Lager: `data/queue/`
Ein Verzeichnis voller fertiger Song-JSONs (`{track_id}.json`). Die einzige Schnittstelle zwischen Standort 1 und 2. Wenn der Processor offline ist, stauen sich JSONs hier auf, bis er wieder läuft. Erfolgreich importierte JSONs wandern in `data/json/`.

### Standort 2: `processor/` (Verarbeitung)
Alles, was fertige JSONs in Datenbanken überführt.

- `processor/importer.py` — `process_queue()` arbeitet alle JSONs in `data/queue/` ab. Pro File: Summary lesen, `save_song_summary` (lokale DB), bei vorhandenen Audio-Features `update_audio_features` (externe DB), dann nach `data/json/` archivieren. Fehler isolieren pro File.
- `processor/songs_db.py` — `save_song_summary(track_id, summary)` schreibt in `data/songs.db` (lokale flache SQLite, eine Zeile pro Track).
- `processor/external_db.py` — `update_audio_features(track_id, features)` schreibt in die **externe** Beatbase-DB (`BEATBASE_DB_PATH`). Erwartet das Summary-Format mit Kleinbuchstaben-Keys; `happiness` wird auf die `valence`-Spalte gemappt.

Der Processor wird vom Orchestrator nach jedem Song synchron getriggert, kann aber auch standalone mit `python -m beatbase process` laufen — etwa wenn die Queue sich nach einem DB-Ausfall angestaut hat.

### Logistik: `shared/`
Alles, was beide Standorte brauchen.

- `shared/config.py` — Watcher-, IPC- und Pfad-Defaults. **Alle hartcodierten Pfade** (`DATA_DIR`, `QUEUE_DIR`, `SONGS_DB_PATH`, `SEARCH_QUEUE_DB_PATH`, `TUNEBAT_SEARCHES_DB_PATH`, `GENIUS_DB_PATH`, `SPOTIFY_CACHE_PATH`, `PID_FILE_PATH` etc.) leben hier und sind über `BEATBASE_DATA_DIR` / `BEATBASE_DB_PATH` per Env-Var überschreibbar.
- `shared/now_playing.py` — IPC-Layer (`now_playing.txt` oder Windows-Env, je nach `IPC_MODE`).
- `shared/utils/log.py`, `validator.py`, `search_variations.py`, `cookie_manager.py` — Hilfsfunktionen, die mehrere Module brauchen.

### Persistenz-Stellen
- **`data/queue/{track_id}.json`** — frisch gescrapete Summaries, die auf den Import warten. Naht zwischen Standort 1 und 2.
- **`data/json/{track_id}.json`** — Archiv erfolgreich importierter Summaries.
- **`data/songs.db`** (`processor/songs_db.py`) — lokale SQLite mit allen Summary-Feldern (Lyrics/Tracklist/Credits als JSON-Strings).
- **`data/search_queue.db`** (`extractor/search_queue.py`) — Batch-Tracking-Tabelle. Eine Zeile pro Track, Statusspalte pro Quelle (`NULL` / `"ok"` / `"no_match"` / `"fail: <msg>"`). Wird **nur** vom Batch-Modus geschrieben — der Spotify-Watcher fasst sie nicht an.
- **`data/tunebat_searches.db`** (`extractor/tunebat/db.py`) — Append-only-Log roher Tunebat-Suchergebnisse. Bleibt bewusst bei Tunebat (nicht im Processor), weil es Scraper-internes Audit-Log ist.
- **`data/genius.db`** (`extractor/genius/db.py`) — Append-only-Tabelle aller auf Artist-Songs-Seiten entdeckten Genius-Songs (`song`, `artist`, `genius_url` PK). Dedupliziert per URL via `INSERT OR IGNORE`; jeder Genius-Lookup fuellt sie weiter — bei Collabs werden **alle** im Song-Header verlinkten Artists abgegrast, nicht nur der Haupt-Künstler.
- **`data/.spotify_cache`** — OAuth-Token-Cache von spotipy. Wird beim ersten Auth-Flow angelegt.
- **`BEATBASE_DB_PATH`** (Default `C:/workspace/beatbase/spotify.db`) — externe DB, vom Importer befüllt, wenn Audio-Features im Summary stehen. Gehört zu einem übergeordneten System.

### IPC-Layer (`shared/now_playing.py`)
Entkoppelt Extraktoren, die standalone laufen können. Modus in `shared/config.py::IPC_MODE`:

- `"file"` (Default): `now_playing.txt` im CWD, **atomar geschrieben** (temp + `os.replace`) gegen Partial-Reads.
- `"env"`: Windows-User-Env `NOW_PLAY`, gelesen/geschrieben über PowerShell-Subprozesse.

Sentinel `"nothing..."` (`SENTINEL_NONE`) bedeutet "kein Track aktiv". Standalone-Extraktoren nutzen ihn als Suchbegriff-Fallback, wenn keine CLI-Args mitgegeben werden.

### Extraktor-Typen
Alle Browser-Extraktoren nutzen **Playwright Chromium** mit persistenten Profilen unter `.profiles/`. Die Profile-Verzeichnisse werden beim ersten Start angelegt, sind in `.gitignore` und **dürfen nicht gelöscht werden** (Cookies, Login-State, Anti-Bot-Reputation).

- **Spotify** (`extractor/spotify/`): Reine HTTP-Requests via `spotipy`, OAuth-Token in `data/.spotify_cache`.
- **Songstats** (`extractor/songstats/`): Playwright + BeautifulSoup. Extrahiert Highcharts-SVG-Daten via Mausbewegungen auf Koordinaten, da die SVGs keine semantischen Klassen haben. Fokus liegt aktuell auf der `Overview`-Sektion (`scraper/overview.py`).
- **Genius** (`extractor/genius/`): **Playwright** (nicht mehr Selenium) + BeautifulSoup. Extrahiert Lyrics, Album-Tracklist und Credits. **Such-Flow:** kombinierte Song+Artist-Queries (aus `generate_variations`) werden direkt in die Genius-Suche getippt, der beste Treffer aus den `mini-song-card`-Resultaten gewinnt (Score-Schwelle `MATCH_THRESHOLD`, Early-Exit bei ≥0.95, max. 3 Queries). Bei No-Match: kein Fallback, Lyrics-Stub und leere `artist_songs`. **Artist-Songs-Sammlung:** aus dem `SongHeader-desktop__CreditList`-Block werden alle beteiligten Artist-Profil-Links extrahiert; pro Artist wird sequenziell in einer neuen Page das Profil geladen, "Show all songs" geklickt und die komplette Songliste in `data/genius.db` geschrieben — über `COLLECT_ARTIST_SONGS=False` in `genius/config.py` komplett abschaltbar (Lyrics-Pfad läuft trotzdem).
- **Tunebat** (`extractor/tunebat/`): Playwright + **`playwright-stealth`** für Bot-Detection-Umgehung (via `USE_STEALTH`-Toggle in `tunebat/config.py` abschaltbar — bei einem echten/warmen Chrome-Profil ist Stealth eher kontraproduktiv). Liefert BPM, Key, Camelot, Audio-Features. Findet zusätzlich Direktlinks zu Songstats und legt sie für den nächsten Extraktor ab. Bei hartnäckiger Bot-Detection: `python -m beatbase.extractor.tunebat.browser.warm_profile` ausführen, um das Profil mit Klick- und Scroll-Aktivität anzureichern.
- **SongBPM** (`extractor/songbpm/`): Playwright + BeautifulSoup mit persistentem Profil (`.profiles/songbpm_profile`). Liefert die "Vibe"-Beschreibung des Tracks.

Jeder Browser-Extraktor folgt dem Submodul-Pattern:
- `browser/context.py` — Playwright-Kontext-Setup mit persistentem Profil
- `browser/navigator.py` — Suche & Resultatsauswahl
- `scraper/extractor.py` (oder `scraper/overview.py`/`scraper/coordinator.py`) — Datenextraktion aus dem geladenen DOM
- `<modul>.py` — `search_on_<modul>()`-Orchestrator + CLI-Einsprung

### Gemeinsame Utilities
- `shared/utils/search_variations.py::generate_variations()`: Generische Variations-Generierung (Reihenfolge, Klammern, Featured-Artists, Remix/Edit-Tags, Unicode-Normalisierung). Wird von Songstats, Genius und Tunebat verwendet.
- `shared/utils/search_variations.py::extract_featured_artists()`: Zieht versteckte Künstler aus dem Titel (`feat.`, `ft.`, `with`, `von`).
- `shared/utils/cookie_manager.py::wait_for_and_dismiss_cookies()`: Zentrales Cookie-Banner-Handling für alle Browser-Extraktoren (OneTrust, deutsche/englische Buttons).
- `shared/utils/validator.py::calculate_validation_score()`: Zentrales Fuzzy-Matching-Scoring (`difflib` + Artist-Bonus + Remix-Bonus) für Suchergebnisbewertung.
- `shared/utils/log.py::log_status()`: Schreibt nach **stderr**. Stdout bleibt frei für die strukturierten JSON-Ausgaben der CLIs — wichtig, wenn die CLIs gepiped werden. Nutze `log_status()`, kein `print()`, für Statusmeldungen.
- `shared/utils/playwright_errors.py::is_browser_closed_error()`: Erkennt `TargetClosedError` plus generische `PlaywrightError`-Messages mit "Target page, context or browser has been closed". Wird in den `search_on_*`-Funktionen genutzt, um Browser-Crashes vom Pool-Worker abfangen zu lassen statt sie als `no_match` zu interpretieren.

## Code-Konventionen

- **`# DEF: Kurztext`** (max ~40 Zeichen) markiert wichtige Funktionen/Sektionen und erscheint in der VSCode-Minimap. Auch `# SECTION:`, `# ENTRY:`, `# CONFIG:`, `# BRIDGE:`, `# STATE:`, `# WHY:`, `# HELP:`, `# MARK:` werden im Codebase verwendet.
- Type Hints überall. Google-Style-Docstrings. f-Strings. `pathlib.Path` (wo möglich — der Bestandscode nutzt teils `os.path`).
- Spezifische Exceptions fangen, kein nacktes `except:`. **Ausnahme:** `_run_extractor` in `extractor/orchestrator.py` — dort ist `except Exception` bewusst breit, damit ein Scraper-Crash die Pipeline nicht killt. Ebenso im `processor/importer.py` pro File, damit ein kaputtes JSON nicht den ganzen Importer-Lauf stoppt.
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

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```

  Erlaubte Typen: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
  Scope ist der Modulname (z. B. `tunebat`, `extractor`, `processor`, `shared`) oder leer.

## Konfiguration

- `.env` im Projektroot: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, optional `SPOTIPY_REDIRECT_URI`.
- `src/beatbase/shared/config.py`: Watcher-, IPC-, Batch- und alle Pfad-Defaults.
  - Watcher/IPC: `POLLING_INTERVAL`, `IPC_MODE`, `WATCHER_HEADLESS`, `SENTINEL_NONE`, `ENABLE_*`-Toggles.
  - Batch-Modus: `BATCH_PARALLEL` (2-Phasen-Pipeline an/aus), `BATCH_HEADLESS` (Headless im Batch-Pfad), `BATCH_RETRY_DELAY_SECONDS` (Wartezeit fuer In-Process-Retry), `BATCH_REUSE_BROWSERS` (Browser-Pool an/aus), `BATCH_RECYCLE_AFTER` (Auto-Recycle nach N Tracks), `BATCH_CRASH_MAX_RETRIES` (Browser-Restart-Versuche bei `TargetClosedError`).
  - Pfade: `DATA_DIR`, `QUEUE_DIR`, `JSON_EXPORT_DIR`, `SONGS_DB_PATH`, `SEARCH_QUEUE_DB_PATH`, `TUNEBAT_SEARCHES_DB_PATH`, `TUNEBAT_SEARCHES_HTML_DIR`, `GENIUS_DB_PATH`, `SPOTIFY_CACHE_PATH`, `PID_FILE_PATH`, `SAVE_TUNEBAT_HTML`, Quellen-URLs.
- `src/beatbase/extractor/{songstats,genius,tunebat}/config.py`: Quellen-spezifische Konstanten (`MATCH_THRESHOLD`, `PROFILE_DIR`, `USER_AGENT`, Timeouts, Headless-Default). Tunebat zusaetzlich `USE_STEALTH` (an/aus fuer `playwright-stealth`). Genius zusaetzlich `COLLECT_ARTIST_SONGS` (an/aus fuer die per-Artist-Songs-Sammlung in `genius.db`).
- `BEATBASE_DATA_DIR` (Env-Var) → überschreibt den `data/`-Pfad für die Queue, JSON-Archive und lokalen DBs.
- `BEATBASE_DB_PATH` (Env-Var oder `shared/config.py`-Default) → externer SQLite-Pfad für `processor/external_db.py`. Default `C:/workspace/beatbase/spotify.db`.
