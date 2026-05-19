import time

from beatbase.extractor.songstats.config import MATCH_THRESHOLD
from beatbase.shared.config import SONGSTATS_URL
from beatbase.shared.utils.cookie_manager import wait_for_and_dismiss_cookies
from beatbase.shared.utils.log import log_status
from beatbase.shared.utils.playwright_errors import is_browser_closed_error
from beatbase.shared.utils.validator import calculate_validation_score


# DEF: find_song_profile(page, queries, target_string, artists) -> bool
def find_song_profile(page, queries: list[str], target_string: str, artists: list[str]) -> bool:
    """Führt die Suchanfragen iterativ auf Songstats aus und navigiert zum besten Treffer.

    Args:
        page: Playwright Page-Objekt.
        queries: Liste der Suchstrings.
        target_string: Ursprungs-Suchstring zur Validierung der Ergebnisse.
        artists: Liste der erwarteten Künstler.

    Returns:
        True, wenn ein valides Profil gefunden und angeklickt wurde, sonst False.
    """
    for query in queries:
        log_status(f"  -> Versuche: '{query}'")
        try:
            page.goto(SONGSTATS_URL, wait_until="domcontentloaded")

            # Zentrales Cookie-Management nutzen
            wait_for_and_dismiss_cookies(page)

            search_box = page.wait_for_selector('input[type="text"]', timeout=5000)
            search_box.fill(query)
            page.keyboard.press("Enter")
            start_time = time.time()
            best_candidate, max_score = None, 0

            # Überwacht das Dropdown/Suchergebnis für 3 Sekunden dynamisch
            while time.time() - start_time < 3:
                rows = page.locator('div[style*="cursor: pointer"]:has(img)').all()
                for row in rows:
                    try:
                        text = row.inner_text().replace("\n", " ")
                        score = calculate_validation_score(text, target_string, artists)
                        if score > max_score:
                            max_score, best_candidate = score, row
                    except Exception:
                        continue
                if max_score > 0.95:  # Fast perfekter Match, breche die Suche vorzeitig ab
                    break
                time.sleep(0.2)

            if best_candidate and max_score > MATCH_THRESHOLD:
                best_candidate.click()
                return True
        except Exception as e:
            # WHY: Browser-Crashes muessen den Pool-Worker erreichen, damit er den
            # Browser neu hochzieht. Echte Scraper-Fehler (Timeout, missing
            # Element) loggen und mit der naechsten Query weitermachen.
            if is_browser_closed_error(e):
                raise
            log_status(f"  ⚠️ Songstats-Query '{query}' fehlgeschlagen: {e}")
    return False
