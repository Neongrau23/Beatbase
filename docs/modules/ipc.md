# IPC-Layer

Quelle: `src/beatbase/utils/now_playing.py`

Der IPC-Layer entkoppelt die Extraktoren vom Watcher. Damit Tunebat, Songstats,
Genius und SongBPM auch standalone laufen können, brauchen sie einen Weg,
"den aktuell spielenden Song" zu erfragen, ohne selbst Spotify zu pollen.

## API

```python
read_now_playing_data() -> dict    # gibt {"song": "...", "artists": [...]} zurück
read_now_playing() -> str          # Kompatibilitäts-Wrapper (Titel + Artist)
write_now_playing(song, artists)   # setzt IPC-Daten als JSON
clear_now_playing()                # schreibt Sentinel "nothing..."
```

Der IPC-Modus wird in `core/config.py::IPC_MODE` festgelegt:

```python
IPC_MODE = "file"   # oder "env"
```

## Backend `"file"` (Default)

Schreibt/liest `now_playing.txt` im aktuellen Arbeitsverzeichnis (CWD). Der
Inhalt ist ein **JSON-String**.

### Atomares Schreiben

```python
def _write_file(value: str) -> None:
    path = os.path.join(os.getcwd(), IPC_FILE_PATH)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(value)
    os.replace(tmp, path)
```

**Warum?** Ohne temp+replace könnte ein Konsument einen Partial-Read machen,
während der Writer noch schreibt. `os.replace` ist auf Windows und POSIX
atomar auf demselben Filesystem.

## Backend `"env"`

Liest/schreibt die Windows-User-Umgebungsvariable `NOW_PLAY` über
PowerShell-Subprozesse. Auch hier wird der Wert als **JSON** gespeichert.

Einschränkungen:
- Nur Windows.
- Eine bereits laufende PowerShell-Session sieht Änderungen erst nach Neustart
  der Shell — Env-Vars werden bei Process-Start in den Prozess geladen.

## Sentinel-Wert

```python
SENTINEL_NONE = "nothing..."
```

Bedeutet: "kein Track aktiv". Wird vom Watcher geschrieben, wenn Spotify
`None` zurückgibt. Konsumenten prüfen:

```python
data = read_now_playing_data()
if not data.get("song") or data["song"] == SENTINEL_NONE:
    sys.exit(1)  # nichts zu tun
```

## Datenformat

Beim Schreiben durch den Watcher (`_publish_now_playing`):

```python
write_now_playing(track.get("song"), track.get("artists", []))
```

Das gespeicherte JSON sieht so aus:

```json
{
  "song": "Blinding Lights",
  "artists": ["The Weeknd"]
}
```

Tunebat, Songstats, Genius und SongBPM nutzen `read_now_playing_data()`, um
Songtitel und Künstlerliste sauber getrennt zu erhalten. Ein Fallback für das
alte String-Format (`"Song von Artist"`) ist in der Lesefunktion integriert.

> ℹ️ **Schreiber-Inkonsistenz:** Der Watcher ruft
> `write_now_playing(song, artists)` mit getrennten Argumenten auf und produziert
> das saubere JSON oben. Das Standalone-Spotify-CLI
> (`python -m beatbase.spotify.spotify_current`) baut dagegen den Suchstring
> selbst zusammen und ruft `write_now_playing("<Title> von <Artists>")` ohne
> separate Artist-Liste — im IPC landet daher
> `{"song": "Title von Artists", "artists": []}`. Der Legacy-Fallback in
> `read_now_playing_data()` splittet das transparent wieder zurück, sodass
> Konsumenten beide Schreiber gleich behandeln können. Details:
> [Spotify-CLI-Modul](spotify.md#cli).

Es gibt keinen Auto-Sync zwischen Backends. Wenn du `IPC_MODE` umschaltest,
während Beatbase läuft, sehen Konsumenten den alten Wert noch. Im Zweifel
Watcher neustarten.
