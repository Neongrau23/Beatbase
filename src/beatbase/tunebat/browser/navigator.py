"""Logik zum Navigieren und Finden von Suchergebnissen auf Tunebat."""

from playwright.sync_api import Locator, Page

from beatbase.tunebat.config import MATCH_THRESHOLD
from beatbase.tunebat.validator import calculate_validation_score
from beatbase.utils.log import log_status


# DEF: find_best_result(page, target_string, artists) -> Locator | None
def find_best_result(page: Page, target_string: str, artists: list[str]) -> Locator | None:
    """Findet das beste Suchergebnis auf der Tunebat-Resultatseite und gibt dessen Locator zurück.

    Analysiert die Resultat-Container in div.hl7iF.
    """
    try:
        # Tunebat listet Ergebnisse in div.hl7iF, jeder Song ist ein div.pDoqI
        results_container = page.locator(".hl7iF")

        # Warte kurz, bis die Ergebnisse gerendert sind
        try:
            results_container.wait_for(state="visible", timeout=5000)
        except Exception:
            return None

        rows = results_container.locator(".pDoqI")
        count = rows.count()

        if count == 0:
            return None

        best_locator = None
        max_score = 0

        for i in range(min(count, 5)):  # Prüfe die Top 5 Ergebnisse
            row = rows.nth(i)

            try:
                # Extrahiere Künstler (_2zAVA) und Titel (aZDDf)
                artist_text = row.locator("._2zAVA").inner_text().strip()
                title_text = row.locator(".aZDDf").inner_text().strip()

                # Kombiniere für Validierung
                found_text = f"{title_text} {artist_text}"
                score = calculate_validation_score(found_text, target_string, artists)

                if score > max_score:
                    max_score = score
                    best_locator = row.locator("a").first
            except Exception:
                continue

        if best_locator and max_score > MATCH_THRESHOLD:
            log_status(f"  ✅ Treffer gefunden: {max_score:.2f} Score")
            return best_locator

    except Exception as e:
        log_status(f"⚠️ Fehler beim Navigieren durch Ergebnisse: {e}")

    return None
