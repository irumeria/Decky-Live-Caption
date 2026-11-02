import asyncio
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass


@dataclass
class Status:
    running: bool = False
    phase: str = "stopped"
    error: str = ""
    source: str = ""
    translation: str = ""
    revision: int = 0
    cache_hits: int = 0
    ocr_ms: float = 0
    translation_ms: float = 0


class Pipeline:
    """One active translation plus one replaceable pending request. Never queue old dialogue."""

    def __init__(self, config, translator, clock=time.monotonic):
        self.config, self.translate, self.clock = config, translator, clock
        self.status = Status()
        self.cache = OrderedDict()
        self.candidate = ""
        self.changed_at = 0.0
        self.submitted_revision = -1
        self.pending = None
        self.wake = asyncio.Event()
        self.task = None

    async def start(self):
        if self.task is not None:
            raise RuntimeError("The pipeline is already running")
        self.status = Status(running=True, phase="starting")
        self.task = asyncio.create_task(self._translate_loop())

    def observe(self, text, ocr_ms=0):
        if not self.status.running:
            return
        text = text.strip()  # Preserve Japanese spacing, punctuation, and OCR line order.
        # Screen AI can alternate the final Japanese full stop between identical frames.
        # Keep an observed full stop without clearing a valid subtitle or restarting translation.
        if text and self.candidate and text.removesuffix("。") == self.candidate.removesuffix("。"):
            text = text if text.endswith("。") else self.candidate
            self.candidate = text
            if self.status.source:
                self.status.source = text
        now = self.clock()
        self.status.ocr_ms = ocr_ms
        if text != self.candidate:
            self.candidate = text
            self.changed_at = now
            self.status.revision += 1
            self.status.source = ""
            self.status.translation = ""
            self.pending = None
            self.status.phase = "settling" if text else "waiting"
        if not text:
            self.status.phase = "waiting"
            return
        if now - self.changed_at < self.config.stable_ms / 1000:
            return
        revision = self.status.revision
        if revision == self.submitted_revision:
            return
        self.submitted_revision = revision
        self.status.source = text
        if self.config.translator == "source":
            self.status.phase = "source-only"
            return
        key = (
            self.config.translator,
            self.config.source_language,
            self.config.target_language,
            self.config.hymt_model,
            text,
        )
        if key in self.cache:
            self.status.translation = self.cache[key]
            self.cache.move_to_end(key)
            self.status.cache_hits += 1
            self.status.phase = "ready"
            return
        self.pending = (revision, key, text)
        self.status.phase = "translating"
        self.wake.set()

    async def _translate_loop(self):
        while True:
            await self.wake.wait()
            self.wake.clear()
            if self.pending is None:
                continue
            revision, key, text = self.pending
            self.pending = None
            started = self.clock()
            try:
                result = await self.translate(text)
                if not isinstance(result, str) or not result.strip():
                    raise ValueError("The translation endpoint returned no text")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Network/model errors cross a process boundary. Stop and expose them; no fallback.
                self.fail(f"Translation failed: {error}")
                return
            self.cache[key] = result.strip()
            if len(self.cache) > 256:
                self.cache.popitem(last=False)
            if self.status.running and revision == self.status.revision:
                self.status.translation = result.strip()
                self.status.translation_ms = (self.clock() - started) * 1000
                self.status.phase = "ready"

    def fail(self, message):
        self.status.running = False
        self.status.phase = "error"
        self.status.error = message
        self.status.source = ""
        self.status.translation = ""
        self.pending = None

    async def stop(self):
        self.status.running = False
        self.status.source = ""
        self.status.translation = ""
        self.pending = None
        if self.status.phase != "error":
            self.status.phase = "stopped"
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass  # Explicit user stop/unload cancels the in-flight translation.
            self.task = None

    def snapshot(self):
        return asdict(self.status)
