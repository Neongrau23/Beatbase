# Tunebat-Extraktor

Quellen:
- `src/beatbase/tunebat/tunebat.py` — CLI + Orchestrator
- `src/beatbase/tunebat/browser/context.py` — Playwright-Kontext mit Stealth
- `src/beatbase/tunebat/browser/navigator.py` — Suche, Pagination, Resultat-Auswahl
- `src/beatbase/tunebat/browser/warm_profile.py` — Profil-Warmup gegen Bot-Detection
- `src/beatbase/tunebat/scraper/extractor.py` — Datenextraktion von der Song-Seite

Browser-Scraper für [tunebat.com](https://tunebat.com). Liefert BPM, Key,
Camelot, Duration, Popularity, Audio-Features (Energy, Danceability, …),
Metadaten (Release Date, Label, Album) und einen Direktlink zu Songstats.

## Public-Entry

```python
search_on_tunebat(
    song: str,
    artists: list[str],
    headless: bool = HEADLESS,
    dev_mode: bool = False,
    page=None,
) -> dict | None
```

Aufbau analog Genius:

```python
artists, target_string, queries = _prepare_search_data(song, artists, page=page)

if page:
    return _execute_tunebat_search(page, song, artists, queries, target_string)

with sync_playwright() as p:
    context = create_browser_context(p, headless=actual_headless)
    new_page = context.new_page()
    try:
        return _execute_tunebat_search(new_page, song, artists, queries, target_string)
    finally:
        if dev_mode:
            input("fertig...")
        context.close()
```

## Pipeline

```
search_on_tunebat(song, artists)
  │
  ├─ _prepare_search_data()                ← Featured-Artists + Variationen
  │
  └─ _execute_tunebat_search()
      │
      ├─ Iteriert über top 5 Variationen:
      │     ├─ perform_search(page, query)
      │     │     │
      │     │     ├─ Header-Suche zuerst
      │     │     └─ Fallback: Main-Suche mit Leerzeichen-Trick (bis 4 Versuche)
      │     │
      │     └─ find_best_result(page, target_string, artists)
      │           │
      │           ├─ Pagination via "Load more" (bis 4 Klicks)
      │           ├─ Scoring (utils/validator.py)
      │           └─ Bester Treffer (> MATCH_THRESHOLD = 0.8)
      │
      └─ Auf der Song-Seite:
          ├─ Klick auf bestes Suchergebnis (Bot-Detection-Umgehung)
          ├─ wait for ".yIPfN" sichtbar
          └─ extract_song_data(page, song, artists)
                ├─ _extract_metrics()        ← Key, BPM, Duration (.yIPfN)
                ├─ _extract_progress_metrics() ← Popularity, Energy, ... (._1MCwQ)
                ├─ _extract_metadata()       ← Release, Label, Album, ... (._4aYzP)
                └─ _extract_songstats_url()  ← Cross-Hop-Link
```

## Persistentes Browser-Profil

`browser/context.py`:

```python
base_dir = Path(__file__).resolve().parents[3]
profile_dir = str(base_dir / PROFILE_DIR)

context = p.chromium.launch_persistent_context(
    user_data_dir=profile_dir,
    headless=headless,
    user_agent=USER_AGENT,
    locale="de-DE",
    timezone_id="Europe/Berlin",
    viewport={"width": 1280, "height": 900},
    args=[
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ],
)

stealth = Stealth()
context.on("page", lambda page: stealth.apply_stealth_sync(page))
```

Das Profil liegt unter `<root>/.profiles/tunebat_profile/`. Zusätzlich zur
Standard-Konfiguration nutzt Tunebat **`playwright-stealth`**, um typische
Automation-Fingerprints zu maskieren — Tunebat hat aggressivere Bot-Detection
als die anderen Quellen.

## Profil-Warmup

Wenn Cloudflare trotz Stealth zuschnappt, kann das Profil mit menschlicher
Browser-Aktivität "warmgelaufen" werden:

```powershell
uv run python -m beatbase.tunebat.browser.warm_profile
```

Das Skript öffnet sichtbar Google, YouTube und Tunebat, scrollt jeweils zwei-
bis viermal mit Pausen und wartet auf `ENTER` zum Schließen. Cookies und
Reputations-Tracking bleiben im Profil — folgende Headless-Läufe sehen den
Browser als "etablierten" Client.

## Such- und Klick-Strategie

Tunebat ist anfällig für Bot-Erkennung und reagiert je nach Eingabe-Timing
unterschiedlich:

1. **Mehrstufige Suche.** `perform_search` versucht erst die Header-Suche
   (klicken → tippen → Submit-Button). Wenn die Resultatliste nicht
   erscheint, schaltet `_fallback_main_search` auf die Haupt-Suche um und
   nutzt den "Leerzeichen-Trick": abwechselnd `query + " "` und `query`
   eintippen, bis Tunebat reagiert (bis zu 4 Versuche).
2. **Pagination.** `find_best_result` klickt bis zu 4-mal auf den
   "Load more"-Button und scrollt bei Hängern hoch/runter, um neue Ergebnisse
   nachzuladen.
3. **Klick statt Direkt-URL.** Auf das beste Suchergebnis wird **geklickt**,
   nicht direkt navigiert — der Klick-Workflow umgeht eine zusätzliche
   Bot-Detection-Schicht.

## Cross-Extractor-Optimierung

Tunebat sucht auf der Song-Seite nach `a[aria-label='Songstats']` und
extrahiert dessen `href` (mit `?source=overview` als Query-Param, damit
Songstats nicht auf Spotify weiterleitet). Der Watcher legt diesen Wert als
`bus.set("tunebat", "songstats_url", …)` ab; der nächste Extraktor in der
Pipeline (Songstats) bekommt ihn als `direct_url` durchgereicht und
überspringt seine eigene Suche.

## Output-Schema

```json
{
  "url": "https://tunebat.com/...",
  "title": "string",
  "artist": "string",
  "key": "C maj",
  "camelot": "8B",
  "bpm": "128",
  "duration": "3:20",
  "popularity": "85",
  "release_date": "...",
  "explicit": "...",
  "album": "...",
  "label": "...",
  "audio_features": {
    "acousticness": "12",
    "danceability": "72",
    "energy": "85",
    "instrumentalness": "0",
    "liveness": "9",
    "speechiness": "6",
    "happiness": "34",
    "loudness": "-5"
  },
  "songstats_url": "https://songstats.com/song/...?source=overview"
}
```

`None`-Werte werden vor der Rückgabe ausgefiltert.

## Cloudflare-Umgehung (Turnstile)

Falls die Seite dennoch blockiert:

1. Skript mit `--no-headless --dev` starten.
2. Manuell die Cloudflare-Checkbox im sichtbaren Browser-Fenster bestätigen.
3. `ENTER` im Terminal drücken, um den Browser zu schließen. Das Cookie wird
   im Profil gespeichert und bei zukünftigen Headless-Starts genutzt.

Alternativ den Profile-Warmup verwenden (siehe oben).
