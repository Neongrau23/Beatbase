# 🎵 Analyse der Genius-Suche

Diese Dokumentation beschreibt den technischen Ablauf der Songsuche und Datenextraktion im Genius-Modul.

## 🚀 Prozess-Übersicht

Der Ablauf ist in vier Hauptphasen unterteilt:

1.  **Vorbereitung & Variantenbildung**
2.  **Browser-Initialisierung**
3.  **Iterative Suche & Validierung**
4.  **Extraktion & Parsing**

---

### 1. 🔍 Vorbereitung & Variantenbildung
Bevor die Suche startet, werden die Eingabedaten aufbereitet:
*   **Künstler-Extraktion**: Es wird geprüft, ob im Songtitel zusätzliche Künstler (z.B. "feat. X") genannt werden.
*   **Ziel-String**: Ein `target_string` wird aus Titel und allen Künstlern für den späteren Abgleich erstellt.
*   **Such-Variationen**: Es werden verschiedene Kombinationen aus Titel und Künstlern generiert, um die Trefferwahrscheinlichkeit zu erhöhen.

### 2. 🌐 Browser-Initialisierung
Das Skript nutzt **Selenium** mit einem Chrome-WebDriver:
*   **Persistentes Profil**: Nutzt den Ordner `genius_profile_selenium`. Dies speichert Cookies und hilft dabei, **Captchas zu vermeiden**.
*   **Headless-Modus**: Der Browser läuft im Hintergrund (unsichtbar), sofern nicht anders konfiguriert.
*   **User-Agent**: Ein echter Browser-String wird verwendet, um nicht als Bot erkannt zu werden.

### 3. ⚖️ Iterative Suche & Validierung
Das Skript geht die generierten Suchbegriffe nacheinander durch:
1.  **Eingabe**: Der Suchbegriff wird in die Genius-Suchleiste (`name='q'`) eingegeben.
2.  **Ergebnis-Sammlung**: Es wird nach Links gesucht, die auf `-lyrics` enden, oder nach sogenannten `mini_card`-Elementen.
3.  **Scoring (Validierung)**:
    *   Jedes Ergebnis erhält einen **Score** basierend auf der Textähnlichkeit (`difflib`).
    *   **Bonus**: +0.2 für jeden korrekt gefundenen Künstler.
    *   **Edit-Bonus**: +0.1 für "Remix" oder "Edit", um Originale gegenüber Covern zu bevorzugen.
4.  **Early Exit**: Wenn ein Treffer einen Score von **> 0.95** erreicht, wird die Suche sofort beendet.

### 4. 📄 Extraktion & Parsing
Sobald der beste Link feststeht:
*   **Vollständiges Laden**: Die Seite wird aufgerufen und **automatisch gescrollt**, damit alle Lyrics-Container dynamisch in den DOM geladen werden.
*   **Inhalts-Extraktion**:
    *   **Lyrics**: Werden nach Sektionen (z.B. `[Intro]`, `[Chorus]`) gruppiert extrahiert.
    *   **Metadaten**: Titel, Künstler, Aufrufe (Views) und Release-Datum.
    *   **Credits**: Alle Mitwirkenden (Produzenten, Autoren) werden erfasst.
    *   **Album**: Falls vorhanden, wird die Tracklist des zugehörigen Albums extrahiert.

---

## 🛠️ Wichtige Konfigurationen (`config.py`)
*   `MATCH_THRESHOLD = 0.8`: Mindest-Score, damit ein Ergebnis akzeptiert wird.
*   `WEBDRIVER_TIMEOUT = 15`: Maximale Wartezeit für Seiten-Elemente.
*   `PAGE_LOAD_SLEEP = 1`: Kurze Pause nach dem Scrollen für dynamische Inhalte.
