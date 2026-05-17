# Architekturüberblick

Dieses Dokument beschreibt die Designentscheidungen und Muster hinter Beatbase.
Die einzelnen Komponenten sind in [`modules/`](modules/) im Detail dokumentiert.

## Designziele

1. **Quellenagnostische Aggregation.** Spotify, Tunebat, Songstats, Genius und
   SongBPM haben unterschiedliche Schemas und Datenqualität. Beatbase soll Daten
   überlappungsfrei mergen können, ohne dass die Extraktoren das Zielschema
   kennen müssen.
2. **Fehler-Isolation.** Ein abgestürzter Scraper darf den Watcher nicht
   anhalten.
3. **Standalone-fähig.** Jeder Extraktor muss auch ohne Watcher laufen.
4. **Lokal nutzbar.** Keine Server-Komponente, keine Cloud, kein Dauerlauf
   nötig — auf einer Maschine, in einem Prozess.

## Datenfluss

```
┌──────────────────┐
│ Spotify Polling  │  ← extractor/orchestrator.py (Default 10s)
└────────┬─────────┘
         │ Songwechsel?
         ▼
┌──────────────────┐
│  bus.clear()     │  ← extractor/hotline.py
│  write_now_play  │  ← shared/now_playing.py (IPC für Standalone-Aufrufe)
└────────┬─────────┘
         │
   ┌─────┴─────────────────────────┐
   ▼  (geteilter Browser-Kontext)  ▼
┌──────────────────────────────────┐
│ Pipeline (EXTRACTORS-Liste):     │
│   Tunebat → Songstats → Genius   │
│        → SongBPM                 │
└────────────────┬─────────────────┘
                 │
   bus.set(source, key, value) für jeden Extraktor
                 │
                 ▼
        ┌────────────────────┐
        │ build_song_summary │  ← extractor/callcenter.py
        │ (deklaratives      │
        │  Master-Schema)    │
        └────────────────────┘
                 │
                 ▼
        data/json/{track_id}.json
```

## Das Hotline/Callcenter-Muster

Beatbase nutzt einen zweistufigen Datenfluss, der Extraktoren von der finalen
Datenstruktur entkoppelt.

### Hotline (`extractor/hotline.py`)

Ein globaler, unstrukturierter Key-Value-Speicher (`bus`). Jeder Extraktor legt
seine Rohdaten unter seinem Quellennamen ab:

```python
bus.set("songstats", "Genres", "Synth-pop, Pop")
bus.set("tunebat", "bpm", "171")
bus.set("spotify", "isrc", "USUG11904206")
```

Die Hotline kennt kein Schema. Sie ist reine Ablage.

**Warum?** Wenn ein neuer Extraktor hinzukommt, muss er das finale Song-Objekt
nicht kennen. Er schreibt einfach alles in den Bus, was er hat. Die Hotline
wird beim Songwechsel über `bus.clear()` geleert.

### Callcenter (`extractor/callcenter.py`)

Die Logik-Schicht. Liest aus `bus.get_all()` und baut strukturierte Views nach
einem **deklarativen Schema**: Pro Feld wird eine geordnete Liste von Quellen
deklariert, aus der die erste nicht-leere Quelle gewinnt.

```python
META = {
    "title": FieldSpec(sources=(
        Source("spotify", "name"),
        Source("songstats", "Title"),
        Source("tunebat", "title"),
    )),
    "release_date": FieldSpec(
        sources=(
            Source("tunebat", "release_date"),
            Source("spotify", "release_date"),
            Source("songstats", "Release Date"),
        ),
        fallback=_determine_release_date,  # ältestes Datum aus allen Quellen
    ),
    ...
}
```

Hier liegt die **Priorisierungslogik**: Welche Quelle hat Vorrang bei welchem
Feld, wie werden Konflikte aufgelöst.

Details: [`modules/hotline-callcenter.md`](modules/hotline-callcenter.md).

## Der Watcher-Loop und Batch-Modus

`extractor/orchestrator.py` ist der zentrale Orchestrator. Es gibt zwei Einstiegspunkte:

