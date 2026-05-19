# SECTION: HOTLINE - Der nackte Datenspeicher
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hotline:
    """
    ENTRY: Speichert alle Variablen des Prozesses in ihrer Rohform.
    Keine Logik, keine Strukturierung - nur Ablage.

    Thread-safe: der Batch-Modus fuellt den Bus aus mehreren Worker-Threads
    parallel. Ein RLock schuetzt jeden Zugriff. Im sequenziellen Watcher-Pfad
    ist der Overhead vernachlaessigbar.
    """

    storage: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def set(self, source: str, key: str, value: Any):
        """Legt einen Wert nackt im Speicher ab."""
        with self._lock:
            if source not in self.storage:
                self.storage[source] = {}
            self.storage[source][key] = value

    def get(
        self,
        source: str,
        key: str,
        default: Any = "kein anschluss unter dieser variable...",
    ) -> Any:
        """Holt einen spezifischen Rohwert. Standard-Fehlermeldung bei Fehlen."""
        with self._lock:
            source_data = self.storage.get(source, {})
            if key not in source_data:
                return default
            return source_data[key]

    def get_all(self) -> dict:
        """Gibt eine Kopie des gesamten Speichers fuer Builder-Funktionen aus.

        WHY: Kopie, damit der Aufrufer ohne Lock iterieren darf, ohne dass
        ein paralleler ``set`` waehrenddessen die Dict-Struktur veraendert.
        Nur die obere Schicht wird kopiert; Werte werden defensiv durchgereicht
        (Tests duerfen ``storage`` direkt mit malformed Daten manipulieren).
        """
        with self._lock:
            return {
                source: dict(data) if isinstance(data, dict) else data
                for source, data in self.storage.items()
            }

    def clear(self) -> None:
        """Leert den Speicher. Notwendig zwischen Songs im Watcher-Loop."""
        with self._lock:
            self.storage = {}


# BRIDGE: Die globale Instanz
bus = Hotline()
