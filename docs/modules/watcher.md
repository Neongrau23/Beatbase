# Orchestrator (Watcher-Loop)

Quelle: `src/beatbase/extractor/orchestrator.py`

Der Orchestrator ist der zentrale Polling-Loop. Er pollt Spotify, erkennt
Songwechsel und führt die deklarative Extraktor-Pipeline aus. Nach jedem
Song reicht er die fertige Summary über die Queue an den Processor (`process_queue()`)
weiter — die Naht zwischen Standort 1 (Beschaffung) und Standort 2 (Verarbeitung).

## Lifecycle

```
run_watcher()
  │
  ├─ log: "👁️ Watcher aktiv. Polling-Intervall: 10s."
  │
  └─ while True:
      ├─ track = get_current_spotify_track()
      │
      ├─ if track is None:
      │     if last_track_id != None: clear_now_playing()
      │
      ├─ elif track.id != last_track_id:
      │     handle_new_track(track)
      │     last_track_id = track.id
      │
      └─ sleep(POLLING_INTERVAL)
```

## Pro Songwechsel: `handle_new_track`

```python
def handle_new_track(track, headless=WATCHER_HEADLESS) -> dict[str, str]:
    bus.clear()
    _publish_now_playing(track)
    _push_spotify(track)

    statuses: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            for spec in EXTRACTORS:
                if spec.enabled:
                    statuses[spec.name] = _run_extractor(spec, track, page, headless)
        finally:
            context.close()
            browser.close()

    summary_json = get_summary_json()
    log_status(summary_json)
    if spotify_id := track.get("id"):
        _handoff_to_processor(spotify_id, summary_json)
    return statuses
```

Schritte:

1. `bus.clear()` — die Hotline wird zurückgesetzt.
2. `_publish_now_playing(track)` — IPC-Layer aktualisieren.
3. `_push_spotify(track)` — Spotify-Rohdaten in den Bus.
4. **Einen** Playwright-Browser-Kontext öffnen.
5. Pipeline durchlaufen — jeder aktivierte Extraktor bekommt denselben `page`
   und liefert einen Status (`"ok"` / `"no_match"` / `"fail: <msg>"`).
6. Browser schließen.
7. `get_summary_json()` ausgeben, via `extractor/queue.py::write_to_queue` als
   JSON in `data/queue/` ablegen und danach synchron
   `processor/importer.py::process_queue()` aufrufen, um die Daten in die DBs
   zu übernehmen.
8. Status-Dict zurückgeben — der Spotify-Watcher ignoriert den Return,
   der Batch-Modus (`extractor/batch.py`) schreibt ihn in `search_queue.db`.

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
`direct_url_from=("tunebat", "songstats_url")` aus der `ExtractorSpec` ab und
überspringt die eigene Suche.

Neuen Extraktor hinzufügen: `search_on_<modul>` implementieren, eine
`ExtractorSpec` in die Liste eintragen, optional `ENABLE_*`-Toggle in
`shared/config.py` ergänzen. Sonst keine Änderung am Orchestrator nötig.

## Fehler-Isolation und Status-Return

`_run_extractor` fängt alle Exceptions des Extraktors ab und gibt einen
Statusstring zurück, den `handle_new_track` zu einem Dict einsammelt:

```python
def _run_extractor(spec, track, page, headless) -> str:
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
            return "no_match"

        if spec.store_under_data_key:
            bus.set(spec.name, "data", result)
        for k, v in result.items():
            bus.set(spec.name, k, v)
        return "ok"
    except Exception as e:
        log_status(f"❌ {spec.label}-Fehler: {e}")
        return f"fail: {type(e).__name__}: {e}"
```

Status-Werte:

- `"ok"` — Treffer im Bus abgelegt.
- `"no_match"` — Quelle ist sauber durchgelaufen, hatte aber kein Ergebnis.
  Terminal: Der Batch-Modus retryed das **nicht**.
- `"fail: <Klasse>: <msg>"` — Exception. Vom Batch-Modus über
  `batch retry` zurücksetzbar.

Ein Crash in einem Extraktor stoppt den Watcher nicht und blockiert die anderen
nicht. Der äußere Loop in `run_watcher` fängt zusätzlich alle übrigen Exceptions
ab und schläft den nächsten Intervall ab, statt zu beenden.

## Geteilter Browser-Kontext

Im Gegensatz zu früher öffnen die `search_on_*`-Funktionen **keinen eigenen
Browser**, wenn das `page`-Argument gesetzt ist — sie verwenden den vom Watcher
gestarteten Kontext weiter. Das spart vier Cold-Starts pro Songwechsel.

Standalone-CLI-Aufrufe (`python -m beatbase.extractor.tunebat.tunebat …`) öffnen
weiterhin ihren eigenen persistenten Kontext via
`extractor/tunebat/browser/context.py::create_browser_context`.

## Track-Identität

Songwechsel-Erkennung erfolgt **ausschließlich** über die Spotify-Track-ID
(`track.get("id")`). Title-Matching wäre fehleranfällig (zwei Songs mit
gleichem Titel, Remixes etc.).

Wenn Spotify `None` zurückgibt (kein Song läuft), wird der IPC-Layer geleert.

## Singleton via PID-Datei

`__main__.py` schreibt beim Start eine `.beatbase.pid` mit der eigenen PID
(Pfad: `shared/config.py::PID_FILE_PATH`). Ein zweiter `python -m beatbase`-Aufruf
verweigert mit Hinweis. Beenden:

```powershell
uv run python -m beatbase --stop
```

Liest die PID, schickt `SIGTERM` und räumt die PID-Datei auf.

## Batch-Modus als Alternative

Wer eine vorgegebene Track-Liste anreichern will, ohne dass Spotify aktiv
spielt, nutzt den Batch-Modus:

```powershell
uv run python -m beatbase batch add tracks.csv
uv run python -m beatbase batch run
```

Er nutzt dieselbe `handle_new_track`-Pipeline, schreibt aber den Status-Return
zusätzlich in `data/search_queue.db`. Details:
[`cli.md#batch-modus`](../cli.md#batch-modus) und der Batch-Abschnitt in
[`architecture.md`](../architecture.md).

## Konfiguration

Siehe [Konfiguration → Watcher](../configuration.md#watcher--ipc-sharedconfigpy).

Die wichtigsten Hebel (alle in `shared/config.py`):

- `POLLING_INTERVAL` (Default 10s) — niedriger = schneller Wechsel erkannt,
  aber mehr API-Calls. Spotify-API-Limit ist großzügig, aber nicht unendlich.
- `WATCHER_HEADLESS` (Default `False`) — auf `True` setzen für unsichtbares
  Fenster im Headless-Modus.
- `ENABLE_TUNEBAT` / `ENABLE_SONGSTATS` / `ENABLE_GENIUS` / `ENABLE_SONGBPM` —
  einzelne Extraktoren in der Pipeline aktivieren/deaktivieren.
- `QUEUE_DIR` (Default `data/queue/`) — Zwischenablage zwischen Orchestrator
  und Importer.
- `JSON_EXPORT_DIR` (Default `data/json/`) — Archiv erfolgreich importierter
  Summaries.
