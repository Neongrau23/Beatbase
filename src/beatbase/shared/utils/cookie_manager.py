"""Zentrales Cookie-Management für alle Scraper.

Dieses Modul bietet Funktionen zum robusten Erkennen und Schließen von
Cookie-Bannern und Zustimmungs-Dialogen auf verschiedenen Webseiten.
"""

import time

from playwright.sync_api import Page

from beatbase.shared.utils.log import log_status

# CONFIG: Bekannte IDs und Texte für Cookie-Buttons
COOKIE_SELECTORS = [
    # OneTrust (Genius, Songstats)
    "#onetrust-accept-btn-handler",
    # Standard-Rollen und Texte
    "button:has-text('Accept')",
    "button:has-text('Akzeptieren')",
    "button:has-text('Zustimmen')",
    "button:has-text('Alle akzeptieren')",
    "button:has-text('Agree')",
    # Spezielle Dialog-Buttons
    "role=button[name*='akzeptieren' i]",
    "role=button[name*='accept' i]",
    # SongBPM spezifisch
    "button:has-text('Zustimmung zu Cookies')",
]


# DEF: Dismiss Cookie Banner
def dismiss_cookie_banner(page: Page, timeout_ms: int = 3000) -> bool:
    """SECTION: COOKIES - Sucht aktiv nach Cookie-Bannern und klickt auf 'Akzeptieren'.

    Wird von den Scrapern aufgerufen, wenn ein Banner den Zugriff blockiert.
    """
    for selector in COOKIE_SELECTORS:
        try:
            # Wir prüfen, ob der Selector existiert und sichtbar ist
            locator = page.locator(selector).first
            if locator.is_visible(timeout=500):
                log_status(f"🍪 Cookie-Banner erkannt ({selector}). Klicke 'Akzeptieren'...")
                locator.click()
                # Kurze Pause, damit der Dialog verschwinden kann
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


# DEF: Wait and Dismiss
def wait_for_and_dismiss_cookies(page: Page, max_wait_seconds: int = 5) -> bool:
    """SECTION: COOKIES - Wartet eine Zeit lang auf das Erscheinen eines Banners.

    Hilfreich bei Seiten, wo der Banner verzögert nachgeladen wird.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if dismiss_cookie_banner(page):
            return True
        time.sleep(0.5)
    return False
