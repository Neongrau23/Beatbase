# Architekturüberblick

Dieses Dokument beschreibt die Designentscheidungen und Muster hinter Beatbase.
Die einzelnen Komponenten sind in [`modules/`](modules/) im Detail dokumentiert.

## Designziele

1. **Quellenagnostische Aggregation.** Spotify, Songstats und Genius haben
   unterschiedliche Schemas und Datenqualität. Beatbase soll Daten
   überlappungsfrei mergen können, ohne dass die Extraktoren das Zielschema
   kennen müssen.
2. **Fehler-Isolation.** Ein abgestürzter Scraper darf den Watcher nicht
   anhalten.
3. **Standalone-fähig.** Jeder Extraktor muss auch ohne Watcher laufen.
4. **Lokal nutzbar.** Keine Server-Komponente, keine Cloud, kein Dauerlauf
   nötig — auf einer Maschine, in einem Prozess pro Modul.

## Datenfluss

```
┌──────────────────┐
│ Spotify Polling  │  ← core/watcher.py (Default 15s)
└────────┬─────────┘
         │ Songwechsel?
         ▼
┌──────────────────┐
│  bus.clear()     │  ← core/hotline.py
│  write_now_play  │  ← utils/now_playing.py (IPC für Standalone-Aufrufe)
└────────┬─────────┘
         │
   ┌─────┼─────┐
   ▼     ▼     ▼
┌──────┐ ┌──────────┐ ┌────────┐
│Spotify│ │Songstats │ │Genius  │
│ push  │ │ Playwright│ │Selenium│
└───┬──┘ └────┬─────┘ └───┬────┘
    │        │            │
    └────► bus.set(source, key, value) ◄────┘
                 │
                 ▼
        ┌────────────────────┐
        │ build_song_summary │  ← utils/callcenter.py
        └────────────────────┘
```

## Das Hotline/Callcenter-Muster

Beatbase nutzt einen zweistufigen Datenfluss, der Extraktoren von der finalen
Datenstruktur entkoppelt.

### Hotline (`core/hotline.py`)

Ein globaler, unstrukturierter Key-Value-Speicher (`bus`). Jeder Extraktor legt
seine Rohdaten unter seinem Quellennamen ab:

```python
bus.set("songstats", "Energy", 0.73)
bus.set("spotify", "isrc", "USUG11904206")
```

Die Hotline kennt kein Schema. Sie ist reine Ablage.

**Warum?** Wenn ein neuer Extraktor hinzukommt, muss er das finale Song-Objekt
nicht kennen. Er schreibt einfach alles in den Bus, was er hat. Die Hotline
wird beim Songwechsel über `bus.clear()` geleert.

### Callcenter (`utils/callcenter.py`)

Die Logik-Schicht. Liest aus `bus.get_all()` und baut strukturierte Views:

```python
summary = {
    "title": bus.get("songstats", "Title") or bus.get("spotify", "name"),
    "isrc": bus.get("spotify", "isrc") or bus.get("songstats", "ISRCs"),
    "release_date": _determine_release_date(raw),  # nimmt ältestes Datum
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
   - `_run_songstats(track)` — eigener try/except.
   - `_run_genius(track)` — eigener try/except.
   - `build_song_summary()` ausgeben.
3. `time.sleep(POLLING_INTERVAL)`.

Pro Song wird ein **frischer Browser-Kontext** geöffnet und am Ende geschlossen
(siehe `search_on_songstats` / `search_on_genius`). Browser werden nicht
zwischen Songs wiederverwendet, weil persistente Sessions in Playwright
gelegentlich hängen bleiben und Headless-Modi bei Refreshes inkonsistent
reagieren.

Details: [`modules/watcher.md`](modules/watcher.md).

## IPC-Layer

Extraktoren müssen auch standalone laufen können — ohne Watcher. Sie greifen
über `utils/now_playing.py` auf den aktuell spielenden Song zu.

Zwei Backends, konfigurierbar in `core/config.py::IPC_MODE`:

- **`"file"` (Default):** `now_playing.txt` im aktuellen Arbeitsverzeichnis.
  Atomar geschrieben (temp + `os.replace`), damit Reader keinen Partial-Read
  bekommen.
- **`"env"`:** Windows-User-Umgebungsvariable `NOW_PLAY`, gelesen/geschrieben
  über PowerShell-Subprozesse.

Der Sentinel-Wert `"nothing..."` (`SENTINEL_NONE`) bedeutet "kein Track aktiv".

Songstring-Format: `"<Title> von <Artist1>, <Artist2>"`. Songstats und Genius
parsen diesen String als Suchbegriff-Fallback, wenn kein CLI-Argument
übergeben wurde.

Details: [`modules/ipc.md`](modules/ipc.md).

## Extraktortypen

| Typ | Modul | Technologie | Besonderheit |
|-----|-------|-------------|--------------|
| API | `spotify/` | `spotipy` + OAuth2 | Token-Cache neben dem Modul |
| Browser | `songstats/` | Playwright (Chromium) | Highcharts-Daten via Maus-Move-Trick |
| Browser | `genius/` | Selenium (Chrome) + BS4 | Persistentes Profil, Lyrics + Credits |

Beide Browser-Extraktoren nutzen **persistente Profile** im Projektroot
(`songstats_profile/`, `genius_profile_selenium/`). Diese sind in `.gitignore`
und dürfen nicht gelöscht werden — sie enthalten Cookies und Captcha-Bypass.

## Suchlogik

Da die Zielsites unterschiedliche Suchalgorithmen haben, gibt es zwei
Variations-Generatoren:

- **`utils/search_variations.py::generate_variations()`** — generisch,
  wiederverwendbar. Variiert Reihenfolge (`Title Artist` vs. `Artist Title`),
  Klammern, Trennzeichen.
- **Inline in `songstats.py`** — aggressivere Variante via
  `itertools.permutations`. Songstats ist sehr sensitiv auf die Wortreihenfolge.

`extract_featured_artists()` zieht versteckte Künstler aus dem Titel
(`feat.`, `ft.`, `with`, `von`) und ergänzt sie zur Künstler-Liste, bevor
die Suche startet.

## Logging-Konvention

Alle Statusmeldungen gehen über `utils/log.py::log_status()` nach **stderr**.
Stdout bleibt frei für strukturierte JSON-Ausgaben der CLIs — das ist
wichtig, wenn die CLIs gepiped werden:

```powershell
uv run python -m beatbase.songstats.songstats --song X --artist Y `
  | jq '.Energy'
```

Verwende **nie** `print()` für Statusmeldungen, sondern immer `log_status()`.

## Externe Abhängigkeiten

`songstats.py` schreibt bei Angabe von `--track-id` direkt in eine SQLite-DB
unter `C:/workspace/beatbase/spotify.db`. Diese DB gehört nicht zum Repo,
sondern zu einem übergeordneten System. Siehe
[`modules/songstats.md`](modules/songstats.md) für Details.
