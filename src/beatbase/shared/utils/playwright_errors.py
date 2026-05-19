"""Hilfsfunktionen rund um Playwright-Exceptions.

Zentralisiert die Erkennung von "Browser/Page/Context geschlossen"-Fehlern,
damit die Quellen alle dasselbe Verhalten zeigen — wenn der Browser tot ist,
re-raisen wir, damit der Pool-Worker den Browser neu hochziehen kann.
Echte Scraper-Fehler (Element nicht gefunden, Timeout auf einem Selektor)
werden weiterhin von den Quellen gefangen und als ``None`` zurueckgegeben.
"""

from playwright._impl._errors import TargetClosedError
from playwright.sync_api import Error as PlaywrightError


# DEF: is_browser_closed_error(exc) -> bool
def is_browser_closed_error(exc: BaseException) -> bool:
    """Sagt ja, wenn ``exc`` darauf hindeutet, dass Browser/Page/Context tot sind.

    Primaer ``TargetClosedError`` (Playwright wirft den, sobald Page/Context/Browser
    geschlossen sind). Als Sicherheit nehmen wir auch jeden ``PlaywrightError``,
    dessen Message den klassischen Wortlaut enthaelt — manche Code-Pfade in
    Playwright werfen den Basisfehler mit derselben Beschreibung.
    """
    if isinstance(exc, TargetClosedError):
        return True
    if isinstance(exc, PlaywrightError):
        msg = str(exc).lower()
        return (
            "target page" in msg
            or "target closed" in msg
            or "browser has been closed" in msg
            or "browser closed" in msg
            or "context or browser has been closed" in msg
        )
    return False
