# Songstats-Extraktor

Quellen:
- `src/beatbase/songstats/songstats.py` — CLI + Public-Entry
- `src/beatbase/songstats/browser/` — Playwright-Kontext und Navigation
- `src/beatbase/songstats/scraper/` — DOM- und Highcharts-Extraktion
- `src/beatbase/songstats/validator.py` — Match-Scoring

Browser-Scraper für [songstats.com](https://songstats.com). Liefert
Audio-Features, Performance-Daten und plattform-spezifische Metriken
(Spotify, Shazam, SoundCloud).

## Public-Entry

```python
search_on_songstats(song: str, artists: list[str], headless: bool = False) -> dict
```

Verwaltet den eigenen Playwright-Lifecycle:

```python
with sync_playwright() as p:
    context = create_browser_context(p, headless=headless)
    page = context.pages[0] if context.pages else context.new_page()
    try:
        return run_songstats_extraction(page, song, artists)
    finally:
        context.close()
```

Pendant zu `genius.search_on_genius()`. Wird vom Watcher direkt aufgerufen.

## Pipeline

```
search_on_songstats(song, artists)
  │
  ├─ create_browser_context()                 ← persistentes Profil
  │
  └─ run_songstats_extraction(page, ...)
      │
      ├─ extract_featured_artists()           ← Versteckte Artists aus Titel
      ├─ generate_variations()                ← Generische Variationen
      ├─ find_song_profile()                  ← Sucht & klickt Treffer
      │
      └─ Parallel auf der Profilseite:
          ├─ _extract_overview()              ← Artists, Labels, ISRC, Genres
          ├─ _extract_performance()           ← Streams, Popularity, ...
          ├─ _extract_metrics()               ← Audio-Features (Highcharts!)
          ├─ _extract_music_info()            ← Tempo, Key, Duration
          ├─ _extract_spotify_stats()         ← ?source=spotify
          ├─ _extract_shazam_stats()          ← ?source=shazam
          └─ _extract_soundcloud_stats()      ← ?source=soundcloud
```

## Persistentes Browser-Profil

`browser/context.py`:

```python
profile_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "songstats_profile"
)
return p.chromium.launch_persistent_context(
    user_data_dir=profile_dir, headless=headless
)
```

Das Profil liegt im **Projektroot** unter `songstats_profile/`, ist in
`.gitignore` und darf nicht gelöscht werden. Es speichert:

- Cookies / Session
- Captcha-Bypass-Status
- Cloudflare-Challenge-Cache

## Match-Scoring

`validator.py`:

```python
score = difflib.SequenceMatcher(None, target, found_text).ratio()
for artist in artists:
    if artist.lower() in found_text:
        score += ARTIST_BONUS              # Default 0.2
if "edit" in found_text or "remix" in found_text:
    score += 0.1                            # Bias gegen Instrumentals/Cover
```

`navigator.find_song_profile` iteriert über die Suchergebnisse, berechnet
für jedes den Score und klickt den besten, sofern er über
`MATCH_THRESHOLD = 0.8` liegt. Bei `score > 0.95` bricht die Suche vorzeitig
ab — fast-perfekter Match.

## Der Highcharts-Trick

`scraper/metrics.py` extrahiert die Audio-Features (Energy, Danceability,
Valence, …) aus einem **Highcharts-SVG-Spider-Chart**. Das Problem: Die
SVG-Punkte haben keine semantischen Klassen, und Highcharts reagiert nicht
auf synthetische `.hover()`-Events.

Lösung: **Physische Maus-Bewegung** auf die berechneten Pixel-Koordinaten:

```python
box = point.bounding_box()
page.mouse.move(
    box["x"] + box["width"] / 2,
    box["y"] + box["height"] / 2,
    steps=10                                # fließend, damit Highcharts reagiert
)
tooltip_locator.wait_for(state="attached", timeout=2000)
page.wait_for_timeout(250)                   # Einblend-Animation
tooltip_text = tooltip_locator.text_content(timeout=1000)
```

Der Tooltip-Text wird dann geparst:

| Tooltip-Format | Beispiel | Konvertierung |
|----------------|----------|---------------|
| `Acousticness: 12%` | Prozent | `0.12` (Float, konsistent mit Spotify API) |
| `Loudness: -5.4 dB` | dB | `-5.4` (Float) |
| `Tempo: 171` | Zahl | `171.0` (Float) |

Falls Punkte sich im Zentrum überlappen (alle nahe 0), werden alle Metriken
mit `0.0` vorinitialisiert — sonst gingen die Null-Werte verloren.

## Output-Schema

```python
{
    # Overview
    "Artists": "The Weeknd",
    "Collaborators": "...",
    "Record Labels": "...",
    "Distributors": "...",
    "Release Date": "2019-11-29",
    "ISRCs": "USUG11904206",
    "Genres": "Synth-pop, Pop",

    # Music Info
    "Duration": "3:20",
    "Key": "F# minor",
    "Tempo": "171 BPM",
    "Time Signature": "4/4",

    # Audio Features (Floats)
    "Acousticness": 0.00,
    "Danceability": 0.51,
    "Energy": 0.73,
    "Instrumentalness": 0.0,
    "Liveness": 0.09,
    "Speechiness": 0.06,
    "Valence": 0.34,
    "Loudness": -5.4,

    # Performance / Plattform
    "Streams": "...",
    "Popularity": "...",
    "Spotify Streams": "...",
    "Spotify Popularity": "...",
    "Spotify Playlists": "...",
    "Spotify Playlist Reach": "...",
    "Spotify Track Rank": "...",
}
```

Die Shazam- und SoundCloud-Stats werden zwar extrahiert (`shazam_gen`,
`sc_gen`), aber aktuell **nicht** ins finale Dict gemergt — sie werden nur
loggend ausgegeben. Bei Bedarf in `coordinator.py` ergänzen.

## Externe DB

Wenn `--track-id ID` an die CLI übergeben wird **und** `Energy` im Ergebnis
vorhanden ist, schreibt `update_audio_features` die acht Audio-Features in
`C:/workspace/beatbase/spotify.db`:

```sql
UPDATE tracks
SET danceability=?, acousticness=?, energy=?, instrumentalness=?,
    liveness=?, speechiness=?, valence=?, loudness=?
WHERE track_id=?
```

Diese DB gehört nicht zum Repo. Beim Schemawechsel des übergeordneten Systems
muss `core/db.py` angepasst werden.

## Bekannte Sensitivitäten

- **Wortreihenfolge.** Songstats matched "Artist Title" anders als "Title
  Artist". Die `generate_variations`-Liste deckt mehrere Permutationen ab.
  Bei häufigen Misses kann man inline in `songstats.py` zusätzlich
  `itertools.permutations(...)` einbauen.
- **Edits/Remixes.** Der Validator boost-Score für "edit"/"remix"
  (`+0.1`), um Instrumentals zu unterdrücken. Wenn du eine Instrumental-
  Version willst, Threshold senken oder den Bonus entfernen.
- **Sleep-Pausen.** Im Code sind mehrere `time.sleep(1.5)` / `wait_for_timeout`
  zu finden, weil Songstats eine Single-Page-Application ist und der DOM
  asynchron nachlädt. Bei Headless-Aussetzern ggf. Zeiten erhöhen.
