"""Playwright Chromium-Kontext für den Genius-Scraper."""

from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright

from beatbase.genius.config import HEADLESS, PROFILE_DIR, USER_AGENT


# DEF: Erstellt Playwright Kontext
def create_playwright_context(
    playwright: Playwright, headless: bool = HEADLESS
) -> BrowserContext:
    """Erstellt und gibt einen konfigurierten Playwright Chromium-Kontext zurück.

    Nutzt einen absoluten Pfad für das Profil, um Konflikte zu vermeiden.
    """
    # WHY: Absoluter Pfad ist sicherer gegen CWD-Wechsel.
    # 4 Ebenen hoch: browser/ -> genius/ -> beatbase/ -> src/
    base_dir = Path(__file__).resolve().parents[3]
    profile_dir = str(base_dir / PROFILE_DIR)

    # Wir reduzieren die Flags auf das Minimum, um Inkompatibilitäten zu vermeiden
    return playwright.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
        user_agent=USER_AGENT,
        args=["--disable-blink-features=AutomationControlled"],
    )
