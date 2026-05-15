import os

from playwright.sync_api import BrowserContext, Playwright
from playwright_stealth import Stealth

from beatbase.tunebat.config import PROFILE_DIR, USER_AGENT


def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    profile_dir = os.path.join(base_dir, PROFILE_DIR)

    context = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
        user_agent=USER_AGENT,
        locale="de-DE",
        timezone_id="Europe/Berlin",
        viewport={"width": 1280, "height": 900},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    stealth = Stealth()
    context.on("page", lambda page: stealth.apply_stealth_sync(page))
    return context
