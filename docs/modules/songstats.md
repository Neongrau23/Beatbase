# Songstats-Extraktor

Quellen:
- `src/beatbase/songstats/songstats.py` — CLI + Public-Entry
- `src/beatbase/songstats/browser/context.py` — Playwright-Kontext
- `src/beatbase/songstats/browser/navigator.py` — Suche & Profil-Auswahl
- `src/beatbase/songstats/scraper/coordinator.py` — Orchestrierung
- `src/beatbase/songstats/scraper/overview.py` — DOM-Extraktion

Browser-Scraper für [songstats.com](https://songstats.com). Liefert die
Overview-Sektion: Künstler, Labels, Distributors, Release Date, ISRCs,
Genres und Music Info (Duration, Key, Tempo, Time Signature).

## Public-Entry

```python
search_on_songstats(
    song: str,
    artists: list[str],
    headless: bool = False,
    page=None,
    direct_url: str | None = None,
) -> dict | None
```

Mit `page` läuft der Aufruf auf dem Browser-Kontext des Watchers; ohne `page`
öffnet `search_on_songstats` selbst einen persistenten Kontext. Der
`direct_url`-Parameter ist die Cross-Extractor-Optimierung: Tunebat findet
auf seiner Song-Seite einen Direktlink zu Songstats und legt ihn unter
`bus.set("tunebat", "songstats_url", …)` ab. Wird er an Songstats
durchgereicht, überspringt der die eigene Suche.

## Pipeline

```
search_on_songstats(song, artists)
  │
  └─ run_songstats_extraction(page, song, artists, direct_url)
      │
      ├─ extract_featured_artists()              ← Versteckte Artists aus Titel
      ├─ generate_variations()                   ← Such-Variationen
      │
      ├─ if direct_url:
      │     page.goto(direct_url)                ← Cross-Hop von Tunebat
      ├─ else:
      │     find_song_profile()                  ← Sucht & klickt Treffer
      │
      └─ Auf der Profilseite:
          ├─ wait_for_and_dismiss_cookies()
          ├─ goto(profile?source=overview) wenn nötig
          └─ _extract_overview(soup)             ← BS4-Parsing
```

## Persistentes Browser-Profil

`browser/context.py`:

```python
profile_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    ".profiles", "songstats_profile"
)
return p.chromium.launch_persistent_context(
    user_data_dir=profile_dir,
    headless=headless,
)
```

Das Profil liegt im Projektroot unter `.profiles/songstats_profile/`, ist in
`.gitignore` und darf nicht gelöscht werden. Es speichert:

- Cookies / Session
- Captcha-Bypass-Status
- Cloudflare-Challenge-Cache

## Match-Scoring

Songstats nutzt das zentrale Scoring aus `utils/validator.py`:

```python
score = difflib.SequenceMatcher(None, target, found_text).ratio()
for artist in artists:
    if artist.lower() in found_text:
        score += 0.2                            # Artist-Bonus
if "edit" in found_text or "remix" in found_text:
    score += 0.1                                # Bias gegen Instrumentals/Cover
```

`MATCH_THRESHOLD` ist `0.7` (siehe `songstats/config.py`), etwas niedriger
als bei den anderen Extraktoren — Songstats-Treffer sind oft etwas ungenauer
formatiert.

## Output-Schema (Overview)

```python
{
    "Artists":        "The Weeknd",
    "Collaborators":  "...",
    "Record Labels":  "...",
    "Distributors":   "...",
    "Release Date":   "2019-11-29",
    "ISRCs":          "USUG11904206",
    "Genres":         "Synth-pop, Pop",

    "Duration":       "3:20",
    "Key":            "F# minor",
    "Tempo":          "171 BPM",
    "Time Signature": "4/4",

    "url":            "https://songstats.com/song/abc",
}
```

> ⚠️ **Highcharts-/Audio-Features-Trick entfernt.** Frühere Versionen
> extrahierten Audio-Features (Energy, Danceability, …) über physische
> Mausbewegungen auf einem Highcharts-SVG. Der aktuelle Coordinator hat
> *Fokus auf NUR Overview*. Audio-Features kommen jetzt aus **Tunebat**
> ([`modules/tunebat.md`](tunebat.md)).

## Externe DB (`--track-id`-Workflow)

Wenn `--track-id ID` an die CLI übergeben wird **und** `"Energy"` im Ergebnis
vorhanden ist, schreibt `update_audio_features` die acht Audio-Features in
die SQLite-DB unter `BEATBASE_DB_PATH`:

```sql
UPDATE tracks
SET danceability=?, acousticness=?, energy=?, instrumentalness=?,
    liveness=?, speechiness=?, valence=?, loudness=?
WHERE track_id=?
```

> Praktischer Hinweis: Solange der aktuelle `_extract_overview` keine
> Audio-Features liefert, ist dieser Pfad de facto ein No-Op. Wenn das
> Songstats-Schema wieder Audio-Features bedienen soll, in `overview.py` (oder
> einem neuen Sub-Extraktor) ergänzen und sicherstellen, dass der Key
> `"Energy"` vorhanden ist.

Default-Pfad: `C:/workspace/beatbase/spotify.db`, überschreibbar via
`BEATBASE_DB_PATH`-Env-Var.

Diese DB gehört nicht zum Repo. Beim Schemawechsel des übergeordneten Systems
muss `core/db.py` angepasst werden.

## Bekannte Sensitivitäten

- **Wortreihenfolge.** Songstats matched "Artist Title" anders als "Title
  Artist". Die `generate_variations`-Liste deckt mehrere Permutationen ab.
  Bei häufigen Misses kann der `MATCH_THRESHOLD` gesenkt oder die
  Variations-Liste erweitert werden.
- **Cross-Hop von Tunebat.** Bei aktivem Tunebat überspringt Songstats die
  eigene Suche und navigiert direkt auf die richtige Profilseite — robuster
  und schneller. Das `?source=overview`-Query wird angehängt, damit Songstats
  nicht auf eine Spotify-Subseite weiterleitet.
- **Sleep/Wait-Pausen.** Im Code sind mehrere `wait_for_load_state("networkidle")`
  zu finden, weil Songstats eine SPA ist. Bei Headless-Aussetzern ggf.
  Timeouts erhöhen.
