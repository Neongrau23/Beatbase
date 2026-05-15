"""Stderr-Logging-Helper. Hält stdout frei für JSON-Ausgaben."""

import sys


# DEF: Stderr-Log
def log_status(message: str) -> None:
    """Schreibt eine Statusmeldung auf stderr.

    Hält stdout frei für strukturierte JSON-Ausgaben der CLI.
    """
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()
