"""SECTION: ENTRY
Beatbase-Orchestrator. Startet den zentralen Watcher-Loop, beendet ihn
oder ruft den Batch-Modus auf.

Aufruf:
  python -m beatbase                                # Watcher + Importer (default)
  python -m beatbase extract                        # Nur Spotify-Watcher (schreibt in Queue)
  python -m beatbase process                        # Nur Importer (Queue -> DBs)
  python -m beatbase batch add <csv>                # Tracks in search_queue.db einlesen
  python -m beatbase batch run [--limit N]          # Pending-Tracks abarbeiten
  python -m beatbase batch retry [--source NAME]    # 'fail:'-Statuus zuruecksetzen + run
  python -m beatbase batch status                   # Zaehlung pro Quelle
  python -m beatbase --stop                         # Beendet einen laufenden Watcher
  python -m beatbase --headless                     # Watcher ohne sichtbares Browser-Fenster
"""

import argparse
import os
import signal
import sys
from pathlib import Path

from beatbase.extractor.orchestrator import run_watcher
from beatbase.extractor.search_queue import SOURCES as BATCH_SOURCES
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


# DEF: Routet batch add/run/retry/status
def _run_batch(args: argparse.Namespace) -> None:
    """Dispatcht den batch-Subcommand."""
    # WHY: Lokal importieren, damit der normale Watcher-Pfad nicht von
    # batch-Modul-Imports belastet wird.
    from beatbase.extractor import batch

    cmd = args.batch_cmd
    if cmd is None:
        log_status("❌ batch braucht einen Subbefehl: add | run | retry | status")
        sys.exit(2)

    if cmd == "add":
        if not args.batch_arg:
            log_status("❌ 'batch add' benoetigt einen CSV-Pfad als Argument.")
            sys.exit(2)
        path = Path(args.batch_arg)
        if not path.exists():
            log_status(f"❌ Datei nicht gefunden: {path}")
            sys.exit(1)
        batch.add_from_file(path)
        return

    if cmd == "run":
        batch.run(headless=args.headless, limit=args.limit)
        return

    if cmd == "retry":
        if args.source is not None and args.source not in BATCH_SOURCES:
            log_status(f"❌ Unbekannte --source: {args.source}")
            sys.exit(2)
        batch.retry(source=args.source, headless=args.headless)
        return

    if cmd == "status":
        batch.status()
        return


def main():
    """ENTRY: Routet zu extract / process / batch / stop."""
    parser = argparse.ArgumentParser(
        description="Beatbase Orchestrator (Watcher + Importer + Batch)",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["extract", "process", "batch"],
        default=None,
        help=(
            "extract: nur Spotify-Watcher starten (schreibt in Queue). "
            "process: nur Importer (Queue -> DBs). "
            "batch: Track-Liste verarbeiten (siehe batch_cmd). "
            "Ohne Argument: Watcher + synchroner Importer (default)."
        ),
    )
    parser.add_argument(
        "batch_cmd",
        nargs="?",
        choices=["add", "run", "retry", "status"],
        default=None,
        help="Nur fuer mode=batch: add | run | retry | status",
    )
    parser.add_argument(
        "batch_arg",
        nargs="?",
        default=None,
        help="Nur fuer 'batch add': Pfad zur CSV mit Tracks",
    )
    parser.add_argument(
        "--source",
        choices=BATCH_SOURCES,
        default=None,
        help="Nur fuer 'batch retry': einzelne Quelle auswaehlen",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nur fuer 'batch run': maximale Anzahl Tracks",
    )
    parser.add_argument(
        "--stop", action="store_true", help="Stoppt den laufenden Beatbase Watcher"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Startet den Watcher/Batch im Headless-Modus (ohne UI)",
    )
    args = parser.parse_args()

    if args.stop:
        stop_watcher()
        sys.exit(0)

    if args.mode == "process":
        _run_process()
        sys.exit(0)

    if args.mode == "batch":
        _run_batch(args)
        sys.exit(0)

    # extract oder default -> Watcher starten.
    # Im Default-Modus ruft der Orchestrator selbst process_queue() nach jedem Song.
    _run_extract(headless=args.headless)


if __name__ == "__main__":
    main()
