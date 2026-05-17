# Genius-Extraktor

Quellen:
- `src/beatbase/extractor/genius/genius.py` — CLI + Public-Entry
- `src/beatbase/extractor/genius/browser/context.py` — Playwright-Kontext mit persistentem Profil
- `src/beatbase/extractor/genius/browser/navigator.py` — Suche & Profil-Auswahl
- `src/beatbase/extractor/genius/scraper/extractor.py` — BeautifulSoup-Extraktion (Lyrics, Credits, Album)

Browser-Scraper für [genius.com](https://genius.com). Liefert Lyrics
sektionsweise, Credits, Album-Tracklist und die validierte Song-URL.

> **Hinweis:** Genius lief früher auf Selenium. Seit `refactor(genius): ...`
> ist das gesamte Modul auf Playwright (Chromium) umgestellt. Selenium ist
> **nicht** mehr im Dependency-Set.

## Public-Entry

```python
search_on_genius(
    song: str,
    artists: list[str],
    headless: bool = HEADLESS,
    page=None,
) -> dict | None
```

Verwaltet den Playwright-Lifecycle und koordiniert Suche sowie Extraktion:

```python
artists, target_string, queries = _prepare_search_data(song, artists)

if page:
    return _execute_genius_search(page, song, artists, queries, target_string)

with sync_playwright() as p:
    context = create_playwright_context(p, headless=headless)
    new_page = context.pages[0] if context.pages else context.new_page()
    try:
        return _execute_genius_search(new_page, song, artists, queries, target_string)
    finally:
        context.close()
```

Mit `page` läuft Genius auf dem Browser-Kontext des Orchestrators; ohne `page`
öffnet `search_on_genius` selbst einen persistenten Kontext.

## Pipeline

```
search_on_genius(song, artists)
  │
  ├─ _prepare_search_data()                ← Featured-Artists + Variationen
  │
  └─ _execute_genius_search()
      │
      ├─ find_song_url(page, queries, ...)
      │     │
      │     ├─ Sucht über Genius-Suchleiste / Artist-Profil
      │     ├─ Iteriert über Such-Variationen
      │     ├─ Berechnet calculate_validation_score (shared/utils/validator.py)
      │     └─ Bester Treffer (> MATCH_THRESHOLD) → Song-URL
      │
      ├─ load_song_page(page, url)
      │     │
      │     ├─ goto(url)
      │     ├─ Scrollt (50% + 100%)        ← Lazy-Lyrics laden
      │     └─ wait for "[data-lyrics-container='true']"
      │
      └─ extrahiere_song_details_json(soup) ← BS4-Parsing
```

## Persistentes Browser-Profil

`browser/context.py`:

```python
base_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
profile_dir = os.path.join(base_dir, PROFILE_DIR)

context = playwright.chromium.launch_persistent_context(
    user_data_dir=profile_dir,
    headless=headless,
    user_agent=USER_AGENT,
    args=["--disable-blink-features=AutomationControlled"],
)
```

Das Profil liegt unter `<root>/.profiles/genius_profile_playwright/`, ist in
`.gitignore` und darf nicht gelöscht werden. Cookies / Captcha-Bypass-State
sind dort gespeichert.

## Suchstrategie & Validierung

`find_song_url` führt eine mehrstufige Suche aus:

1. **Variationen:** `generate_variations` erzeugt diverse Suchstrings (z. B.
   mit/ohne Features, Reihenfolge umgedreht).
2. **Artist-First:** Zuerst Genius-Suche → versucht den Künstler über
   `mini-artist-card` zu identifizieren → dann den Song in dessen Liste.
3. **Scoring:** Jedes Ergebnis wird gegen den `target_string` (Titel + Artists)
   geprüft (`calculate_validation_score`). Ein Bonus wird für
   Übereinstimmungen bei Künstlernamen (`+0.2` pro Match) und für Begriffe wie
   "Remix" oder "Edit" (`+0.1`) vergeben.
4. **Threshold:** Nur Ergebnisse über `MATCH_THRESHOLD` (Default `0.8`)
   werden akzeptiert.

## Scroll-Trick für Lyrics

Genius lädt Lyrics-Container lazy. `load_song_page` scrollt schrittweise:

```python
page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
time.sleep(PAGE_LOAD_SLEEP)
page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(PAGE_LOAD_SLEEP)
```

Danach Wartebedingung auf `[data-lyrics-container='true']`.

## Extraktions-Details (Lyrics)

Pro Container in `[data-lyrics-container='true']`:

1. `[data-exclude-from-selection='true']`-Divs entfernen (Annotation-Trigger).
2. `<br>` → `\n`.
3. Zeilen splitten und bereinigen.
4. Sections anhand von Metadaten in eckigen Klammern (`[Verse 1]`,
   `[Chorus]`, …) gruppieren.

## Output-Schema

```json
{
  "lyrics": [
    {"section": "[Verse 1]", "lines": ["..."]},
    {"section": "[Chorus]", "lines": ["..."]}
  ],
  "url": "https://genius.com/...",
  "album_tracklist": [
    {"number": "1", "title": "...", "link": "https://genius.com/..."}
  ],
  "credits": {
    "producers": ["..."],
    "writers": ["..."]
  }
}
```

Wenn kein Treffer gefunden wird, gibt der Extraktor ein "Fallback"-Ergebnis
zurück mit Lyrics `[{"section": "[Info]", "lines": ["Keine Lyrics Verfügbar"]}]`
und `"url": None`.

## Stealth-Flag

Um Cloudflare-Challenges zu minimieren, läuft Chromium mit:

```python
args=["--disable-blink-features=AutomationControlled"]
```

Falls die Seite trotzdem blockiert: einmal sichtbar (nicht headless) starten,
die Challenge manuell lösen — das Profil speichert das Cookie für künftige
Headless-Läufe.
