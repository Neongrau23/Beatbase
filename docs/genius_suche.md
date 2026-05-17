# Analyse der Genius-Suche

Diese Dokumentation beschreibt den technischen Ablauf der Songsuche und
Datenextraktion im Genius-Modul. Für die User-zentrierte Modul-Übersicht
siehe [`modules/genius.md`](modules/genius.md).

## Prozess-Übersicht

Der Ablauf ist in vier Hauptphasen unterteilt:

1. **Vorbereitung & Variantenbildung**
2. **Browser-Initialisierung**
3. **Iterative Suche & Validierung**
4. **Extraktion & Parsing**

---

### 1. Vorbereitung & Variantenbildung

`_prepare_search_data` bereitet die Eingaben auf:

- **Künstler-Extraktion**: Es wird geprüft, ob im Songtitel zusätzliche
  Künstler genannt sind (`feat. X`, `ft. Y`, `with Z`, `von …`).
- **Ziel-String**: Ein `target_string` aus Titel und allen Künstlern für den
  späteren Abgleich.
- **Such-Variationen**: `generate_variations` (`shared/utils/search_variations.py`)
  erzeugt verschiedene Kombinationen aus Titel und Künstlern, um die
  Trefferwahrscheinlichkeit zu erhöhen.

### 2. Browser-Initialisierung

Das Skript nutzt **Playwright** mit einem persistenten Chromium-Profil:

- **Profil-Pfad**: `<root>/.profiles/genius_profile_playwright/`. Speichert
  Cookies und hilft beim Vermeiden von Captchas.
- **Headless-Modus**: Default `True` (siehe `genius/config.py::HEADLESS`).
  Im Watcher überschrieben durch `WATCHER_HEADLESS`.
- **User-Agent**: Ein Chrome-123-Browser-String aus `config.py::USER_AGENT`.
- **Stealth-Flag**: `--disable-blink-features=AutomationControlled` minimiert
  Cloudflare-Challenges.

> **Hinweis:** Genius lief früher auf Selenium + Chrome WebDriver. Seit dem
> Playwright-Refactor sind diese Abhängigkeiten entfernt.

### 3. Iterative Suche & Validierung

`find_song_url` arbeitet sich durch die generierten Suchbegriffe:

1. **Eingabe**: Der Suchbegriff wird in die Genius-Suchleiste eingegeben.
2. **Artist-First-Strategie**: Zuerst wird über `mini-artist-card` der
   Künstler identifiziert; dann der Song in dessen Liste gesucht.
3. **Fallback**: Wenn keine Artist-Card passt, wird die erste `mini_card`
   überhaupt als Fallback genutzt.
4. **Scoring** (`shared/utils/validator.py::calculate_validation_score`):
   - Basis-Ähnlichkeit über `difflib.SequenceMatcher`.
   - **+0.2** für jeden korrekt gefundenen Künstler.
   - **+0.1** für "Remix" oder "Edit", um Originale gegenüber Covern zu
     bevorzugen.
5. **Threshold**: `MATCH_THRESHOLD` (Default `0.8`).

### 4. Extraktion & Parsing

Sobald der beste Link feststeht (`load_song_page` + `extrahiere_song_details_json`):

- **Vollständiges Laden**: Die Seite wird aufgerufen und schrittweise
  gescrollt (50% → 100%), damit alle Lyrics-Container dynamisch in den DOM
  geladen werden.
- **Inhalts-Extraktion**:
  - **Lyrics**: Nach Sektionen (`[Intro]`, `[Chorus]`, …) gruppiert.
  - **Album-Tracklist**: Falls vorhanden, mit Track-Nummern und Links.
  - **Credits**: Producers, Writers, weitere Mitwirkende.

---

## Wichtige Konfigurationen (`genius/config.py`)

| Konstante | Default | Wirkung |
|-----------|---------|---------|
| `MATCH_THRESHOLD` | `0.8` | Mindest-Score, damit ein Ergebnis akzeptiert wird. |
| `WEBDRIVER_TIMEOUT` | `15` | Maximale Wartezeit (s) für Seiten-Elemente. |
| `PAGE_LOAD_SLEEP` | `0.5` | Pause (s) nach dem Scrollen für dynamische Inhalte. |
| `HEADLESS` | `True` | Browser unsichtbar (Standalone-Default). |
| `PROFILE_DIR` | `"../.profiles/genius_profile_playwright"` | Relativ zu `src/`. |
