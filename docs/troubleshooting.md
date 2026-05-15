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

## Songstats

### Captcha-Schleife / Cloudflare-Challenge

- Beim allerersten Start einmalig **mit sichtbarem Browser** laufen lassen,
  damit du die Challenge manuell lösen kannst:
  ```powershell
  uv run python -m beatbase.songstats.songstats --song "X" --artist "Y"
  # Ohne --headless!
  ```
- Cookies landen in `songstats_profile/`. Folgeaufrufe sind dann auch
  headless möglich.

### `❌ Kein Treffer.`

- Die `MATCH_THRESHOLD` von 0.8 hat keinen Treffer überschritten.
- Möglichkeiten:
  - Threshold in `src/beatbase/songstats/config.py` senken (`0.7`).
  - Variationen in `utils/search_variations.py` ergänzen.
  - Aggressivere Permutations-Variante inline ergänzen (siehe Hinweis in
    [`modules/songstats.md`](modules/songstats.md)).

### Audio-Features alle 0.0

- Der Highcharts-Tooltip wurde nicht angezeigt. Häufige Ursachen:
  - Headless-Modus: Maus-Events landen ggf. nicht. Mit sichtbarem Browser
    testen.
  - Sleep-Pause zu kurz. In `scraper/metrics.py` die
    `page.wait_for_timeout(250)` erhöhen.
  - Songstats hat das SVG umgebaut. Selektor
    `svg.highcharts-root:has(g.highcharts-xaxis-labels)` prüfen.

### Playwright Browser nicht gefunden

```
Executable doesn't exist at ...\ms-playwright\chromium-...\chrome.exe
```

- `uv run playwright install chromium` ausführen.

## Genius

### Selenium / Chrome-Version-Mismatch

- Ab Selenium 4 verwaltet Selenium Manager den `chromedriver` automatisch.
  Falls trotzdem ein Mismatch: Chrome aktualisieren.

### `❌ Kein Song gefunden.`

- Der erste Treffer auf der Genius-Suchergebnis-Seite war kein
  `-lyrics`-Link.
- Häufige Ursachen:
  - Tippfehler im Suchbegriff.
  - Sehr neue / sehr obskure Songs ohne Genius-Seite.
- Aktuell gibt es **keinen** Variations-Fallback (anders als bei Songstats).
  Bei häufigen Misses: Variation-Schleife in `genius/browser/navigator.py`
  ergänzen.

### Lyrics unvollständig

- Genius lädt Lyrics-Container lazy. `load_song_page` scrollt zweimal —
  bei sehr langen Songs könnte ein dritter Scroll helfen
  (`scrollHeight * 0.75`).

## Watcher

### `⚠️ Fehler im Watcher-Loop: <Exception>`

- Eine Exception ist außerhalb der Extraktor-Try-Blöcke geflogen
  (meist Spotify-API).
- Watcher läuft weiter und versucht es im nächsten Intervall erneut.

### Beide Browser öffnen sich gleichzeitig und kollidieren

- Sollte nicht passieren — sie laufen sequenziell (`_run_songstats` →
  `_run_genius`). Wenn doch: stelle sicher, dass nur **eine** Watcher-
  Instanz läuft. Check via Task-Manager (mehrere `python.exe`-Prozesse).

### Hoher CPU-Verbrauch im Idle

- Die Browser-Profile bleiben zwischen Songs **geschlossen** — wenn du
  Dauer-CPU siehst, ist möglicherweise Spotify (`is_playing`-Loop) der
  Verursacher, nicht Beatbase.

## IPC

### Konsument liest leeren String

- `IPC_MODE = "file"`: Konsument läuft in einem anderen CWD als der Writer.
  Beide aus Projektroot starten oder `IPC_MODE = "env"` nutzen.
- `IPC_MODE = "env"`: Eine bereits laufende PowerShell-Session sieht
  Änderungen erst nach Neustart der Shell (Env-Vars werden bei Process-Start
  geladen).

### `Unbekannter IPC_MODE: '…'`

- `core/config.py::IPC_MODE` ist nur `"file"` oder `"env"` erlaubt.

## Datenbank

### `sqlite3.OperationalError: unable to open database file`

- `C:/workspace/beatbase/spotify.db` existiert nicht oder das übergeordnete
  Verzeichnis fehlt.
- Diese DB gehört nicht zu Beatbase, sondern zu einem übergeordneten System.
  Wenn du `--track-id` nicht nutzt, kannst du den Aufruf ignorieren.

### `sqlite3.OperationalError: no such table: tracks`

- Schema-Mismatch. Die Spalten und der Tabellenname sind in `core/db.py`
  hartkodiert. Bei Schema-Wechsel im übergeordneten System dort anpassen.

## Allgemein

### Headless funktioniert, sichtbar nicht (oder umgekehrt)

- Headless-Modus reagiert auf Browser-Events teils anders. Wenn etwas in
  einem Modus geht und im anderen nicht: Sleep-Pausen erhöhen, dann
  Maus-Events prüfen.

### Profil löschen?

- **Nicht.** `songstats_profile/` und `genius_profile_selenium/` speichern
  Cookies und Captcha-Bypass. Wegwerfen heißt: alle Captchas wieder lösen.
- Wenn doch nötig (z. B. korruptes Profil): Verzeichnis löschen, mit
  sichtbarem Browser starten, einmal manuell durch klicken.
