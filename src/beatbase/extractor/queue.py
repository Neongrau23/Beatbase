"""Schreibt fertige Song-Summaries als JSON in die Queue (data/queue/).

Die Queue ist die Naht zwischen den beiden Standorten:
- Der Extractor legt fertige JSONs hier ab.
- Der Processor (processor/importer.py) liest sie und schreibt sie in die DBs.

Dass das JSON in der Queue bereits die aggregierte Master-View ist, macht das
Debuggen einfach: Wer wissen will, was der Scraper geliefert hat, schaut hier rein.
"""

import json
from pathlib import Path

from beatbase.shared.config import QUEUE_DIR


def write_to_queue(track_id: str, summary: dict | str) -> Path:
    """Speichert eine Summary als ``{track_id}.json`` in der Queue.

    Args:
        track_id: Wird als Dateiname verwendet (Spotify-Track-ID).
        summary: Entweder bereits ein JSON-String oder ein dict, das serialisiert
            wird. Beide Formen sind erlaubt, weil der Orchestrator
            ``get_summary_json()`` aufruft und so einen String erhaelt.

    Returns:
        Pfad zur geschriebenen Datei.
    """
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{track_id}.json"
    if isinstance(summary, str):
        path.write_text(summary, encoding="utf-8")
    else:
        path.write_text(json.dumps(summary, indent=4, ensure_ascii=False), encoding="utf-8")
    return path
