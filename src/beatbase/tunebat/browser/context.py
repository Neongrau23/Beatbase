import os

from playwright.sync_api import BrowserContext, Playwright

from beatbase.tunebat.config import PROFILE_DIR, USER_AGENT


# DEF: create_browser_context(p, headless) -> BrowserContext
def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    """Erstellt einen Browser-Kontext für Tunebat mit Stealth-Optionen."""

    # WHY: Absoluter Pfad ist sicherer gegen CWD-Wechsel
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    profile_dir = os.path.join(base_dir, PROFILE_DIR)

    context = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=headless, user_agent=USER_AGENT, args=["--disable-blink-features=AutomationControlled"])
    return context
