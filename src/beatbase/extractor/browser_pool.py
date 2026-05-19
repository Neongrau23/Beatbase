"""Persistente Browser-Pools fuer den parallelen Batch-Modus.

Pro Quelle laeuft ein dedizierter Worker-Thread, der seinen eigenen
``sync_playwright()``-Lifecycle haelt — Playwright hat Thread-Affinitaet,
daher braucht jeder Thread seine eigene Instanz. Die Worker konsumieren
Tasks aus einer ``queue.Queue`` und melden Ergebnisse ueber ``Future``s
zurueck an den Main-Thread.

Hauptklassen:

- ``ExtractorWorker``: Ein Thread, eine Quelle, ein offener Browser. Crash-
  Recovery baut den Browser intern neu, wenn Playwright eine Exception wirft.
- ``BrowserPool``: Dispatch-Layer. ``submit(source, track)`` legt einen Task
  beim passenden Worker ab und returned den Future. ``recycle()`` faehrt
  alle Worker neu, ``shutdown()`` schliesst sauber.
"""

import queue
import threading
import time
from concurrent.futures import Future
from typing import Optional

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from beatbase.extractor.orchestrator import EXTRACTORS, ExtractorSpec, _run_extractor
from beatbase.shared.config import BATCH_CRASH_MAX_RETRIES, BATCH_RETRY_DELAY_SECONDS
from beatbase.shared.utils.log import log_status

# SECTION: Sentinel — markiert "Worker bitte beenden"
_SHUTDOWN = object()


# DEF: Source-Name → passende create_browser_context-Funktion
def _create_context_for(source: str, p: Playwright, headless: bool) -> BrowserContext:
    """Oeffnet den persistenten Browser-Kontext der angegebenen Quelle.

    Importe sind lazy, damit Tests, die nur einzelne Quellen mocken, nicht
    alle Browser-Kontexte hochziehen muessen.
    """
    if source == "tunebat":
        from beatbase.extractor.tunebat.browser.context import create_browser_context

        return create_browser_context(p, headless=headless)
    if source == "songstats":
        from beatbase.extractor.songstats.browser.context import create_browser_context

        return create_browser_context(p, headless=headless)
    if source == "genius":
        from beatbase.extractor.genius.browser.context import create_playwright_context

        return create_playwright_context(p, headless=headless)
    if source == "songbpm":
        from beatbase.extractor.songbpm.browser.context import create_browser_context

        return create_browser_context(p, headless=headless)
    raise ValueError(f"Unknown source for browser context: {source!r}")


