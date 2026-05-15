# Watcher

Quelle: `src/beatbase/core/watcher.py`

Der Watcher ist der zentrale Polling-Loop und Orchestrator. Er pollt Spotify,
erkennt Songwechsel und triggert die Extraktoren.

## Lifecycle

```
run_watcher()
  │
  ├─ log: "Watcher aktiv"
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

Pro neuem Track läuft `_handle_new_track`:

1. `bus.clear()` — die Hotline wird zurückgesetzt.
2. `_publish_now_playing(track)` — IPC-Layer aktualisieren.
3. `_push_spotify(track)` — Spotify-Rohdaten in den Bus.
4. `_run_songstats(track)` — eigener try/except.
5. `_run_genius(track)` — eigener try/except.
6. `build_song_summary()` ausgeben.

## Fehler-Isolation

Jeder Extraktor läuft in einem eigenen try/except:

```python
def _run_songstats(track: dict) -> None:
    log_status("\n--- Songstats ---")
    try:
        result = search_on_songstats(...)
        if result:
            for k, v in result.items():
                bus.set("songstats", k, v)
    except Exception as e:
        log_status(f"❌ Songstats-Fehler: {e}")
```

Ein Crash in Songstats stoppt den Watcher nicht und blockiert Genius nicht.
Der äußere Loop fängt zusätzlich alle übrigen Exceptions ab und schläft den
nächsten Intervall ab, statt zu beenden.

## Browser-Lifecycle

`search_on_songstats` und `search_on_genius` öffnen ihren Browser-Kontext
**selbst** und schließen ihn im `finally`-Block:

```python
def search_on_songstats(song, artists, headless=False):
    with sync_playwright() as p:
        context = create_browser_context(p, headless=headless)
        ...
        try:
            return run_songstats_extraction(page, song, artists)
        finally:
            context.close()
```

Browser werden bewusst **nicht** zwischen Songs wiederverwendet. Persistente
Sessions führen in Headless-Modi zu Hängern beim Reload. Cookies bleiben
trotzdem erhalten — sie liegen im persistenten Profilverzeichnis, nicht im
Browser-Prozess.

## Track-Identität

Songwechsel-Erkennung erfolgt **ausschließlich** über die Spotify-Track-ID
(`track.get("id")`). Title-Matching wäre fehleranfällig (zwei Songs mit
gleichem Titel, Remixes etc.).

Wenn Spotify `None` zurückgibt (kein Song läuft), wird der IPC-Layer auf
den Sentinel `"nothing..."` gesetzt — Konsumenten können das prüfen.

## Konfiguration

Siehe [Konfiguration → Watcher](../configuration.md#watcher).

Die wichtigsten Hebel:

- `POLLING_INTERVAL` (Default 15s) — niedriger = schneller Wechsel erkannt,
  aber mehr API-Calls. Spotify-API-Limit ist großzügig, aber nicht unendlich.
- `WATCHER_HEADLESS` (Default `True`) — auf `False` setzen, wenn du Browser-
  Sessions debuggen willst (z. B. Songstats-Captchas einmalig manuell lösen).
