"""SECTION: ENTRY
Beatbase-Orchestrator. Startet den zentralen Watcher-Loop oder beendet ihn.

Aufruf:
  python -m beatbase                 # Watcher + Importer (default)
  python -m beatbase extract         # Nur Spotify-Watcher (schreibt in Queue)
  python -m beatbase process         # Nur Importer (Queue -> DBs)
  python -m beatbase --stop          # Beendet einen laufenden Watcher
  python -m beatbase --headless      # Watcher ohne sichtbares Browser-Fenster
"""

import argparse
import os
import signal
import sys

from beatbase.extractor.orchestrator import run_watcher
from beatbase.processor.importer import process_queue
from beatbase.shared.config import PID_FILE_PATH as PID_FILE
from beatbase.shared.utils.log import log_status


def stop_watcher():
    """Beendet den laufenden Watcher anhand der PID-Datei."""
    if not PID_FILE.exists():
        print("❌ Keine PID-Datei gefunden. Läuft Beatbase überhaupt?")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        print(f"🛑 Stoppe Beatbase (PID: {pid})...")
        os.kill(pid, signal.SIGTERM)
        print("✅ Prozess wurde beendet.")
    except ProcessLookupError:
        print("⚠️ Prozess existiert nicht mehr. Räume PID-Datei auf...")
    except ValueError:
        print("❌ PID-Datei ist korrupt.")
    except Exception as e:
        print(f"❌ Fehler beim Beenden: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


def _run_extract(headless: bool) -> None:
    """Startet den Watcher (mit PID-Singleton-Schutz)."""
    if PID_FILE.exists():
        print("⚠️ PID-Datei existiert bereits! Beatbase scheint schon zu laufen.")
        print("Tipp: Nutze 'python -m beatbase --stop', falls das ein Fehler ist.")
        sys.exit(1)

    try:
        PID_FILE.write_text(str(os.getpid()))
        print(f"🚀 Beatbase Orchestrator wird gestartet... (PID: {os.getpid()})")
        watcher_kwargs = {"headless": True} if headless else {}
        run_watcher(**watcher_kwargs)
    except KeyboardInterrupt:
        print("\n🛑 Watcher durch Benutzer beendet.")
    finally:
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except Exception:
                pass


def _run_process() -> None:
    """Arbeitet die Queue einmal ab und beendet sich."""
    count = process_queue()
    log_status(f"✅ Importer fertig: {count} Datei(en) verarbeitet.")


def main():
    """ENTRY: Routet zu extract / process / stop."""
    parser = argparse.ArgumentParser(
        description="Beatbase Orchestrator (Watcher + Importer)",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["extract", "process"],
        default=None,
        help=(
            "extract: nur Spotify-Watcher starten (schreibt in Queue). "
            "process: nur Importer (Queue -> DBs). "
            "Ohne Argument: Watcher + synchroner Importer (default)."
        ),
    )
    parser.add_argument(
        "--stop", action="store_true", help="Stoppt den laufenden Beatbase Watcher"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Startet den Watcher im Headless-Modus (ohne UI)",
    )
    args = parser.parse_args()

    if args.stop:
        stop_watcher()
        sys.exit(0)

    if args.mode == "process":
        _run_process()
        sys.exit(0)

    # extract oder default -> Watcher starten.
    # Im Default-Modus ruft der Orchestrator selbst process_queue() nach jedem Song.
    _run_extract(headless=args.headless)


if __name__ == "__main__":
    main()
