"""Importer: Liest Queue-JSONs und routet sie in die Datenbanken.

Der Importer ist der ``Posteingang`` des Processors. Er schaut in ``data/queue/``
nach fertigen Song-Summaries und reicht sie an:

- ``processor.songs_db.save_song_summary`` (lokale flache SQLite-DB)
- ``processor.external_db.update_audio_features`` (externe Beatbase-DB,
  nur wenn die Summary Audio-Features mitbringt)

Erfolgreich verarbeitete JSONs wandern in das Archiv ``data/json/``. Fehler bei
einer Datei stoppen den Lauf nicht ─ der naechste Aufruf greift sie wieder auf.
"""

import json

from beatbase.processor.external_db import update_audio_features
from beatbase.processor.songs_db import save_song_summary
from beatbase.shared.config import JSON_EXPORT_DIR, QUEUE_DIR
from beatbase.shared.utils.log import log_status


# DEF: process_queue() -> int
def process_queue() -> int:
    """Arbeitet alle JSONs in der Queue ab. Gibt die Anzahl verarbeiteter Files zurueck.

    Ein JSON gilt als erfolgreich verarbeitet, wenn ``save_song_summary`` ohne
    Fehler durchlaeuft. Audio-Features sind optional ─ ein Fehler beim
    ``update_audio_features`` wird geloggt, blockiert aber nicht die Archivierung.
    """
    if not QUEUE_DIR.exists():
        return 0

    JSON_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for json_file in sorted(QUEUE_DIR.glob("*.json")):
        try:
            summary = json.loads(json_file.read_text(encoding="utf-8"))
            track_id = json_file.stem

            save_song_summary(track_id, summary)

            features = summary.get("audio_features", {})
            if features and any(v is not None for v in features.values()):
                try:
                    update_audio_features(track_id, features)
                except Exception as e:
                    log_status(f"⚠️ Audio-Features-Update fehlgeschlagen ({track_id}): {e}")

            target = JSON_EXPORT_DIR / json_file.name
            if target.exists():
                target.unlink()
            json_file.rename(target)
            log_status(f"📥 Importiert: {json_file.name}")
            count += 1
        except Exception as e:
            log_status(f"❌ Importer-Fehler bei {json_file.name}: {e}")

    return count
