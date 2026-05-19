"""Navigation und Seitensteuerung für den Genius-Scraper über Playwright."""

import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext, Page

from beatbase.extractor.genius.config import MATCH_THRESHOLD, PAGE_LOAD_SLEEP
from beatbase.extractor.genius.scraper.extractor import extract_artist_songs
from beatbase.shared.config import GENIUS_URL
from beatbase.shared.utils.cookie_manager import wait_for_and_dismiss_cookies
from beatbase.shared.utils.log import log_status
from beatbase.shared.utils.validator import calculate_validation_score

# CONFIG: Sicherheits-Cap fuer das Voll-Scrollen einer Artist-Songs-Liste.
# WHY: Genius nutzt Infinite Scroll; ohne Cap koennte ein Bug zu Endlos-Loop fuehren.
MAX_ARTIST_SONG_SCROLLS = 50
# Anzahl aufeinanderfolgender Scrolls ohne neue Karten, bevor wir abbrechen.
SCROLL_STAGNATION_LIMIT = 3
# Maximale Anzahl Such-Queries, die wir nacheinander durchprobieren.
MAX_SEARCH_QUERIES = 3
# Score, ab dem wir die Query-Schleife sofort abbrechen.
EARLY_EXIT_SCORE = 0.95


# DEF: Scrollt die Artist-Songs-Seite bis ans Ende und sammelt alle Karten
def _scroll_collect_artist_songs(page: Page) -> list[dict]:
    """Scrollt bis kein neuer Content mehr nachgeladen wird und liefert alle Songs.

    Bricht ab, wenn drei aufeinanderfolgende Scrolls keine neuen Karten mehr
    bringen oder ``MAX_ARTIST_SONG_SCROLLS`` ueberschritten ist.
    """
    prev_count = -1
    stagnation = 0
    songs: list[dict] = []

    for _ in range(MAX_ARTIST_SONG_SCROLLS):
        soup = BeautifulSoup(page.content(), "html.parser")
        songs = extract_artist_songs(soup)

        if len(songs) == prev_count:
            stagnation += 1
            if stagnation >= SCROLL_STAGNATION_LIMIT:
                break
        else:
            stagnation = 0
            prev_count = len(songs)

        page.mouse.wheel(0, 3000)
        time.sleep(1)

    log_status(f"  🎼 Artist-Songs gesammelt: {len(songs)} Eintrag(e)")
    return songs


# DEF: Tippt Query in die Suchbox und drueckt Enter
def _submit_search(page: Page, query: str) -> None:
    """Leert die Suchbox und sendet die naechste Query ab."""
    search_box = page.get_by_role("textbox", name="Search lyrics & more")
    search_box.click()
    search_box.fill("")
    search_box.fill(query)
    search_box.press("Enter")


# DEF: Bewertet die Song-Cards der Suchergebnis-Seite
def _best_song_card(
    soup: BeautifulSoup, target_string: str, artists: list[str]
) -> tuple[str | None, float]:
    """Liefert die beste Song-URL aus den Treffern plus deren Score."""
    best_link: str | None = None
    max_score = 0.0

    cards = soup.select("mini-song-card a.mini_card")
    for card in cards:
        title_elem = card.select_one(".mini_card-title")
        subtitle_elem = card.select_one(".mini_card-subtitle")
        if not title_elem:
            continue

        title_text = title_elem.get_text(strip=True)
        subtitle_text = subtitle_elem.get_text(strip=True) if subtitle_elem else ""
        compare_text = f"{title_text} {subtitle_text}"
        score: float = calculate_validation_score(compare_text, target_string, artists)

        if score > max_score:
            max_score = score
            href = card.get("href")
            if href:
                best_link = href if href.startswith("http") else GENIUS_URL + href

    return best_link, max_score


