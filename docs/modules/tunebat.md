# Tunebat-Extraktor

Quellen:
- `src/beatbase/tunebat/tunebat.py` — CLI + Public-Entry
- `src/beatbase/tunebat/browser/` — Playwright-Kontext & Navigation
- `src/beatbase/tunebat/validator.py` — Match-Scoring

Browser-Scraper für [tunebat.com](https://tunebat.com). Liefert BPM, Key, Audio-Features und Metadaten.

## Public-Entry

```python
search_on_tunebat(song: str, artists: list[str], headless: bool = HEADLESS, dev_mode: bool = False) -> dict | None
```

Verwaltet den Playwright-Lifecycle und koordiniert die Suche:

```python
with sync_playwright() as p:
    context = create_browser_context(p, headless=actual_headless)
    browser = context.browser
    page = context.new_page()
    try:
        # Sucht mit Variationen und Scoring
        # Extrahiert Audio-Features und Metadaten
        ...
        return formatted_results
    finally:
        context.close()
        if browser:
            browser.close()
```

## Pipeline

```
search_on_tunebat(song, artists)
  │
  ├─ generate_variations()                ← Aus beatbase.utils
  ├─ create_browser_context(headless)     ← Persistentes Profil + Stealth Flags
  │
  ├─ Iteration über top 5 Variationen
  │     │
  │     ├─ page.goto("https://tunebat.com/")
  │     ├─ Eingabe Suchbegriff -> Enter
  │     └─ find_best_result(page, target_string, artists)
  │           │
  │           ├─ Sucht in div.hl7iF -> div.pDoqI
  │           ├─ Berechnet Validation-Score (validator.py)
  │           └─ Bester Treffer (> Threshold) -> Song-URL
  │
  └─ Datenextraktion auf Song-Seite
        ├─ page.goto(best_song_url)
        ├─ Extraktion Key, BPM, Duration (.yIPfN)
        ├─ Extraktion Progress-Metriken wie Energy, Danceability (._1MCwQ)
        └─ Extraktion Metadaten wie Album, Label (._4aYzP)
```

## Persistentes Browser-Profil

`browser/context.py`:

```python
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
profile_dir = os.path.join(base_dir, PROFILE_DIR)

context = p.chromium.launch_persistent_context(
    user_data_dir=profile_dir,
    headless=headless,
    user_agent=USER_AGENT,
    args=["--disable-blink-features=AutomationControlled"]
)
```

Das Profil (`.profiles/tunebat_profile/`) liegt sicher im Projektroot. Es speichert gelöste Cloudflare-Challenges (Cookies), um bei zukünftigen Headless-Durchläufen nicht erneut blockiert zu werden.

## Suchstrategie & Validierung

Tunebat ist anfällig für Bot-Erkennung (Cloudflare) und oft sehr restriktiv bei Suchanfragen.
Um eine robuste Suche zu gewährleisten:
1. **Mehrstufige Suche:** Es werden automatisch Variationen (Titel+Künstler, Titel allein, etc.) ausprobiert (`generate_variations`). Oft reicht bei Tunebat nur der Titel für das beste Ergebnis.
2. **Scoring:** Gefundene Zeilen in der Resultatliste werden gegen den ursprünglichen Suchstring geprüft (`calculate_validation_score`). Ein Treffer über `MATCH_THRESHOLD = 0.8` löst den Klick aus.

## Migration & Fehlerbehebung (Playwright)

Beim Umstieg von Selenium auf Playwright traten spezifische Probleme auf:

- **Browser-Crashes (Exit Code 2147483651 / 21):** Dies passiert, wenn alte "Zombie"-Prozesse das Profil-Verzeichnis blockieren.
  - *Lösung:* Regelmäßiges Beenden aller Chrome-Prozesse (`taskkill /F /IM chrome.exe /T`).
- **Pfade:** Die Nutzung von `os.getcwd()` ist für Profile riskant. Wir verwenden nun absolute Pfade basierend auf `os.path.abspath(__file__)`.

## Cloudflare-Umgehung (Turnstile)

Falls die Seite dennoch blockiert:
1. Skript mit `--no-headless --dev` starten.
2. Manuell die Cloudflare-Checkbox (Mensch-Test) im sichtbaren Browser-Fenster bestätigen.
3. Warten bis die Seite lädt, dann `ENTER` im Terminal drücken, um den Browser zu schließen. Das Cookie wird im Profil gespeichert und bei zukünftigen headless-Starts automatisch genutzt.

## Output-Schema

```json
{
  "url": "https://tunebat.com/...",
  "title": "string",
  "artist": "string",
  "key": "string",
  "camelot": "string",
  "bpm": "string",
  "duration": "string",
  "popularity": "string",
  "release_date": "string",
  "explicit": "string",
  "album": "string",
  "label": "string",
  "audio_features": {
    "acousticness": "string",
    "danceability": "string",
    "energy": "string",
    "instrumentalness": "string",
    "liveness": "string",
    "speechiness": "string",
    "happiness": "string",
    "loudness": "string"
  }
}
```
