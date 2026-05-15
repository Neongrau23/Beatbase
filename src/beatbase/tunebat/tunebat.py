"""CLI-Einstiegspunkt für den Tunebat-Scraper."""

import argparse
import json
import random
import sys
import time

from playwright.sync_api import sync_playwright

from beatbase.core.config import SENTINEL_NONE, TUNEBAT_URL
from beatbase.tunebat.browser.context import create_browser_context
from beatbase.tunebat.browser.navigator import find_best_result
from beatbase.tunebat.config import HEADLESS
from beatbase.utils.cookie_manager import wait_for_and_dismiss_cookies
from beatbase.utils.log import log_status
from beatbase.utils.now_playing import read_now_playing_data
from beatbase.utils.search_variations import extract_featured_artists, generate_variations


# DEF: Tunebat Suche
def search_on_tunebat(song: str, artists: list[str], headless: bool = HEADLESS, dev_mode: bool = False, page=None) -> dict | None:
    """Suche auf Tunebat mit Variations-Strategie."""
    actual_headless = False if dev_mode else headless

    if not artists:
        # Kurz warten wie ein Mensch der überlegt
        time.sleep(random.uniform(0.8, 1.4))

        if page is not None:
            log_status("⚠️ Keine Künstler – lade Seite neu...")
            # Menschlich: F5 drücken statt API-Reload
            page.keyboard.press("F5")
            # Kurze Pause nach dem Reload wie ein Mensch der wartet
            time.sleep(random.uniform(1.2, 2.1))

            featured = extract_featured_artists(song)
            for artist in featured:
                if not any(artist.lower() in existing.lower() for existing in artists):
                    artists.append(artist)

    target_string = f"{song} {' '.join(artists)}".lower()
    queries = generate_variations(song, artists)

    def _do_search(active_page):
        best_song_locator = None

        for query in queries[:5]:  # Auf Tunebat reichen meist die Top 5 Variationen
            log_status(f"🔗 Suche auf Tunebat: '{query}'")
            active_page.goto(TUNEBAT_URL)

            # Zentrales Cookie-Management nutzen
            wait_for_and_dismiss_cookies(active_page)

            # Suche ausführen (Gezielter Zugriff auf den oberen Suchbereich im Header)
            search_input = active_page.locator(".ant-input-search input[aria-label='Song search field']").first
            if not search_input.is_visible(timeout=5000):
                # Fallback auf den mittleren Bereich, falls der Header-Bereich nicht da ist
                search_input = active_page.get_by_role("main").get_by_role("textbox", name="Song search field")
            
            if not search_input.is_visible(timeout=5000):
                continue

            search_input.fill(query)
            search_input.press("Enter")

            # Resultat finden
            best_song_locator = find_best_result(active_page, target_string, artists)
            if best_song_locator:
                break

        if not best_song_locator:
            log_status("⚠️ Kein passender Treffer auf Tunebat gefunden.")
            return None

        # Song-Seite laden per Klick (Bot-Detection Umgehung)
        log_status("🖱️ Klicke auf bestes Suchergebnis...")
        best_song_locator.click()
        active_page.wait_for_selector(".yIPfN", timeout=10000)

        # SECTION: Datenextraktion
        log_status("🔍 Extrahiere Metriken...")
        results = {}

        # 1. Key, BPM, Duration
        try:
            metrics_containers = active_page.locator(".yIPfN")
            for i in range(metrics_containers.count()):
                container = metrics_containers.nth(i)
                value = container.locator("h3").inner_text().strip()
                label = container.locator("span.ant-typography-secondary").inner_text().strip().lower()
                results[label] = value
        except Exception:
            pass

        # 2. Progress-Metriken (Popularity, Energy, etc.)
        try:
            progress_containers = active_page.locator("._1MCwQ")
            for i in range(progress_containers.count()):
                container = progress_containers.nth(i)
                value_elem = container.locator(".ant-progress-text")
                label_elem = container.locator("span.ant-typography").last

                if value_elem.count() > 0 and label_elem.count() > 0:
                    val = value_elem.inner_text().strip()
                    lab = label_elem.inner_text().strip().lower()
                    results[lab] = val
        except Exception:
            pass

        # 3. Metadaten (Release Date, Label, etc.)
        try:
            meta_container = active_page.locator("._4aYzP")
            if meta_container.count() > 0:
                meta_items = meta_container.locator("div")
                for i in range(meta_items.count()):
                    item = meta_items.nth(i)
                    text = item.inner_text().strip()
                    if ":" in text:
                        parts = text.split(":", 1)
                        if len(parts) == 2:
                            lab = parts[0].strip().lower().replace(" ", "_")
                            val = parts[1].strip()
                            results[lab] = val
        except Exception:
            pass

        # 4. Direkter Songstats-Link
        songstats_url = None
        try:
            songstats_link = active_page.locator("a[aria-label='Songstats']")
            if songstats_link.count() > 0:
                href = songstats_link.first.get_attribute("href")
                if href:
                    # &source=overview anhängen, damit Songstats nicht auf Spotify weiterleitet
                    songstats_url = f"{href.split('?')[0]}?source=overview"
        except Exception:
            pass

        audio_features_keys = ["acousticness", "danceability", "energy", "instrumentalness", "liveness", "speechiness", "happiness", "loudness"]

        formatted_results = {
            "url": active_page.url,
            "title": song,
            "artist": ", ".join(artists),
            "key": results.get("key"),
            "camelot": results.get("camelot"),
            "bpm": results.get("bpm"),
            "duration": results.get("duration"),
            "popularity": results.get("popularity"),
            "release_date": results.get("release_date"),
            "explicit": results.get("explicit"),
            "album": results.get("album"),
            "label": results.get("label"),
            "audio_features": {k: results.get(k) for k in audio_features_keys if k in results},
            "songstats_url": songstats_url,
        }

        formatted_results = {k: v for k, v in formatted_results.items() if v is not None}
        log_status("✅ Daten extrahiert.")
        return formatted_results

    if page:
        try:
            return _do_search(page)
        except Exception as e:
            log_status(f"❌ Fehler bei Tunebat: {e}")
            return None
    else:
        with sync_playwright() as p:
            context = create_browser_context(p, headless=actual_headless)
            browser = context.browser
            new_page = context.new_page()
            try:
                return _do_search(new_page)
            except Exception as e:
                log_status(f"❌ Fehler bei Tunebat: {e}")
            finally:
                if dev_mode:
                    log_status("\n🛠️ DEV-MODE: Browser bleibt offen. Drücke ENTER zum Schließen...")
                    input("fertig...")
                context.close()
                if browser:
                    browser.close()
        return None


# DEF: Haupteinsprungpunkt
def main():
    """ENTRY: Einstiegspunkt für das Skript."""
    parser = argparse.ArgumentParser(description="Tunebat Metadata Scraper")
    parser.add_argument("query", nargs="?", help="Suchbegriff (Fallback: aktueller Song)")
    parser.add_argument("--song", help="Expliziter Songtitel")
    parser.add_argument("--artist", action="append", default=[], help="Expliziter Künstler")
    parser.add_argument("--headless", action="store_true", help="Browser im Headless-Modus")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Browser mit UI öffnen")
    parser.add_argument("--dev", action="store_true", help="Browser nach Suche offen lassen (stoppt Script)")
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