# DEF: Ein Worker = ein Thread mit eigenem Playwright + Browser fuer eine Quelle
class ExtractorWorker:
    """Worker-Thread, der genau eine Quelle haelt und nacheinander Tasks abarbeitet.

    Lebenszyklus:
    1. ``start()`` — Thread an, Playwright + Browser werden im Thread geoeffnet.
    2. Beliebig viele ``submit(track)`` — pro Aufruf ein Task in der Queue, ein
       Future zurueck. Reihenfolge bleibt FIFO innerhalb derselben Quelle.
    3. ``shutdown()`` — Sentinel in die Queue, Browser zu, Thread joinen.
    """

    def __init__(self, spec: ExtractorSpec, headless: bool):
        self.spec = spec
        self.headless = headless
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"pool-{spec.name}"
        )
        self._ready = threading.Event()

    def start(self) -> None:
        self._thread.start()

    def submit(self, track: dict) -> Future:
        """Legt einen Track in die Queue und returnt den zugehoerigen Future."""
        fut: Future = Future()
        self._queue.put((track, fut))
        return fut

    def shutdown(self, timeout: float = 30.0) -> None:
        """Sentinel rein, Thread joinen. Browser schliesst der Thread selbst."""
        self._queue.put((_SHUTDOWN, None))
        self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    # SECTION: Internals
    def _run(self) -> None:
        """Top-Level-Loop des Workers. Bei Browser-Crash bis zu N Mal neu
        hochziehen und erneut versuchen (siehe ``BATCH_CRASH_MAX_RETRIES``).
        """
        try:
            with sync_playwright() as p:
                context, page = self._open_browser(p)
                try:
                    while True:
                        item = self._queue.get()
                        track, fut = item
                        if track is _SHUTDOWN:
                            break
                        status, context, page = self._process_with_crash_retry(
                            p, track, context, page
                        )
                        fut.set_result(status)
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as e:
            log_status(f"❌ [{self.spec.name}] Worker konnte nicht starten: {e}")
            # WHY: noch wartende Tasks duerfen nicht ewig haengen — wir setzen
            # ihre Futures mit einem fail-Status, damit der Main-Thread weiterkommt.
            self._drain_remaining_with_fail(f"fail: {type(e).__name__}: {e}")

    def _process_with_crash_retry(
        self,
        p: Playwright,
        track: dict,
        context: BrowserContext,
        page: Page,
    ) -> tuple[str, BrowserContext, Page]:
        """Fuehrt _run_with_retry aus und retried bei Browser-Crash bis zu
        ``BATCH_CRASH_MAX_RETRIES`` Mal mit Browser-Neustart.

        Returns:
            (status, context, page) — die letzten beiden ggf. mit neuem Browser.
        """
        # Mindestens 1 Versuch, auch wenn BATCH_CRASH_MAX_RETRIES auf 0 steht.
        max_attempts = max(1, BATCH_CRASH_MAX_RETRIES)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                status = self._run_with_retry(track, page)
                return status, context, page
            except Exception as e:
                last_error = e
                log_status(
                    f"❌ [{self.spec.name}] Browser-Crash Versuch {attempt}/"
                    f"{max_attempts}: {e}"
                )
                # Browser jedes Mal frisch hochziehen — auch beim letzten Versuch,
                # damit der naechste Track in der Queue einen lebenden Browser sieht.
                context, page = self._reopen_browser(p, context)
        # Alle Versuche fehlgeschlagen — als 'fail:' melden.
        status = f"fail: BrowserCrash nach {max_attempts} Versuchen: {last_error}"
        return status, context, page

    def _open_browser(self, p: Playwright) -> tuple[BrowserContext, Page]:
        context = _create_context_for(self.spec.name, p, self.headless)
        # WHY: launch_persistent_context startet mit einer existierenden about:blank-Page.
        # new_page() ist sicherer (immer eine frische Tab), funktioniert auch fuer Mocks.
        page = context.new_page()
        return context, page

    def _reopen_browser(
        self, p: Playwright, old_context: BrowserContext
    ) -> tuple[BrowserContext, Page]:
        try:
            old_context.close()
        except Exception:
            pass
        return self._open_browser(p)

    def _run_with_retry(self, track: dict, page: Page) -> str:
        """Einmaliger Retry bei ``fail:`` analog zu parallel._run_extractor_with_retry."""
        status = _run_extractor(self.spec, track, page=page, headless=self.headless)
        if status.startswith("fail:"):
            log_status(
                f"♻️  [{self.spec.name}] retry in {BATCH_RETRY_DELAY_SECONDS:.0f}s nach: {status}"
            )
            time.sleep(BATCH_RETRY_DELAY_SECONDS)
            status = _run_extractor(self.spec, track, page=page, headless=self.headless)
        return status

    def _drain_remaining_with_fail(self, status: str) -> None:
        """Setzt die Futures aller noch in der Queue wartenden Tasks auf ``fail:``."""
        while True:
            try:
                track, fut = self._queue.get_nowait()
            except queue.Empty:
                return
            if track is _SHUTDOWN or fut is None:
                continue
            try:
                fut.set_result(status)
            except Exception:
                pass


# DEF: Pool, der einen Worker pro aktivierter Quelle hochzieht
class BrowserPool:
    """Dispatch-Layer ueber mehrere ``ExtractorWorker``.

    Erzeugt einen Worker pro Quelle, die in ``source_names`` enthalten ist
    (Default: alle aktivierten ``EXTRACTORS``). Der Pool weiss nicht, was im
    Bus passiert — er dispatcht nur Status-Futures pro Quelle.
    """

    def __init__(self, headless: bool, source_names: Optional[list[str]] = None):
        self.headless = headless
        if source_names is None:
            source_names = [s.name for s in EXTRACTORS if s.enabled]
        self.source_names = source_names
        self._workers: dict[str, ExtractorWorker] = {}

    def start(self) -> None:
        for spec in EXTRACTORS:
            if spec.name not in self.source_names or not spec.enabled:
                continue
            worker = ExtractorWorker(spec, self.headless)
            worker.start()
            self._workers[spec.name] = worker
        log_status(
            f"🏊 BrowserPool gestartet ({len(self._workers)} Worker: "
            f"{', '.join(self._workers.keys())})"
        )

    def has(self, source: str) -> bool:
        return source in self._workers

    def submit(self, source: str, track: dict) -> Future:
        if source not in self._workers:
            raise KeyError(f"No worker for source {source!r} — vergessen zu starten?")
        return self._workers[source].submit(track)

    def recycle(self) -> None:
        """Schliesst alle Worker und startet sie neu — Memory-Hygiene."""
        log_status(f"♻️  Pool recycle: {len(self._workers)} Worker neu hochziehen")
        names = list(self._workers.keys())
        for worker in self._workers.values():
            worker.shutdown()
        self._workers.clear()
        # Mit den gleichen Quellen neu starten
        previous_sources = self.source_names
        self.source_names = names
        try:
            self.start()
        finally:
            self.source_names = previous_sources

    def shutdown(self) -> None:
        for worker in self._workers.values():
            worker.shutdown()
        self._workers.clear()
