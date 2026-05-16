# Troubleshooting

Bekannte Fehlerbilder und Lösungen.

## Spotify

### `Fehler: Spotify API Credentials fehlen in der .env Datei`

- `.env` fehlt im Projektroot oder enthält leere Werte.
- Prüfe: `SPOTIPY_CLIENT_ID` und `SPOTIPY_CLIENT_SECRET` gesetzt?
- Credentials erhältst du im
  [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

### `INVALID_CLIENT: Invalid redirect URI`

- Die `SPOTIPY_REDIRECT_URI` in deiner `.env` ist nicht im
  Dashboard-App-Setting hinterlegt.
- Default ist `http://localhost:8888/callback`. Eintragen unter
  *App → Edit Settings → Redirect URIs*.

### Token-Refresh schlägt fehl

- `src/beatbase/spotify/.spotify_cache` löschen.
- Beim nächsten Aufruf startet der OAuth-Flow neu.

### Watcher zeigt nie einen Songwechsel an

- Läuft Spotify im **Web-Player** oder im **Desktop-Client**?
  `user-read-currently-playing` funktioniert für beide. Bei Spotify
  Connect-Geräten (Lautsprechern) kann es Aussetzer geben.
- Prüfe manuell:
  ```powershell
  uv run python -m beatbase.spotify.spotify_current
  ```
- Wenn das nichts liefert: `is_playing` ist `false` (z. B. pausierter Track)
  oder kein Token.

## Watcher

### `⚠️ PID-Datei existiert bereits!`

- Eine laufende Beatbase-Instanz ist bereits aktiv (PID in `.beatbase.pid`).
- Beenden via `uv run python -m beatbase --stop` oder Task-Manager.
- Wenn die PID-Datei verwaist ist (Prozess existiert nicht mehr): `.beatbase.pid`
  manuell löschen.

### `⚠️ Fehler im Watcher-Loop: <Exception>`

- Eine Exception ist außerhalb der Extraktor-Try-Blöcke geflogen
  (meist Spotify-API).
- Watcher läuft weiter und versucht es im nächsten Intervall erneut.

### Browser-Fenster bleibt offen nach `--stop`

- `SIGTERM` schließt den Python-Prozess; Playwright/Chromium-Kindprozesse
  sollten mit beendet werden. Wenn nicht: Task-Manager → `chrome.exe`
  manuell beenden.

## Tunebat

### Cloudflare-Challenge blockiert Headless

- Skript einmalig mit sichtbarem Browser laufen lassen und die Challenge
  manuell lösen:
  ```powershell
  uv run python -m beatbase.tunebat.tunebat --no-headless --dev `
    --song "X" --artist "Y"
  ```
- Cookies landen in `.profiles/tunebat_profile/`. Folgeaufrufe sind dann
  auch headless möglich.
- Alternative: das Profil-Warmup-Skript:
  ```powershell
  uv run python -m beatbase.tunebat.browser.warm_profile
  ```
  Browst sichtbar Google, YouTube, Tunebat mit menschlicher
  Scroll-/Klick-Aktivität.

### `⚠️ Kein passender Treffer auf Tunebat gefunden`

- Die Top-5-Variationen haben keinen Treffer über `MATCH_THRESHOLD = 0.8`
  erbracht.
- Optionen:
  - Threshold in `tunebat/config.py` senken.
  - Variations-Logik in `utils/search_variations.py` erweitern.

## Songstats

### `❌ Kein Treffer.`

- Die `MATCH_THRESHOLD` von `0.7` hat keinen Treffer überschritten.
- Möglichkeiten:
  - Threshold in `src/beatbase/songstats/config.py` senken.
  - Variationen in `utils/search_variations.py` ergänzen.
  - Wenn Tunebat aktiv ist und einen `songstats_url` liefert, überspringt
    Songstats die eigene Suche — prüfe, ob Tunebat überhaupt einen Treffer
    hatte.

### Audio-Features fehlen im Master-Summary

- Aktuell liefert Songstats **keine** Audio-Features mehr (Highcharts-Trick
  wurde entfernt). Audio-Features kommen aus **Tunebat**.
- Wenn Tunebat im Pipeline-Lauf gescheitert ist, sind die Audio-Features im
  Master-Summary `None`.

### Playwright Browser nicht gefunden

```
Executable doesn't exist at ...\ms-playwright\chromium-...\chrome.exe
```

- `uv run playwright install chromium` ausführen.

## Genius

### `❌ Kein Song gefunden.`

- Genius hat keinen Treffer auf Suchergebnis-Seite oder über das
  Künstler-Profil gefunden.
- Häufige Ursachen:
  - Tippfehler im Suchbegriff.
  - Sehr neue / sehr obskure Songs ohne Genius-Seite.
- Falls Cloudflare oder Captcha: einmalig **sichtbar** starten
  (`--no-headless`), Challenge manuell lösen — Profil speichert das Cookie.

### Lyrics unvollständig

- Genius lädt Lyrics-Container lazy. `load_song_page` scrollt zweimal — bei
  sehr langen Songs könnte ein dritter Scroll helfen (`scrollHeight * 0.75`).

## SongBPM

### Keine Vibe-Beschreibung im Master-Summary

- SongBPM ist optional via `ENABLE_SONGBPM`. Prüfen, ob aktiv.
- Cookie-Banner blockiert? Das zentrale `wait_for_and_dismiss_cookies`
  sollte das handhaben — bei Layout-Änderungen in `utils/cookie_manager.py`
  neuen Selector ergänzen.

## IPC

### Konsument liest leeren String

- `IPC_MODE = "file"`: Konsument läuft in einem anderen CWD als der Writer.
  Beide aus Projektroot starten oder `IPC_MODE = "env"` nutzen.
- `IPC_MODE = "env"`: Eine bereits laufende PowerShell-Session sieht
  Änderungen erst nach Neustart der Shell (Env-Vars werden bei Process-Start
  geladen).

### `Unbekannter IPC_MODE: '…'`

- `core/config.py::IPC_MODE` ist nur `"file"` oder `"env"` erlaubt.

## Datenbanken

Beatbase schreibt an drei lokale Pfade unter `data/` und optional in eine
externe DB. Übersicht: [Konfiguration → Persistenz-Pfade](configuration.md#persistenz-pfade).

### Externe DB (`--track-id`)

#### `sqlite3.OperationalError: unable to open database file`

- Der Pfad in `BEATBASE_DB_PATH` zeigt auf eine Datei, die nicht existiert,
  oder das übergeordnete Verzeichnis fehlt.
- Default ist `C:/workspace/beatbase/spotify.db`. Diese DB gehört nicht zu
  Beatbase, sondern zu einem übergeordneten System. Wenn du `--track-id`
  nicht nutzt, kannst du den Aufruf ignorieren.
- Eigenen Pfad setzen: `$env:BEATBASE_DB_PATH = "D:/foo/spotify.db"`.

#### `sqlite3.OperationalError: no such table: tracks`

- Schema-Mismatch. Die Spalten und der Tabellenname sind in `core/db.py`
  hartkodiert. Bei Schema-Wechsel im übergeordneten System dort anpassen.

### Lokale DBs (`data/songs.db`, `data/tunebat_searches.db`)

- Beide werden beim ersten Schreibvorgang automatisch angelegt
  (`mkdir(parents=True, exist_ok=True)`); das `data/`-Verzeichnis muss nicht
  manuell vorhanden sein.
- **Korrupte DB / Schema-Wechsel:** Die jeweilige Datei einfach löschen — wird
  beim nächsten Lauf neu erzeugt. Bei `data/songs.db` gehen damit alle
  archivierten Song-Summaries verloren; bei `data/tunebat_searches.db` die
  Such-Historie. Wer das Archiv unter `data/json/` parallel führt (Default),
  hat die Summaries noch als Einzelfiles.
- **HTML-Dumps loswerden:** `SAVE_TUNEBAT_HTML = False` in `core/config.py`
  setzen. Bestehende Dumps unter `data/tunebat_searches/` können dann manuell
  gelöscht werden.

## Allgemein

### Headless funktioniert, sichtbar nicht (oder umgekehrt)

- Headless-Modus reagiert auf Browser-Events teils anders. Wenn etwas in
  einem Modus geht und im anderen nicht: Sleep-Pausen erhöhen, dann
  Maus-Events prüfen.

### Profil löschen?

- **Nicht.** Die Verzeichnisse unter `.profiles/` speichern Cookies und
  Captcha-Bypass-State. Wegwerfen heißt: alle Captchas wieder lösen, evtl.
  neue Bot-Detection-Stufe.
- Wenn doch nötig (z. B. korruptes Profil): das spezifische Verzeichnis
  löschen, mit sichtbarem Browser starten, einmal manuell durchklicken.
