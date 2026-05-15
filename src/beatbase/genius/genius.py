"""CLI-Einstiegspunkt für den Genius-Scraper.

Alle Logik liegt in den Untermodulen. Diese Datei nur für den CLI-Aufruf.
"""

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

from beatbase.core.config import SENTINEL_NONE
from beatbase.genius.browser.context import create_playwright_context
from beatbase.genius.browser.navigator import find_song_url, load_song_page
from beatbase.genius.config import HEADLESS
from beatbase.genius.scraper.extractor import extrahiere_song_details_json
from beatbase.utils.log import log_status
from beatbase.utils.now_playing import read_now_playing_data
from beatbase.utils.search_variations import extract_featured_artists, generate_variations


# DEF: Metadaten für Genius-Suche vorbereiten
def _prepare_search_data(song: str, artists: list[str]) -> tuple[list[str], str, list[str]]:
    """SECTION: PREPARATION - Bereitet Künstlerliste und Suchbegriffe vor."""
    # Im Titel versteckte Feature-Künstler (z. B. "ft. XY") extrahieren
    featured = extract_featured_artists(song)

    # Gefundene Feature-Künstler zur Künstlerliste hinzufügen, sofern noch nicht vorhanden
    for artist in featured:
        if not any(artist.lower() in existing.lower() for existing in artists):
            artists.append(artist)

    # Ziel-String für den späteren Treffervergleich normalisieren
    target_string = f"{song} {', '.join(artists)}".lower()

    # Verschiedene Suchanfragen generieren (z. B. mit/ohne Featured-Künstler)
    queries = generate_variations(song, artists)
    return artists, target_string, queries


# DEF: Eigentlichen Such- und Extraktions-Workflow ausführen
def _execute_genius_search(
    page,
    song: str,
    artists: list[str],
    queries: list[str],
    target_string: str,
) -> dict | None:
    """SECTION: EXTRACTION - Führt die Playwright-Interaktionen aus."""
    try:
        log_status(f"🔗 Suche auf Genius: {song} von {', '.join(artists)}")

        # Genius durchsuchen und die URL des passenden Songs ermitteln
        song_url = find_song_url(page, queries, target_string, artists)

        # Abbruch, wenn kein passender Treffer gefunden wurde
        if not song_url:
            log_status("❌ Kein Song gefunden.")
            return {
                "lyrics": [{"section": "[Info]", "lines": ["Keine Lyrics Verfügbar"]}],
                "url": None,
            }

        log_status(f"🔗 Öffne Song: {song_url}")

        # Song-Seite laden und als BeautifulSoup-Objekt parsen
        soup = load_song_page(page, song_url)

        # Lyrics und Metadaten aus dem geparsten HTML extrahieren
        ergebnis_json = extrahiere_song_details_json(soup)

        # Quell-URL zum Ergebnis hinzufügen
        ergebnis_json["url"] = song_url

        log_status("✅ Vollständige Daten (inkl. Lyrics) extrahiert.")
        log_status(f"📊 Genius Daten: {json.dumps(ergebnis_json, indent=4, ensure_ascii=False)}")
        return ergebnis_json

    except Exception as e:
        # Unerwartete Fehler abfangen und None zurückgeben
        log_status(f"❌ Fehler bei der Verarbeitung: {e}")
        return None


# DEF: Genius Suche (Orchestrator)
def search_on_genius(
    song: str,
    artists: list[str],
    headless: bool = HEADLESS,
    page=None,
) -> dict | None:
    """SECTION: ORCHESTRATION - Sucht auf Genius und gibt extrahierte Song-Details zurück.

    Koordiniert Browser-Kontext, Navigation und Extraktion über Playwright.
    """
    artists, target_string, queries = _prepare_search_data(song, artists)

    if page:
        return _execute_genius_search(page, song, artists, queries, target_string)
    else:
        with sync_playwright() as p:
            # Browser-Kontext starten (mit oder ohne sichtbarem Fenster)
            context = create_playwright_context(p, headless=headless)

            # Vorhandene Seite wiederverwenden oder neue öffnen
            new_page = context.pages[0] if context.pages else context.new_page()

            try:
                return _execute_genius_search(new_page, song, artists, queries, target_string)
            finally:
                # Browser-Kontext in jedem Fall schließen (auch bei Fehlern)
                context.close()


# DEF: Haupteinsprungpunkt
def main():
    """ENTRY: Einstiegspunkt für das Skript."""
    parser = argparse.ArgumentParser(description="Genius Lyrics & Metadata Scraper (Selenium)")
    parser.add_argument("query", nargs="?", help="Suchbegriff (Fallback: aktueller Song)")
    parser.add_argument("--song", help="Expliziter Songtitel")
    parser.add_argument(
        "--artist",
        action="append",
        default=[],
        help="Expliziter Künstler (mehrfach möglich)",
    )
    parser.add_argument("--headless", action="store_true", help="Browser im Headless-Modus")
    args = parser.parse_args()

    song_name = args.song
    artists = args.artist

    if not song_name and args.query:
        # Wenn nur ein query-String da ist, versuchen wir ihn zu splitten
        # oder nehmen ihn als Songnamen
        song_name = args.query
        # FEATURE: Falls 'von' im String ist, splitten wir
        if " von " in song_name.lower():
            parts = song_name.lower().split(" von ")
            song_name = parts[0].strip()
            artists = [parts[1].strip()]

    if not song_name:
        # Fallback: aktueller Song strukturiert aus dem IPC-Layer
        data = read_now_playing_data()
        song_name = data.get("song")
        artists = data.get("artists", [])

    if not song_name or song_name == SENTINEL_NONE:
        log_status("❌ Kein Suchbegriff angegeben.")
        sys.exit(1)

    log_status(f"⏳ Suche nach: '{song_name}'...")
    ergebnis_json = search_on_genius(song_name, artists, headless=args.headless)
    if ergebnis_json:
        print(json.dumps(ergebnis_json, indent=4, ensure_ascii=False))
    else:
        log_status("❌ Keine Details gefunden.")
        sys.exit(1)


if __name__ == "__main__":
    main()