# DEF: Sucht den Song direkt ueber Genius' Suche (Song-Card Treffer)
def _find_song_in_search_results(
    page: Page,
    queries: list[str],
    target_string: str,
    artists: list[str],
) -> str | None:
    """Probiert mehrere ``song artist``-Queries und liefert die beste Song-URL.

    Args:
        page: Aktive Playwright-Page (bringt eigenen Context mit).
        queries: Reihenfolge der Suchstrings (aus ``generate_variations``).
        target_string: Normalisierter Vergleichsstring fuer das Scoring.
        artists: Beteiligte Kuenstler (fuer den Artist-Bonus im Score).

    Returns:
        Vollstaendige Song-URL oder ``None``, wenn keine Query > ``MATCH_THRESHOLD``
        gepunktet hat.
    """
    if not queries:
        return None

    # Genius oeffnen + Cookie-Banner einmalig.
    page.goto(GENIUS_URL)
    wait_for_and_dismiss_cookies(page)

    best_overall_link: str | None = None
    best_overall_score = 0.0

    for query in queries[:MAX_SEARCH_QUERIES]:
        log_status(f"  🔍 Genius-Suche: '{query}'")
        try:
            _submit_search(page, query)
            page.wait_for_selector("search-result-section", timeout=10000)
            # WHY: Suche rendert mini-song-card lazy — kurz warten.
            page.wait_for_selector("mini-song-card a.mini_card", timeout=5000)
        except Exception as e:
            log_status(f"    ⚠️ Keine Suchergebnisse fuer '{query}': {e}")
            continue

        soup = BeautifulSoup(page.content(), "html.parser")
        link, score = _best_song_card(soup, target_string, artists)
        log_status(f"    📊 Bester Treffer-Score: {score:.2f}")

        if link and score > best_overall_score:
            best_overall_link = link
            best_overall_score = score

        if best_overall_score >= EARLY_EXIT_SCORE:
            break

    if best_overall_link and best_overall_score > MATCH_THRESHOLD:
        log_status(
            f"  ✅ Song-URL: {best_overall_link} (Score {best_overall_score:.2f})"
        )
        return best_overall_link

    log_status(
        f"  ❌ Kein ausreichender Treffer (max Score {best_overall_score:.2f})."
    )
    return None


# DEF: Oeffnet pro Artist eine neue Page und sammelt alle Songs
def collect_songs_for_artists(
    context: BrowserContext, artist_urls: list[str]
) -> list[dict]:
    """Sequenzielle Sammlung aller Songs aller beteiligten Kuenstler.

    Pro Artist-Profil-URL: neue Page oeffnen, Profil laden, "Show all songs"
    klicken und mit ``_scroll_collect_artist_songs`` durchscrollen. Fehler
    einer Artist-Seite stoppen die Gesamtsammlung nicht.
    """
    aggregated: list[dict] = []
    seen_urls: set[str] = set()

    for artist_url in artist_urls:
        log_status(f"  👤 Artist-Profil: {artist_url}")
        new_page = context.new_page()
        try:
            new_page.goto(artist_url)
            wait_for_and_dismiss_cookies(new_page)

            try:
                all_songs_link = new_page.get_by_role(
                    "link", name=re.compile("Show all songs", re.I)
                )
                all_songs_link.click(timeout=10000)
            except Exception as e:
                log_status(f"    ⚠️ 'Show all songs' nicht klickbar: {e}")
                continue

            try:
                new_page.wait_for_selector("mini-song-card, .mini_card", timeout=10000)
            except Exception:
                log_status("    ⚠️ Keine Songkarten auf der Artist-Songs-Seite.")
                continue

            songs = _scroll_collect_artist_songs(new_page)
            for song in songs:
                url = song.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                aggregated.append(song)
        except Exception as e:
            log_status(f"    ⚠️ Artist-Seite fehlgeschlagen ({artist_url}): {e}")
        finally:
            new_page.close()

    return aggregated


# DEF: Findet die Song-URL ueber kombinierten Song+Artist-Query
def find_song_url(
    page: Page,
    queries: list[str],
    target_string: str,
    artists: list[str],
) -> str | None:
    """Liefert die Genius-Song-URL fuer den passenden Treffer oder ``None``.

    Die fruehere Artist-Profil-Suche wurde ersetzt: Wir tippen ``song artist``
    direkt in die Suche und waehlen die beste Song-Card. Artist-Songs werden
    danach separat ueber ``collect_songs_for_artists`` aus den Header-Links
    der Song-Seite gesammelt.
    """
    if not queries:
        log_status("  ⚠️ Keine Such-Queries generiert.")
        return None

    try:
        return _find_song_in_search_results(page, queries, target_string, artists)
    except Exception as e:
        log_status(f"  ⚠️ Fehler in der Song-Suche: {e}")
        raise


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
