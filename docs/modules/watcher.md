# Orchestrator

Quelle: `src/beatbase/core/watcher.py`

Der Orchestrator ist der zentrale Polling-Loop. Er pollt Spotify,
erkennt Songwechsel und führt die deklarative Extraktor-Pipeline aus.

## Lifecycle

```
run_orchestrator()
  │
  ├─ log: "Orchestrator aktiv"
  │
  └─ while True:
      ├─ track = get_current_spotify_track()
      │
      ├─ if track is None:
      │     if last_track_id != None: clear_now_playing()
      │
      ├─ elif track.id != last_track_id:
      │     _handle_new_track(track)
      │     last_track_id = track.id
      │
      └─ sleep(POLLING_INTERVAL)
```

## Pro Songwechsel: `_handle_new_track`

```python
def _handle_new_track(track, headless=ORCHESTRATOR_HEADLESS):
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            for spec in EXTRACTORS:
                if spec.enabled:
                    _run_extractor(spec, track, page, headless)
        finally:
            context.close()
            browser.close()

    summary_json = get_summary_json()
    log_status(summary_json)
    if spotify_id := track.get("id"):
        _archive_summary(spotify_id, summary_json)
```

Schritte:

1. `bus.clear()` — die Hotline wird zurückgesetzt.
2. `_publish_now_playing(track)` — IPC-Layer aktualisieren.
3. `_push_spotify(track)` — Spotify-Rohdaten in den Bus.
4. **Einen** Playwright-Browser-Kontext öffnen.
5. Pipeline durchlaufen — jeder aktivierte Extraktor bekommt denselben `page`.
6. Browser schließen.
7. `get_summary_json()` ausgeben, via `extractor/queue.py` als JSON in `data/queue/` ablegen
   und danach synchron `processor/importer.py` aufrufen, um die Daten in die
   Datenbank zu übernehmen.

## Deklarative Pipeline: `EXTRACTORS`

```python
@dataclass(frozen=True)
class ExtractorSpec:
    name: str                                # Hotline-Source-Key
    label: str                               # Anzeigename
    enabled: bool                            # Aus shared/config.py::ENABLE_*
    search_fn: Callable[..., dict | None]    # search_on_<modul>
    store_under_data_key: bool = False       # Zusätzlich bus.set(name, "data", result)?
    direct_url_from: tuple[str, str] | None = None  # Cross-Hop-Quelle

EXTRACTORS = [
    ExtractorSpec("tunebat",   "Tunebat",   ENABLE_TUNEBAT,   search_on_tunebat),
    ExtractorSpec("songstats", "Songstats", ENABLE_SONGSTATS, search_on_songstats,
                  direct_url_from=("tunebat", "songstats_url")),
    ExtractorSpec("genius",    "Genius",    ENABLE_GENIUS,    search_on_genius,
                  store_under_data_key=True),
    ExtractorSpec("songbpm",   "SongBPM",   ENABLE_SONGBPM,   search_on_songbpm,
                  store_under_data_key=True),
]
```

**Reihenfolge ist signifikant.** Tunebat zuerst, weil sein Ergebnis einen
Direktlink `songstats_url` liefern kann. Songstats greift ihn via
`direct_url_from=("tunebat", "songstats_url")` ab und überspringt die eigene
Suche.

Neuen Extraktor hinzufügen: `search_on_<modul>` implementieren, eine
`ExtractorSpec` in die Liste eintragen, optional `ENABLE_*`-Toggle in
`core/config.py` ergänzen. Sonst keine Änderung am Orchestrator nötig.

## Fehler-Isolation

`_run_extractor` fängt alle Exceptions des Extraktors ab und loggt sie:

```python
def _run_extractor(spec, track, page, headless):
    log_status(f"\n--- {spec.label} ---")
    try:
        kwargs = {"headless": headless, "page": page}
        if spec.direct_url_from:
            kwargs["direct_url"] = bus.get(*spec.direct_url_from, default=None)

        result = spec.search_fn(
            track.get("song"),
            list(track.get("artists", [])),
            **kwargs,
        )
        if not result:
            return

        if spec.store_under_data_key:
            bus.set(spec.name, "data", result)
        for k, v in result.items():
            bus.set(spec.name, k, v)
    except Exception as e:
        log_status(f"❌ {spec.label}-Fehler: {e}")
```

Ein Crash in einem Extraktor stoppt den Watcher nicht und blockiert die anderen
nicht. Der äußere Loop fängt zusätzlich alle übrigen Exceptions ab und schläft
den nächsten Intervall ab, statt zu beenden.

## Geteilter Browser-Kontext

Im Gegensatz zu früher öffnen die `search_on_*`-Funktionen **keinen eigenen
Browser**, wenn das `page`-Argument gesetzt ist — sie verwenden den vom Watcher
gestarteten Kontext weiter. Das spart vier Cold-Starts pro Songwechsel.

Standalone-CLI-Aufrufe (`python -m beatbase.tunebat.tunebat …`) öffnen
weiterhin ihren eigenen persistenten Kontext via
`extractor/tunebat/browser/context.py::create_browser_context`.

## Track-Identität

Songwechsel-Erkennung erfolgt **ausschließlich** über die Spotify-Track-ID
(`track.get("id")`). Title-Matching wäre fehleranfällig (zwei Songs mit
gleichem Titel, Remixes etc.).

Wenn Spotify `None` zurückgibt (kein Song läuft), wird der IPC-Layer auf
den Sentinel `"nothing..."` gesetzt — Konsumenten können das prüfen.

## Singleton via PID-Datei

`__main__.py` schreibt beim Start eine `.beatbase.pid` mit der eigenen PID.
Ein zweiter `python -m beatbase`-Aufruf verweigert mit Hinweis. Beenden:

```powershell
uv run python -m beatbase --stop
```

Liest die PID, schickt `SIGTERM` und räumt die PID-Datei auf.

## Konfiguration

Siehe [Konfiguration → Orchestrator](../configuration.md#orchestrator--ipc-coreconfigpy).

Die wichtigsten Hebel:

- `POLLING_INTERVAL` (Default 10s) — niedriger = schneller Wechsel erkannt,
  aber mehr API-Calls. Spotify-API-Limit ist großzügig, aber nicht unendlich.
- `WATCHER_HEADLESS` (Default `False`) — auf `True` setzen für unsichtbares
  Fenster im Headless-Modus.
- `ENABLE_TUNEBAT` / `ENABLE_SONGSTATS` / `ENABLE_GENIUS` / `ENABLE_SONGBPM` —
  einzelne Extraktoren in der Pipeline aktivieren/deaktivieren.
- `JSON_EXPORT_DIR` (Default `data/json`) — Zielverzeichnis für die
  Master-JSON-Archivierung pro Track.
