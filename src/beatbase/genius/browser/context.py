"""Playwright Chromium-Kontext für den Genius-Scraper."""

import os

from playwright.sync_api import BrowserContext, Playwright

from beatbase.genius.config import HEADLESS, PROFILE_DIR, USER_AGENT


# DEF: Erstellt Playwright Kontext
def create_playwright_context(playwright: Playwright, headless: bool = HEADLESS) -> BrowserContext:
    """Erstellt und gibt einen konfigurierten Playwright Chromium-Kontext zurück.

    Nutzt einen absoluten Pfad für das Profil, um Konflikte zu vermeiden.
    """
    # WHY: Absoluter Pfad ist sicherer gegen CWD-Wechsel
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    profile_dir = os.path.join(base_dir, PROFILE_DIR)

    # Wir reduzieren die Flags auf das Minimum, um Inkompatibilitäten zu vermeiden
    context = playwright.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=headless, user_agent=USER_AGENT, args=["--disable-blink-features=AutomationControlled"])

    return context
