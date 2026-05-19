"""Zentraler Scraper für songbpm.com.

Nutzt Playwright für die Suche und BeautifulSoup für die Extraktion der Vibe-Texte.
"""

import argparse
import json
import sys

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from beatbase.extractor.songbpm.scraper.extractor import extract_song_info
from beatbase.shared.config import SENTINEL_NONE, SONGBPM_URL
from beatbase.shared.now_playing import read_now_playing_data
from beatbase.shared.utils.cookie_manager import wait_for_and_dismiss_cookies
from beatbase.shared.utils.log import log_status
from beatbase.shared.utils.playwright_errors import is_browser_closed_error


# DEF: search_on_songbpm(query, headless) -> dict | None
def search_on_songbpm(
    song: str,
    artists: list[str],
    headless: bool = True,
    page=None,
    album: str | None = None,
) -> dict | None:
    """Führt eine Suche auf SongBPM aus und extrahiert die Details des besten Treffers.

    ``album`` wird vom Orchestrator pipeline-einheitlich durchgereicht, aber
    von SongBPM derzeit nicht genutzt. Platzhalter fuer kuenftige
    Album-spezifische Suchstrategien.
    """
    search_query = f"{song} {', '.join(artists)}"

    def _do_search(active_page):
        try:
            log_status(f"🔗 Suche auf SongBPM: {search_query}")
            active_page.goto(SONGBPM_URL)  # ✅ Erst navigieren

            # Zentrales Cookie-Management nutzen
            wait_for_and_dismiss_cookies(active_page)

            # Suche ausführen
            search_selector = 'input[type="text"]'
            active_page.fill(search_selector, search_query)
            active_page.keyboard.press("Enter")

            # Warte auf einen Resultat-Link (Song-Links fangen mit /@ an)
            active_page.wait_for_selector('a[href^="/@"]', timeout=15000)

            soup = BeautifulSoup(active_page.content(), "html.parser")
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
            if is_browser_closed_error(e):
                raise
            log_status(f"❌ Fehler bei der SongBPM-Suche: {e}")
            return None

    if page:
        return _do_search(page)
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)  # ✅ Erst Browser starten
            new_page = browser.new_page()  # ✅ Dann Page erstellen
            try:
                return _do_search(new_page)
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
