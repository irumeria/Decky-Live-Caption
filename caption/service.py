import asyncio
import json
import os
from pathlib import Path

from caption.config import Config
from caption.downloads import ModelInstaller
from caption.hymt import LocalHyMT
from caption.pipeline import Pipeline, Status
from caption.process import terminate_group


class Service:
    def __init__(self, root, settings_dir, runtime_dir, data_dir=None):
        self.root = Path(root)
        self.settings_dir = Path(settings_dir)
        self.runtime_dir = Path(runtime_dir)
        self.settings_file = self.settings_dir / "config.json"
        self.config = (
            Config.parse(json.loads(self.settings_file.read_text("utf-8")))
            if self.settings_file.exists()
            else Config()
        )
        self.pipeline = None
        self.worker = None
        self.reader = None
        self.lock = asyncio.Lock()
        self.local_model = None
        self.menu_open = False
        self.installer = ModelInstaller(data_dir if data_dir is not None else runtime_dir)

    def set_menu_open(self, opened):
        if type(opened) is not bool:
            raise ValueError("Menu state must be a boolean")
        self.menu_open = opened
        if opened and self.pipeline is not None:
            self.pipeline.observe("")
        return self.snapshot()

    def snapshot(self):
        from dataclasses import asdict

        status = self.pipeline.snapshot() if self.pipeline else asdict(Status())
        return {
            "config": self.config.to_dict(),
            "status": status,
            "download": self.installer.snapshot(),
        }

    async def configure(self, data):
        config = Config.parse(data)
        async with self.lock:
            await self._stop()
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            path = self.settings_file.with_suffix(".tmp")
            path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
            path.chmod(0o600)
            path.replace(self.settings_file)
            self.config = config
        return self.snapshot()

    async def start(self):
        async with self.lock:
            await self._stop()
            config = self.config
            # User-supplied paths can be stale after a model move or a deleted runtime.
            if not Path(config.python).is_file():
                raise ValueError("Create the isolated Python runtime and set its executable path")
            if not Path(config.model_dir, "libchromescreenai.so").is_file():
                raise ValueError("Select the existing Screen AI resources directory")
            self.local_model = LocalHyMT(config) if config.translator == "hymt" else None
            translate = self.local_model.translate if self.local_model else None
            self.pipeline = Pipeline(config, translate)
            await self.pipeline.start()
            env = os.environ.copy()
            # Decky may not inherit the graphical session environment. PipeWire uses this socket.
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            env["PYTHONUNBUFFERED"] = "1"
            try:
                if self.local_model is not None:
                    await self.local_model.start()
                self.worker = await asyncio.create_subprocess_exec(
                    config.python,
                    str(self.root / "runtime" / "worker.py"),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                    start_new_session=True,
                )
                self.worker.stdin.write((json.dumps(config.to_dict()) + "\n").encode())
                await self.worker.stdin.drain()
                self.worker.stdin.close()
                self.reader = asyncio.create_task(
                    self._read(self.worker, self.pipeline, self.local_model)
                )
            except Exception as error:
                self.pipeline.fail(f"Cannot start capture/translation: {error}")
                await self._stop()
                raise
        return self.snapshot()

    async def _read(self, worker, pipeline, local_model=None):
        try:
            while pipeline.status.running:
                # A native OCR hang or a disconnected capture must not leave old subtitles visible.
                line = await asyncio.wait_for(worker.stdout.readline(), 30)
                if not line:
                    code = await worker.wait()
                    raise RuntimeError(f"OCR worker exited ({code})")
                message = json.loads(line)
                if message["type"] == "error":
                    raise RuntimeError(message["message"])
                if message["type"] != "text":
                    raise ValueError("Unexpected OCR worker message")
                pipeline.observe("" if self.menu_open else message["text"], message["ocr_ms"])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            pipeline.fail(f"Capture/OCR stopped: {error}")
        finally:
            await terminate_group(worker)
            await pipeline.stop()
            if local_model is not None:
                await local_model.close()

    async def _stop(self):
        if self.reader is not None:
            self.reader.cancel()
            try:
                await self.reader
            except asyncio.CancelledError:
                pass
            self.reader = None
        elif self.worker is not None:
            await terminate_group(self.worker)
        self.worker = None
        if self.pipeline is not None:
            await self.pipeline.stop()
        if self.local_model is not None:
            await self.local_model.close()
            self.local_model = None

    async def stop(self):
        async with self.lock:
            await self._stop()
        return self.snapshot()
