# 🏗️ Architektur & Konzepte

Dieses Dokument beschreibt die architektonischen Entscheidungen und Muster, die in **Beatbase** verwendet werden.

## 📞 Das Hotline / Callcenter Muster

Beatbase verwendet einen zweistufigen Datenfluss, um Daten aus verschiedenen Quellen (Spotify, Songstats, Genius) zu aggregieren, ohne die Extraktoren mit der finalen Datenstruktur zu belasten.

### 1. Hotline (`core/hotline.py`)
Die **Hotline** ist ein globaler, unstrukturierter Key-Value-Speicher (`bus`). 
- **Aufgabe:** Extraktoren werfen ihre Rohdaten (Scraping-Ergebnisse, API-Antworten) "nackt" in den Speicher.
- **Vorteil:** Ein neuer Extraktor muss nicht wissen, wie das finale `Song`-Objekt aussieht. Er speichert einfach alles, was er findet, unter seinem Quellennamen (z.B. `"songstats"`).

### 2. Callcenter (`utils/callcenter.py`)
Das **Callcenter** ist die Logik-Schicht, die auf die Hotline zugreift.
- **Aufgabe:** Es liest alle verfügbaren Rohdaten aus dem `bus` und setzt sie zu einer strukturierten Ansicht (z.B. `build_song_summary()`) zusammen.
- **Entscheidungsgewalt:** Hier wird entschieden, welche Quelle Vorrang hat (z.B. "Nimm das Release-Datum von Spotify, außer Songstats hat ein älteres").

---

## 🛰️ Extraktoren & Technologien

Wir unterscheiden zwischen zwei Arten von Extraktoren:

### API-Extraktoren (`spotify/`)
- **Spotify:** Nutzt die offizielle Web-API (`spotipy`).
- **Technik:** Reine HTTP-Requests, OAuth2 mit lokalem Token-Caching (`.spotify_cache`).

### Core/Browser-Extraktoren (`genius/ and songstats/`)
Für Seiten ohne (öffentliche) API nutzen wir Browser-Automatisierung.
- **Songstats:** Playwright (Chromium).
  - *Besonderheit:* Extrahiert Daten aus Highcharts-SVGs durch physische Mausbewegungen auf Koordinaten, da die SVGs keine semantischen Klassen besitzen.
- **Genius:** Selenium (Chrome).
  - *Besonderheit:* Nutzt BeautifulSoup zur Deep-Extraction von Lyrics und Credits.

---

## 🔄 Interprozesskommunikation (IPC) via `NOW_PLAY`

Da die verschiedenen Extraktoren oft entkoppelt voneinander laufen (z.B. Spotify-Polling im Hintergrund, Genius im Watch-Mode), kommunizieren sie über eine Windows-User-Umgebungsvariable: `NOW_PLAY`.

1. **Producer:** `spotify_current.py` schreibt den aktuellen Songstring (z.B. `"Blinding Lights von The Weeknd"`) in `NOW_PLAY`.
2. **Consumer:** `genius.py --auto` oder `songstats.py` lesen diese Variable als Fallback, wenn kein expliziter Suchbegriff übergeben wurde.

---

## 🔍 Suchlogik (Variationen)

Aufgrund der unterschiedlichen Suchalgorithmen der Zielseiten existieren zwei Varianten der Suchbegriff-Generierung:
- **`utils/search_variations.py`:** Generische Logik für die meisten Quellen.
- **Inline in `songstats.py`:** Aggressivere Generierung mittels `itertools.permutations`, da Songstats extrem sensitiv auf die Wortreihenfolge reagiert.

---

## 💾 Externe Abhängigkeiten
`songstats.py` schreibt bei Angabe einer `--track-id` direkt in eine SQLite-Datenbank unter `C:/workspace/beatbase/spotify.db`. Diese DB gehört nicht zum Repository, sondern zu einem übergeordneten System.
