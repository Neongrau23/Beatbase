from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright
from playwright_stealth import Stealth

from beatbase.extractor.tunebat.config import PROFILE_DIR, USE_STEALTH, USER_AGENT


def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    # parents[4] = src/, dann ../ via PROFILE_DIR aufs Repo-Root.
    # browser/ -> tunebat/ -> extractor/ -> beatbase/ -> src/
    base_dir = Path(__file__).resolve().parents[4]
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

    if USE_STEALTH:
        stealth = Stealth()
        context.on("page", lambda page: stealth.apply_stealth_sync(page))
    return context
