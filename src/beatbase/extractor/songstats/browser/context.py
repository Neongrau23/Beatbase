from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright


# DEF: create_browser_context(p, headless) -> BrowserContext
def create_browser_context(p: Playwright, headless: bool = False) -> BrowserContext:
    """Erstellt einen persistenten Playwright-Kontext.

    Das Profil wird im Verzeichnis neben dieser Datei gespeichert,
    um Captchas zu vermeiden und Session-Cookies zu erhalten.
    Nicht löschen!
    """
    # 4 Ebenen hoch: browser/ -> songstats/ -> beatbase/ -> src/ -> <root>
    profile_dir = str(Path(__file__).resolve().parents[4] / ".profiles" / "songstats_profile")
    return p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
    )
