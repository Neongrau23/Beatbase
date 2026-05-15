"""Zentraler Scraper für songbpm.com.

Nutzt Playwright für die Suche und BeautifulSoup für die Extraktion der Vibe-Texte.
"""

import argparse
import json
import sys

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from beatbase.core.config import SENTINEL_NONE, SONGBPM_URL
from beatbase.songbpm.scraper.extractor import extract_song_info
from beatbase.utils.log import log_status
from beatbase.utils.now_playing import read_now_playing_data


# DEF: search_on_songbpm(query, headless) -> dict | None
def search_on_songbpm(song: str, artists: list[str], headless: bool = True) -> dict | None:
    """Führt eine Suche auf SongBPM aus und extrahiert die Details des besten Treffers."""
    search_query = f"{song} {', '.join(artists)}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)  # ✅ Erst Browser starten
        page = browser.new_page()  # ✅ Dann Page erstellen
        try:
            log_status(f"🔗 Suche auf SongBPM: {search_query}")
            page.goto(SONGBPM_URL)  # ✅ Erst navigieren

            # ✅ Cookie-Dialog erst nach dem Laden prüfen
            dialog = page.get_by_role("dialog", name="Zustimmung zu Cookies &")
            if dialog.is_visible():
                page.get_by_role("button", name="Alle akzeptieren").click()

            # Suche ausführen
            search_selector = 'input[type="text"]'
            page.fill(search_selector, search_query)
            page.keyboard.press("Enter")

            page.wait_for_url("**/searches/**", timeout=15000)

            soup = BeautifulSoup(page.content(), "html.parser")
            song_links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if href.startswith("/@") and not href.endswith("/apple-music"):
                    song_links.append(SONGBPM_URL.rstrip("/") + "/" + href.lstrip("/"))

            if not song_links:
                log_status("⚠️  Keine Links auf SongBPM gefunden.")
                return None

            return extract_song_info(song_links[0])

        except Exception as e:
            log_status(f"❌ Fehler bei der SongBPM-Suche: {e}")
            return None

        finally:
            browser.close()  # ✅ Wird immer ausgeführt, auch bei Exception


# DEF: main()
def main():
    """CLI-Einstiegspunkt für Tests."""
    parser = argparse.ArgumentParser(description="SongBPM Scraper CLI")
    parser.add_argument("query", nargs="?", help="Suchbegriff")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    song_name = args.query
    artists = []

    if not song_name:
        data = read_now_playing_data()
        song_name = data.get("song")
        artists = data.get("artists", [])

    if not song_name or song_name == SENTINEL_NONE:
        log_status("❌ Kein Suchbegriff.")
        sys.exit(1)

    result = search_on_songbpm(song_name, artists, headless=args.headless)
    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
