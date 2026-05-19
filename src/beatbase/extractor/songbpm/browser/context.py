"""Playwright-Kontext fuer den SongBPM-Scraper.

Persistentes Profil unter ``.profiles/songbpm_profile``. Wird vom BrowserPool
und beim Standalone-Aufruf von ``search_on_songbpm(page=None, ...)`` genutzt,
sobald wir den Aufruf darueber umleiten.
"""

from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright


# DEF: create_browser_context(p, headless) -> BrowserContext
def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    """Erstellt einen persistenten Playwright-Kontext fuer SongBPM."""
    # 4 Ebenen hoch: browser/ -> songbpm/ -> beatbase/ -> src/ -> <root>
    profile_dir = str(Path(__file__).resolve().parents[4] / ".profiles" / "songbpm_profile")
    return p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
    )
