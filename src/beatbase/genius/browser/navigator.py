"""Navigation und Seitensteuerung für den Genius-Scraper über Playwright."""

import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from beatbase.core.config import GENIUS_URL
from beatbase.genius.config import MATCH_THRESHOLD, PAGE_LOAD_SLEEP
from beatbase.genius.validator import calculate_validation_score
from beatbase.utils.log import log_status


# DEF: Sucht Song-URL über Künstler-Profil
def find_song_url(page: Page, queries: list[str], target_string: str, artists: list[str]) -> str | None:
    """Sucht auf Genius zuerst den Künstler über mini-artist-card und dann den Song in dessen Liste.

    Args:
        page: Ein aktives Playwright Page-Objekt.
        queries: Liste der Suchstrings.
        target_string: Der zusammengesetzte Zielstring zur Validierung.
        artists: Liste der beteiligten Künstler (erster ist der Haupt-Künstler).

    Returns:
        Die vollständige URL des Song-Treffers, oder None wenn nichts gefunden.
    """
    if not artists:
        log_status("  ⚠️ Keine Künstler für die Suche angegeben.")
        return None

    main_artist = artists[0]
    song_name = queries[0] if queries else ""
    log_status(f"  🔍 Präzise Profil-Suche: '{main_artist}' -> '{song_name}'")

    try:
        # STEP 1: Suche nach dem Künstler
        page.goto(GENIUS_URL)

        try:
            accept_btn = page.get_by_role("button", name="Akzeptieren")
            if accept_btn.is_visible(timeout=2000):
                accept_btn.click()
        except Exception:
            pass

        search_box = page.get_by_role("textbox", name="Search lyrics & more")
        search_box.click()
        search_box.fill(main_artist)
        search_box.press("Enter")

        # STEP 2: Identifiziere den Künstler über <mini-artist-card>
        # Wir warten darauf, dass die Resultate-Sektion geladen wird
        page.wait_for_selector("search-result-section", timeout=10000)

        # Wir suchen alle mini-artist-cards
        artist_cards = page.locator("mini-artist-card").all()
        target_profile_url = None

        for card in artist_cards:
            # Der Name steht in .mini_card-title
            name_elem = card.locator(".mini_card-title")
            if name_elem.count() > 0:
                card_name = name_elem.inner_text().strip()
                # Falls der Name passt (case-insensitive)
                if card_name.lower() == main_artist.lower():
                    # Der Link ist das <a> Tag in der Card
                    link_elem = card.locator("a.mini_card")
                    target_profile_url = link_elem.get_attribute("href")
                    if target_profile_url:
                        link_elem.click()
                        break

        if not target_profile_url:
            log_status(f"  ⚠️ Kein präzises Profil für '{main_artist}' in den Artist-Cards gefunden.")
            # Fallback: Versuche den ersten Artist-Link überhaupt
            fallback_link = page.locator("mini-artist-card a.mini_card").first
            if fallback_link.count() > 0:
                log_status("  💡 Nutze ersten verfügbaren Artist-Treffer als Fallback.")
                fallback_link.click()
            else:
                return None

        log_status(f"  ✅ Künstler-Profil von '{main_artist}' geöffnet.")

        # STEP 3: "Show all songs" öffnen
        all_songs_link = page.get_by_role("link", name=re.compile("Show all songs", re.I))
        all_songs_link.click()
        log_status("  📂 Vollständige Songliste geöffnet.")

        # STEP 4: In der Liste nach dem Song suchen (via mini-song-card)
        best_link = None
        max_score = 0

        # Bis zu 5 Scroll-Versuche für Infinite Scroll
        for scroll_attempt in range(5):
            # Warten auf Song-Karten
            page.wait_for_selector("mini-song-card, .mini_card", timeout=10000)

            # Wir nutzen BeautifulSoup für das schnelle Scannen der Liste
            soup = BeautifulSoup(page.content(), "html.parser")
            # Wir suchen mini-song-card oder .mini_card (je nachdem was geladen wurde)
            song_cards = soup.select("mini-song-card a.mini_card, .profile_list_item a.mini_card")

            for card in song_cards:
                title_elem = card.select_one(".mini_card-title")
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    compare_text = f"{title_text} {main_artist}"
                    score: float = calculate_validation_score(compare_text, target_string, artists)

                    if score > max_score:
                        max_score = score
                        best_link = card.get("href")

            if max_score > 0.95:
                break

            page.mouse.wheel(0, 2000)
            time.sleep(1)

        if best_link and max_score > MATCH_THRESHOLD:
            if not best_link.startswith("http"):
                best_link = GENIUS_URL + best_link
            log_status(f"  ✅ Song gefunden: '{best_link}' ({max_score:.2f} Score)")
            return best_link

    except Exception as e:
        log_status(f"  ⚠️ Fehler bei der präzisen Profil-Suche: {e}")

    return None


# DEF: Lädt Song-Seite und extrahiert Soup
def load_song_page(page: Page, url: str) -> BeautifulSoup:
    """Navigiert zur Song-Seite und bereitet den DOM für die Extraktion vor.

    Args:
        page: Ein aktives Playwright Page-Objekt.
        url: Die vollständige Genius-Song-URL.

    Returns:
        BeautifulSoup-Objekt des vollständig geladenen DOM.
    """
    page.goto(url)

    # Scrollen für Lazy-Load der Lyrics
    page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(PAGE_LOAD_SLEEP)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(PAGE_LOAD_SLEEP)

    try:
        page.wait_for_selector("[data-lyrics-container='true']", timeout=10000)
    except Exception:
        log_status("    ⚠️ Lyrics-Container nicht gefunden (Timeout).")

    return BeautifulSoup(page.content(), "html.parser")
