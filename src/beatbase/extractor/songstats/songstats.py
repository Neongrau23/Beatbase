"""ENTRY: CLI-Einstiegspunkt für den Songstats-Scraper.

Alle Logik liegt in den Untermodulen. Diese Datei nur für den CLI-Aufruf.
"""

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

from beatbase.extractor.songstats.browser.context import create_browser_context
from beatbase.extractor.songstats.scraper.coordinator import run_songstats_extraction
from beatbase.shared.now_playing import read_now_playing_data
from beatbase.shared.utils.log import log_status


# DEF: Songstats-Suche (eigene Browser-Lifecycle)
def search_on_songstats(
    song: str,
    artists: list[str],
    headless: bool = False,
    page=None,
    direct_url: str | None = None,
    album: str | None = None,
) -> dict | None:
    """Öffnet eigenen Playwright-Kontext, scrapet einen Song und schließt wieder.

    Pendant zu `genius.search_on_genius()`. Für Aufrufer, die nicht selbst
    einen Browser-Kontext verwalten wollen (z. B. der zentrale Watcher).
    Liefert ``None`` bei Fehler oder leerem Ergebnis (konsistent mit den
    anderen ``search_on_*``-Funktionen).

    ``album`` wird vom Orchestrator pipeline-einheitlich durchgereicht, aber
    von Songstats derzeit nicht genutzt. Platzhalter fuer kuenftige
    Album-spezifische Suchstrategien.
    """
    if page:
        try:
            results = run_songstats_extraction(page, song, artists, direct_url=direct_url)
            if results:
                pretty = json.dumps(results, indent=4, ensure_ascii=False)
                log_status(f"📊 Songstats Daten: {pretty}")
                return results
            return None
        except Exception as e:
            log_status(f"❌ Songstats Fehler: {e}")
            return None

    with sync_playwright() as p:
        context = create_browser_context(p, headless=headless)
        new_page = context.pages[0] if context.pages else context.new_page()
        try:
            results = run_songstats_extraction(new_page, song, artists, direct_url=direct_url)
            if results:
                pretty = json.dumps(results, indent=4, ensure_ascii=False)
                log_status(f"📊 Songstats Daten: {pretty}")
                return results
            return None
        except Exception as e:
            log_status(f"❌ Songstats Fehler: {e}")
            return None
        finally:
            context.close()


def main():
    """ENTRY: Einstiegspunkt für das Skript.

    Gibt die rohen Songstats-Ergebnisse als JSON auf stdout aus. Die
    DB-Persistenz uebernimmt der Processor (``python -m beatbase process``),
    nicht mehr dieser Standalone-Aufruf.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--song", type=str)
    parser.add_argument("--artist", type=str, action="append", default=[])
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    song_name = args.song
    artists = args.artist
    if not song_name:
        # Fallback: Aktueller Song strukturiert aus dem IPC-Layer
        data = read_now_playing_data()
        song_name = data.get("song")
        artists = data.get("artists", [])

    if not song_name or song_name == "nothing...":
        log_status("❌ Kein Song angegeben.")
        sys.exit(1)

    with sync_playwright() as p:
        context = create_browser_context(p, headless=args.headless)
        page = context.pages[0] if context.pages else context.new_page()
        results = run_songstats_extraction(page, song_name, artists)

        context.close()

        if results:
            # WHY: JSON-Ausgabe auf stdout, damit Pipes (z.B. jq) funktionieren.
            print(json.dumps(results, indent=4, ensure_ascii=False))
        else:
            log_status("❌ Keine Details gefunden.")


if __name__ == "__main__":
    main()
