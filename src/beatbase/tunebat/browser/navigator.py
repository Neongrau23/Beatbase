"""Logik zum Navigieren und Finden von Suchergebnissen auf Tunebat."""

import os
import re
import time

from playwright.sync_api import Locator, Page

from beatbase.tunebat.config import MATCH_THRESHOLD
from beatbase.utils.log import log_status
from beatbase.utils.validator import calculate_validation_score


def _save_debug_html(target_string: str, html_content: str):
    """Speichert den HTML-Inhalt für Debugging-Zwecke."""
    try:
        os.makedirs("data/tunebat_searches", exist_ok=True)
        # Ersetze ungültige Dateinamen-Zeichen, wandle Leerzeichen in Bindestriche um
        safe_name = re.sub(r"[^a-zA-Z0-9\s-]", "", target_string).strip()
        safe_name = re.sub(r"\s+", "-", safe_name)
        file_path = f"data/tunebat_searches/{safe_name}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        log_status(f"  ⚠️ Fehler beim Speichern der HTML: {e}")


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

        # --- Load more Pagination Logik ---
        # Versuche bis zu 4 Mal, den "Load more"-Button zu klicken
        for _ in range(4):
            try:
                load_more_btn = page.get_by_role("button", name=re.compile(r"Load more", re.I))
                if load_more_btn.is_visible(timeout=1000):
                    # Vorherige Anzahl der Ergebnisse merken
                    previous_count = page.locator(".pDoqI").count()

                    load_more_btn.click()

                    # Kurz warten, ob mehr Ergebnisse laden
                    try:
                        # Warte darauf, dass die Anzahl der .pDoqI-Elemente größer wird
                        page.wait_for_function(
                            f"document.querySelectorAll('.pDoqI').length > {previous_count}",
                            timeout=3000,
                        )
                    except Exception:
                        # Wenn nicht mehr Ergebnisse kommen, hoch und wieder runter scrollen,
                        # und nochmal klicken.
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.5)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(0.5)

                        try:
                            load_more_btn.click()
                            page.wait_for_function(
                                f"document.querySelectorAll('.pDoqI').length > {previous_count}",
                                timeout=3000,
                            )
                        except Exception:
                            break  # Hat trotzdem nicht geklappt, breche die Pagination ab
                else:
                    break  # Kein Button mehr sichtbar
            except Exception:
                break  # Allgemeiner Fehler beim Button-Handling
        # ----------------------------------

        # Speichere die HTML des Containers (inklusive aller nachgeladenen Ergebnisse)
        try:
            html_content = results_container.inner_html()
            _save_debug_html(target_string, html_content)
        except Exception:
            pass

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