1. **Spotify Watcher (`__main__.py`):** Pollt Spotify alle 10s und triggert `handle_new_track()` bei Songwechsel.
2. **Batch-Modus (`extractor/batch.py`):** Liest Tracks aus `data/search_queue.db` und triggert `handle_new_track()` für jeden anstehenden Track, um gezielt große Mengen abzuarbeiten.

Der Ablauf in `handle_new_track(track)`:
- `bus.clear()` — Hotline reseten.
- `write_now_playing(...)` — IPC-Layer aktualisieren.
- **Einen** Playwright-Browser-Kontext öffnen.
- Für jede aktivierte `ExtractorSpec` in `EXTRACTORS` der Reihe nach
  `_run_extractor(spec, …)` aufrufen — alle nutzen denselben `page`. Die Statusrückgabe (`ok`, `no_match`, `fail: <msg>`) wird vom Batch-Modus erfasst.
- `write_to_queue(...)` — Gibt das finale JSON in die Verarbeitungs-Queue aus.
- Browser-Kontext schließen.

Pro Song wird **ein gemeinsamer** Browser-Kontext geöffnet und zwischen allen
Extraktoren geteilt — das spart vier Cold-Starts. Die `search_on_*`-Funktionen
akzeptieren ein optionales `page`-Argument; wird es gesetzt, verwalten sie
keinen eigenen Browser. Standalone-CLI-Aufrufe öffnen weiterhin ihren eigenen
Kontext.

### Cross-Extractor-Optimierung

Tunebat findet auf der Song-Seite häufig einen Direktlink zu Songstats und
legt ihn als `bus.set("tunebat", "songstats_url", …)` ab. Der nächste Extraktor
(Songstats) bekommt diesen Wert über `direct_url_from=("tunebat",
"songstats_url")` aus der `ExtractorSpec` durchgereicht und überspringt seine
eigene Suche.

Details: [`modules/watcher.md`](modules/watcher.md).

## IPC-Layer

Extraktoren müssen auch standalone laufen können — ohne Watcher. Sie greifen
über `shared/now_playing.py` auf den aktuell spielenden Song zu.

Zwei Backends, konfigurierbar in `shared/config.py::IPC_MODE`:

- **`"file"` (Default):** `now_playing.txt` im aktuellen Arbeitsverzeichnis.
  Atomar geschrieben (temp + `os.replace`), damit Reader keinen Partial-Read
  bekommen. Inhalt ist ein JSON-String mit `{"song": ..., "artists": [...]}`.
- **`"env"`:** Windows-User-Umgebungsvariable `NOW_PLAY`, gelesen/geschrieben
  über PowerShell-Subprozesse. Selbes JSON-Format.

Der Sentinel-Wert `"nothing..."` (`SENTINEL_NONE`) bedeutet "kein Track aktiv".

Details: [`modules/ipc.md`](modules/ipc.md).

## Extraktortypen

| Typ | Modul | Technologie | Besonderheit |
|-----|-------|-------------|--------------|
| API | `spotify/` | `spotipy` + OAuth2 | Token-Cache neben dem Modul |
| Browser | `tunebat/` | Playwright + `playwright-stealth` | BPM, Key, Audio-Features; liefert `songstats_url` als Cross-Hop |
| Browser | `songstats/` | Playwright + BS4 | Overview-Daten (Genres, ISRCs, Distributors, Music Info) |
| Browser | `genius/` | Playwright + BS4 | Lyrics, Credits, Album-Tracklist |
| Browser | `songbpm/` | Playwright + BS4 | Vibe-Beschreibung |

Alle Browser-Extraktoren nutzen **persistente Profile** im Verzeichnis
`.profiles/` (z. B. `.profiles/tunebat_profile/`). Die Profile werden beim
ersten Start angelegt, sind in `.gitignore` und **dürfen nicht gelöscht werden**
— sie enthalten Cookies, Login-State und Anti-Bot-Reputation.

