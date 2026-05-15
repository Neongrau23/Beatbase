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
│ Spotify Polling  │  ← core/watcher.py (Default 10s)
└────────┬─────────┘
         │ Songwechsel?
         ▼
┌──────────────────┐
│  bus.clear()     │  ← core/hotline.py
│  write_now_play  │  ← utils/now_playing.py (IPC für Standalone-Aufrufe)
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
        │ build_song_summary │  ← utils/callcenter.py
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

### Hotline (`core/hotline.py`)

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

### Callcenter (`utils/callcenter.py`)

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

## Der Watcher-Loop

`core/watcher.py` ist der Orchestrator. Pro Iteration:

1. Spotify API pollen (`get_current_spotify_track`).
2. Wenn Track-ID sich geändert hat → `_handle_new_track(track)`:
   - `bus.clear()` — Hotline reseten.
   - `write_now_playing(...)` — IPC-Layer aktualisieren.
   - Spotify-Rohdaten in den Bus pushen.
   - **Einen** Playwright-Browser-Kontext öffnen.
   - Für jede aktivierte `ExtractorSpec` in `EXTRACTORS` der Reihe nach
     `_run_extractor(spec, …)` aufrufen — alle nutzen denselben `page`.
   - `get_summary_json()` ausgeben und nach
     `JSON_EXPORT_DIR/{track_id}.json` archivieren.
   - Browser-Kontext schließen.
3. `time.sleep(POLLING_INTERVAL)`.

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
über `utils/now_playing.py` auf den aktuell spielenden Song zu.

Zwei Backends, konfigurierbar in `core/config.py::IPC_MODE`:

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

- `utils/search_variations.py::generate_variations()` — generische
  Variations-Generierung (Reihenfolge, Klammern, Featured-Artists,
  Remix/Edit-Tags, Unicode-Normalisierung). Wird von Tunebat, Songstats und
  Genius verwendet.
- `utils/search_variations.py::extract_featured_artists()` — zieht versteckte
  Künstler aus dem Titel (`feat.`, `ft.`, `with`, `von`).
- `utils/cookie_manager.py::wait_for_and_dismiss_cookies()` — zentrales
  Cookie-Banner-Handling (OneTrust, deutsche/englische Buttons).
- `utils/validator.py::calculate_validation_score()` — zentrales
  Fuzzy-Matching-Scoring (difflib + Artist-Bonus + Remix-Bonus) für die
  Suchergebnis-Bewertung in allen Browser-Extraktoren.

## Logging-Konvention

Alle Statusmeldungen gehen über `utils/log.py::log_status()` nach **stderr**.
Stdout bleibt frei für strukturierte JSON-Ausgaben der CLIs — das ist
wichtig, wenn die CLIs gepiped werden:

```powershell
uv run python -m beatbase.tunebat.tunebat --song X --artist Y `
  | jq '.bpm'
```

Verwende **nie** `print()` für Statusmeldungen, sondern immer `log_status()`.

## Externe Abhängigkeiten

`songstats.py` schreibt bei Angabe von `--track-id` direkt in eine externe
SQLite-DB. Der Pfad steht in `BEATBASE_DB_PATH` (Default
`C:/workspace/beatbase/spotify.db`, via Env-Var überschreibbar). Diese DB
gehört nicht zum Repo, sondern zu einem übergeordneten System. Siehe
[`modules/songstats.md`](modules/songstats.md) für Details.
