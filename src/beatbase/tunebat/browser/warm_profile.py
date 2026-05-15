import random
import time

from playwright.sync_api import sync_playwright

from beatbase.tunebat.browser.context import create_browser_context


def warm_profile():
    with sync_playwright() as p:
        context = create_browser_context(p, headless=False)
        page = context.new_page()

        for url in ["https://google.de", "https://youtube.com", "https://tunebat.com"]:
            print(f"🌐 {url}...")
            page.goto(url, wait_until="domcontentloaded")
            for _ in range(random.randint(2, 4)):
                page.mouse.wheel(0, random.randint(200, 500))
                time.sleep(random.uniform(0.8, 1.8))
            time.sleep(random.uniform(2, 3))

        input("✅ Fertig – ENTER zum Schließen")
        context.close()


if __name__ == "__main__":
    warm_profile()
