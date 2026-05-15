"""Zentraler Scraper für songbpm.com.

Nutzt Playwright für die Suche und BeautifulSoup für die Extraktion der Vibe-Texte.
"""

import argparse
import json
import re
import sys

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from beatbase.core.config import SENTINEL_NONE, SONGBPM_URL
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


# DEF: extract_song_info(url) -> dict | None
def extract_song_info(url: str) -> dict | None:
    """Extrahiert Metadaten und die Beschreibung von einer SongBPM Detailseite."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        # MARK: - Metriken Parsing
        def metric(name):
            dt = soup.find("dt", string=re.compile(name))
            if not dt:
                return None
            return dt.find_next_sibling("dd").get_text(strip=True)

        # MARK: - Entity Extraktion
        artist = soup.find("h2").get_text(strip=True) if soup.find("h2") else None
        song_title = soup.find("h1").get_text(strip=True) if soup.find("h1") else None

        # Die wichtige Vibe-Beschreibung
        desc_div = soup.find("div", class_=re.compile(r"lg:prose-xl"))
        description = desc_div.get_text(" ", strip=True) if desc_div else None

        spotify_link = soup.find("a", href=re.compile(r"spotify\.com/track"))

        details = {
            "artist": artist,
            "title": song_title,
            "key": metric("Key"),
            "duration": metric("Duration"),
            "bpm": metric(r"Tempo \(BPM\)"),
            "description": description,
            "spotify_url": spotify_link["href"] if spotify_link else None,
            "url": url,
        }

        # Nur gefüllte Werte behalten
        details = {k: v for k, v in details.items() if v is not None}

        log_status(f"✅ SongBPM Details geladen: {details.get('description', 'Keine Beschreibung')[:100]}...")
        log_status(f"📊 SongBPM Daten: {json.dumps(details, indent=4, ensure_ascii=False)}")
        return details

    except Exception as e:
        log_status(f"❌ Fehler beim Laden von SongBPM Details: {e}")
        return None


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
