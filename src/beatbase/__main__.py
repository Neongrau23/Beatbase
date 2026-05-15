"""SECTION: ENTRY
Beatbase-Orchestrator. Startet den zentralen Watcher-Loop oder beendet ihn.

Aufruf:
  python -m beatbase         # Startet den Watcher
  python -m beatbase --stop  # Beendet einen laufenden Watcher
"""

import argparse
import os
import signal
import sys
from pathlib import Path

from beatbase.core.watcher import run_watcher

PID_FILE = Path(".beatbase.pid")


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


def main():
    """ENTRY: Startet oder stoppt den Watcher."""
    parser = argparse.ArgumentParser(description="Beatbase Orchestrator")
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

    if PID_FILE.exists():
        print("⚠️ PID-Datei existiert bereits! Beatbase scheint schon zu laufen.")
        print("Tipp: Nutze 'python -m beatbase --stop', falls das ein Fehler ist.")
        sys.exit(1)

    # Schreibe PID-Datei
    try:
        PID_FILE.write_text(str(os.getpid()))
        print(f"🚀 Beatbase Orchestrator wird gestartet... (PID: {os.getpid()})")

        # Nur übergeben, wenn explizit True (CLI-Flag gesetzt)
        # Ansonsten wird der Default aus der Config in run_watcher() genutzt.
        watcher_kwargs = {}
        if args.headless:
            watcher_kwargs["headless"] = True

        run_watcher(**watcher_kwargs)
    except KeyboardInterrupt:
        print("\n🛑 Watcher durch Benutzer beendet.")
    finally:
        # Aufräumen
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
