import os

from playwright.sync_api import BrowserContext, Playwright


# DEF: create_browser_context(p, headless) -> BrowserContext
def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    """Erstellt einen persistenten Playwright-Kontext.

    Das Profil wird im Verzeichnis neben dieser Datei gespeichert,
    um Captchas zu vermeiden und Session-Cookies zu erhalten.
    Nicht löschen!
    """
    # Das Profil liegt im Root-Verzeichnis des Projekts
    profile_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".profiles", "songstats_profile")
    profile_dir = os.path.abspath(profile_dir)
    return p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
    )