Jeder Browser-Extraktor folgt dem Submodul-Pattern:
- `browser/context.py` — Playwright-Kontext-Setup mit persistentem Profil
- `browser/navigator.py` — Suche & Resultatsauswahl
- `scraper/*.py` — Datenextraktion aus dem geladenen DOM
- `<modul>.py` — `search_on_<modul>()`-Orchestrator + CLI-Einsprung

## Gemeinsame Utilities

- `shared/utils/search_variations.py::generate_variations()` — generische
  Variations-Generierung (Reihenfolge, Klammern, Featured-Artists,
  Remix/Edit-Tags, Unicode-Normalisierung). Wird von Tunebat, Songstats und
  Genius verwendet.
- `shared/utils/search_variations.py::extract_featured_artists()` — zieht versteckte
  Künstler aus dem Titel (`feat.`, `ft.`, `with`, `von`).
- `shared/utils/cookie_manager.py::wait_for_and_dismiss_cookies()` — zentrales
  Cookie-Banner-Handling (OneTrust, deutsche/englische Buttons).
- `shared/utils/validator.py::calculate_validation_score()` — zentrales
  Fuzzy-Matching-Scoring (difflib + Artist-Bonus + Remix-Bonus) für die
  Suchergebnis-Bewertung in allen Browser-Extraktoren.

## Logging-Konvention

Alle Statusmeldungen gehen über `shared/utils/log.py::log_status()` nach **stderr**.
Stdout bleibt frei für strukturierte JSON-Ausgaben der CLIs — das ist
wichtig, wenn die CLIs gepiped werden:

```powershell
uv run python -m beatbase.tunebat.tunebat --song X --artist Y `
  | jq '.bpm'
```

Verwende **nie** `print()` für Statusmeldungen, sondern immer `log_status()`.

## Persistenz-Stellen

Beatbase schreibt an mehrere Stellen parallel — nicht verwechseln:

| Pfad | Schreiber | Inhalt |
|------|-----------|--------|
| `data/json/{track_id}.json` | `extractor/orchestrator.py::_archive_summary` | Master-JSON pro Song (Default-Output) |
| `data/songs.db` | `processor/songs_db.py::save_song_summary` | Lokale SQLite, vom Watcher pro Songwechsel gefüllt. Track-ID = PK, bestehende Einträge werden überschrieben. Lyrics/Tracklist/Credits als JSON-Strings serialisiert. |
| `data/tunebat_searches.db` | `tunebat/db.py::save_search_results` | Lokale SQLite mit den rohen Tunebat-Suchtreffern. Append-only, eine Zeile pro Treffer mit `searched_at`. |
| `data/genius.db` | `genius/db.py::save_artist_songs` | Lokale SQLite mit allen auf Artist-Songs-Seiten entdeckten Genius-Songs. Schema: `genius_url` (PK), `song`, `artist`. Append-only, dedupliziert per URL via `INSERT OR IGNORE`. |
| `data/tunebat_searches/<query>.html` | `tunebat/browser/navigator.py::_save_debug_html` | Optionale Roh-HTML-Dumps der Suchergebnisseite. Toggle via `SAVE_TUNEBAT_HTML` in `shared/config.py`. |
| `BEATBASE_DB_PATH` (Default `C:/workspace/beatbase/spotify.db`) | `processor/external_db.py::update_audio_features` | **Externe** SQLite, nur über `--track-id`-Workflow bei Songstats geschrieben. Gehört nicht zum Repo, sondern zu einem übergeordneten System. Pfad via Env-Var überschreibbar. |

Die lokalen `data/`-Pfade sind in `.gitignore`. Die externe DB existiert nur, wenn
das übergeordnete System sie anlegt — fehlt sie, schlägt der `--track-id`-Pfad
fehl, alle anderen Workflows laufen weiter.

Details:
- Songstats `--track-id`-Workflow: [`modules/songstats.md`](modules/songstats.md).
- Tunebat-Persistenz: [`modules/tunebat.md`](modules/tunebat.md).
- Watcher-Archivierung: [`modules/watcher.md`](modules/watcher.md).
