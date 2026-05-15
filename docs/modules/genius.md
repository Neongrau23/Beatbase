# Genius-Extraktor

Quellen:
- `src/beatbase/genius/genius.py` — CLI + Public-Entry
- `src/beatbase/genius/browser/` — Selenium-Treiber & Navigation
- `src/beatbase/genius/scraper/extractor.py` — BeautifulSoup-Parsing
- `src/beatbase/genius/validator.py` — Scoring-Logik

Browser-Scraper für [genius.com](https://genius.com). Liefert primär Lyrics und die validierte Song-URL.

## Public-Entry

```python
search_on_genius(song: str, artists: list[str], headless: bool = HEADLESS) -> dict | None
```

Verwaltet den Selenium-Lifecycle und koordiniert Suche sowie Extraktion:

```python
driver = create_driver(headless=headless)
try:
    # Suche mit Variations und Scoring
    song_url = find_song_url(driver, queries, target_string, artists)
    if not song_url:
        return None

    # Laden und Scrollen
    soup = load_song_page(driver, song_url)

    # Extraktion
    ergebnis_json = extrahiere_song_details_json(soup)
    ergebnis_json["url"] = song_url
    return ergebnis_json
finally:
    driver.quit()
```

## Pipeline

```
search_on_genius(song, artists)
  │
  ├─ generate_variations()                ← Aus beatbase.utils
  ├─ create_driver(headless)              ← Persistentes Profil
  │
  ├─ find_song_url()                      ← Suche über Genius-Suchleiste
  │     │
  │     ├─ Iteriert über Such-Variationen
  │     ├─ Berechnet Validation-Score (validator.py)
  │     └─ Bester Treffer (> Threshold)   → Song-URL
  │
  ├─ load_song_page(driver, url)
  │     │
  │     ├─ goto(url)
  │     ├─ scroll(50% + 100%)             ← Lazy-Lyrics laden
  │     └─ wait for "[data-lyrics-container='true']"
  │
  └─ extrahiere_song_details_json(soup)   ← BS4-Parsing (nur Lyrics)
```

## Migration & Fehlerbehebung (Playwright)

Beim Umstieg von Selenium auf Playwright sind folgende Punkte entscheidend:

- **Browser-Crashes (TargetClosedError/Exit Code 21):** Diese treten meist auf, wenn Chromium-Prozesse (oft als "Zombies" im Hintergrund) den Profil-Ordner sperren.
  - *Lösung:* Aktive `chrome.exe` Prozesse über den Task-Manager oder `taskkill /F /IM chrome.exe /T` beenden.
- **Absolute Pfad-Berechnung:** Um Konflikte durch wechselnde Arbeitsverzeichnisse (`os.getcwd()`) zu vermeiden, wird der Profil-Pfad nun absolut berechnet:
  ```python
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  profile_dir = os.path.join(base_dir, PROFILE_DIR)
  ```
- **Stealth-Flags:** Um Cloudflare-Challenges zu minimieren, nutzen wir:
  ```python
  args=["--disable-blink-features=AutomationControlled"]
  ```

## Suchstrategie & Validierung

Genius nutzt nun eine mehrstufige Suche (`find_song_url`):
1. **Variationen:** Erzeugt verschiedene Suchstrings (z.B. mit/ohne Features).
2. **Scoring:** Jedes Suchergebnis wird gegen den `target_string` (Titel + Artists) geprüft (`calculate_validation_score`).
3. **Threshold:** Nur Ergebnisse über `MATCH_THRESHOLD` (Standard: 0.8) werden akzeptiert. Ein Bonus wird für Übereinstimmungen bei Künstlernamen und Begriffen wie "Remix" oder "Edit" vergeben.

## Scroll-Trick für Lyrics

Genius lädt Lyrics lazy nach. `load_song_page` scrollt schrittweise:

```python
driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
time.sleep(PAGE_LOAD_SLEEP)
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
```

## Extraction-Details (Lyrics)

Der Extraktor in `scraper/extractor.py` konzentriert sich aktuell ausschließlich auf die Lyrics:

```python
lyrics_containers = soup.find_all("div", {"data-lyrics-container": "true"})
```

Pro Container:
1. `[data-exclude-from-selection='true']`-Divs entfernen (Annotation-Trigger).
2. `<br>` → `\n`.
3. Zeilen splitten und bereinigen.
4. Sections anhand von Metadaten in eckigen Klammern (z.B. `[Verse 1]`, `[Chorus]`) gruppieren.

## Output-Schema

```json
{
  "lyrics": [
    {
      "section": "[Verse 1]",
      "lines": ["...", "..."]
    }
  ],
  "url": "https://genius.com/..."
}
```

> **Hinweis:** Frühere Versionen der Dokumentation enthielten Felder für Credits, Track-Infos und Album-Tracklists. Diese sind in der aktuellen Implementierung (`extractor.py`) zugunsten einer stabileren Lyrics-Extraktion vorerst entfernt worden.
