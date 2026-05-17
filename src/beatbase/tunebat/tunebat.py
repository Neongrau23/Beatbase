"""CLI-Einstiegspunkt und Orchestrator für den Tunebat-Scraper.

Die Datei haelt nur noch die Orchestrierung: Browser-Lifecycle, Datenvorbereitung
und CLI-Argumente. Such- und Extraktionslogik liegen in den Untermodulen:

- ``browser.navigator`` — Suche (Header- und Fallback-Suche) + Resultatauswahl
- ``scraper.extractor`` — Datenextraktion von der Song-Seite
"""

import argparse
import json
import random
import sys
import time

from playwright.sync_api import sync_playwright

from beatbase.core.config import SENTINEL_NONE
from beatbase.tunebat.browser.context import create_browser_context
from beatbase.tunebat.browser.navigator import find_best_result, perform_search
from beatbase.tunebat.config import HEADLESS
from beatbase.tunebat.scraper.extractor import extract_song_data
from beatbase.utils.log import log_status
from beatbase.utils.now_playing import read_now_playing_data
from beatbase.utils.search_variations import extract_featured_artists, generate_variations


# DEF: Künstlerliste und Suchbegriffe für Tunebat vorbereiten
def _prepare_search_data(
    song: str,
    artists: list[str],
    page=None,
) -> tuple[list[str], str, list[str]]:
    """SECTION: PREPARATION - Bereitet Künstlerliste, Zielstring und Suchbegriffe vor.

    Bei fehlender Artist-Liste wird optional ein F5-Reload ausgeloest und aus
    dem Titel werden Featured-Artists ergaenzt (nur sinnvoll, wenn schon eine
    Page-Instanz existiert).
    """
    if not artists:
        # Kurz warten wie ein Mensch der überlegt
        time.sleep(random.uniform(0.8, 1.4))

        if page is not None:
            log_status("⚠️ Keine Künstler – lade Seite neu...")
            # Menschlich: F5 drücken statt API-Reload
            page.keyboard.press("F5")
            time.sleep(random.uniform(1.2, 2.1))

            featured = extract_featured_artists(song)
            for artist in featured:
                if not any(artist.lower() in existing.lower() for existing in artists):
                    artists.append(artist)

    target_string = f"{song} {' '.join(artists)}".lower()
    queries = generate_variations(song, artists)
    return artists, target_string, queries


# DEF: Eigentlichen Such- und Extraktions-Workflow ausführen
def _execute_tunebat_search(
    page,
    song: str,
    artists: list[str],
    queries: list[str],
    target_string: str,
) -> dict | None:
    """SECTION: EXTRACTION - Probiert Suchvariationen, klickt den besten Treffer,
    extrahiert die Songdaten.
    """
    best_song_locator = None
    # Top 5 Variationen reichen erfahrungsgemaess auf Tunebat
    for query in queries[:5]:
        if not perform_search(page, query):
            continue
        best_song_locator = find_best_result(page, target_string, artists)
        if best_song_locator:
            break

    if not best_song_locator:
        log_status("⚠️ Kein passender Treffer auf Tunebat gefunden.")
        return None

    # Song-Seite per Klick laden (Bot-Detection Umgehung)
    log_status("🖱️ Klicke auf bestes Suchergebnis...")
    best_song_locator.click()
    page.wait_for_selector(".yIPfN", timeout=10000)

    return extract_song_data(page, song, artists)


# DEF: Tunebat Suche (Orchestrator)
def search_on_tunebat(
    song: str,
    artists: list[str],
    headless: bool = HEADLESS,
    dev_mode: bool = False,
    page=None,
) -> dict | None:
    """SECTION: ORCHESTRATION - Sucht auf Tunebat und liefert extrahierte Song-Details.

    Koordiniert Browser-Kontext, Datenvorbereitung und den eigentlichen
    Such-/Extraktions-Workflow. Im ``dev_mode`` wird der Browser nach der Suche
    fuer manuelle Inspektion offen gelassen (blockiert auf ``input()``).
    """
    actual_headless = False if dev_mode else headless
    artists, target_string, queries = _prepare_search_data(song, artists, page=page)

    if page:
        try:
            return _execute_tunebat_search(page, song, artists, queries, target_string)
        except Exception as e:
            log_status(f"❌ Fehler bei Tunebat: {e}")
            return None

    with sync_playwright() as p:
        context = create_browser_context(p, headless=actual_headless)
        new_page = context.new_page()
        try:
            return _execute_tunebat_search(new_page, song, artists, queries, target_string)
        except Exception as e:
            log_status(f"❌ Fehler bei Tunebat: {e}")
            return None
        finally:
            if dev_mode:
                log_status("\n🛠️ DEV-MODE: Browser bleibt offen. ENTER zum Schließen...")
                input("fertig...")
            context.close()


# DEF: Haupteinsprungpunkt
def main():
    """ENTRY: Einstiegspunkt für das Skript."""
    parser = argparse.ArgumentParser(description="Tunebat Metadata Scraper")
    parser.add_argument("query", nargs="?", help="Suchbegriff (Fallback: aktueller Song)")
    parser.add_argument("--song", help="Expliziter Songtitel")
    parser.add_argument("--artist", action="append", default=[], help="Expliziter Künstler")
    parser.add_argument("--headless", action="store_true", help="Browser im Headless-Modus")
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Browser mit UI öffnen",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Browser nach Suche offen lassen (stoppt Script)",
    )
    parser.set_defaults(headless=HEADLESS)
    args = parser.parse_args()

    song_name = args.song
    artists = args.artist

    if not song_name and args.query:
        song_name = args.query
        if " von " in song_name.lower():
            parts = song_name.lower().split(" von ")
            song_name = parts[0].strip()
            artists = [parts[1].strip()]

    if not song_name:
        data = read_now_playing_data()
        song_name = data.get("song")
        artists = data.get("artists", [])

    if not song_name or song_name == SENTINEL_NONE:
        log_status("❌ Kein Suchbegriff angegeben.")
        sys.exit(1)

    log_status(f"⏳ Suche auf Tunebat: '{song_name}'...")
    ergebnis = search_on_tunebat(song_name, artists, headless=args.headless, dev_mode=args.dev)
    if ergebnis:
        print(json.dumps(ergebnis, indent=4, ensure_ascii=False))
    else:
        log_status("❌ Keine Details gefunden.")
        sys.exit(1)


if __name__ == "__main__":
    main()
