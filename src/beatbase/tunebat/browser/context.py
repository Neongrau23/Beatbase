from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright
from playwright_stealth import Stealth

from beatbase.tunebat.config import PROFILE_DIR, USER_AGENT


def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    # 4 Ebenen hoch: browser/ -> tunebat/ -> beatbase/ -> src/
    base_dir = Path(__file__).resolve().parents[3]
    profile_dir = str(base_dir / PROFILE_DIR)

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
