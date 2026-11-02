"""User-requested, checksum-pinned downloads. No inference requests leave the device."""

import asyncio
import hashlib
import os
import shutil
import ssl
import sys
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path

MODEL_NAME = "Hy-MT2-1.8B-Q4_K_M.gguf"
MODEL_URL = (
    "https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF/resolve/"
    "1cd5208700acedef4ef93019b6cfc148b8522d45/" + MODEL_NAME
)
MODEL_SHA256 = "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"
MODEL_SIZE = 1133080448
RUNTIME_NAME = "llama-b10175-bin-ubuntu-vulkan-x64.tar.gz"
RUNTIME_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b10175/" + RUNTIME_NAME
RUNTIME_SHA256 = "74906d104aed776d4e3b387cb4efd67e450530ed602df40676108018937f44ae"
RUNTIME_SIZE = 32413553


class DownloadCancelled(Exception):
    pass


class ModelInstaller:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.task = None
        self.cancelled = threading.Event()
        self.state = dict(
            phase="idle", active=False, file="", received=0, total=0, error="", paths={}
        )

    def snapshot(self):
        return dict(self.state)

    def update(self, **values):
        self.state = {**self.state, **values}

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise DownloadCancelled()

    def start(self):
        if self.task is not None and not self.task.done():
            raise ValueError("A model download is already active")
        self.cancelled.clear()
        self.update(
            phase="downloading", active=True, file="", received=0, total=0, error="", paths={}
        )
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            paths = await asyncio.to_thread(self.install)
            self.update(phase="ready", paths=paths)
        except DownloadCancelled:
            self.update(phase="cancelled")
        except Exception as error:
            # Network, disk, and checksum failures are user-visible. Never report partial installs.
            self.update(phase="error", error=str(error))
        finally:
            self.update(active=False)

    async def close(self):
        self.cancelled.set()
        if self.task is not None:
            await self.task  # Join the writer before plugin unload, rather than orphan its thread.

    def digest(self, path):
        sha = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                self.check_cancelled()
                sha.update(chunk)
        return sha.hexdigest()

    def fetch(self, url, destination, expected_hash, size):
        self.update(file=destination.name, received=0, total=size, phase="verifying")
        if destination.exists():
            if self.digest(destination) != expected_hash:
                raise ValueError(f"Existing file has a different checksum: {destination.name}")
            self.update(received=size)
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        # A failed transfer must not become an apparently installed model.
        with tempfile.TemporaryDirectory(prefix="download-", dir=destination.parent) as staging:
            temporary = Path(staging) / "payload"
            self.update(phase="downloading")
            request = urllib.request.Request(url, headers={"User-Agent": "DeckyLiveCaption/0.1"})
            # Decky's frozen Python can point OpenSSL at a nonexistent build-machine CA path.
            # SteamOS maintains this bundle independently of the embedded Python runtime.
            context = ssl.create_default_context(
                cafile="/etc/ssl/certs/ca-certificates.crt" if sys.platform == "linux" else None
            )
            with (
                urllib.request.urlopen(request, timeout=15, context=context) as response,
                temporary.open("wb") as out,
            ):
                sha = hashlib.sha256()
                received = 0
                while chunk := response.read(1024 * 1024):
                    self.check_cancelled()
                    received += len(chunk)
                    if received > size:
                        raise ValueError("Download exceeds the pinned file size")
                    out.write(chunk)
                    sha.update(chunk)
                    self.update(received=received)
            self.update(phase="verifying")
            if received != size or sha.hexdigest() != expected_hash:
                raise ValueError("Download size or SHA-256 does not match the pinned release")
            self.check_cancelled()
            temporary.replace(destination)

    def install(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # A GGUF, compressed archive, and extracted runtime coexist during installation.
        if shutil.disk_usage(self.data_dir).free < 1600 * 1024 * 1024:
            raise ValueError("Free at least 1.6 GiB before installing the model and runtime")
        model = self.data_dir / "models/hy-mt2-1.8b-q4" / MODEL_NAME
        archive = self.data_dir / "downloads" / RUNTIME_NAME
        runtime = self.data_dir / "runtime/llama-b10175-managed"
        marker = runtime / ".archive-sha256"
        if runtime.exists() and (
            not marker.is_file() or marker.read_text().strip() != RUNTIME_SHA256
        ):
            raise ValueError("Runtime directory already exists without a matching install marker")
        self.fetch(MODEL_URL, model, MODEL_SHA256, MODEL_SIZE)
        self.fetch(RUNTIME_URL, archive, RUNTIME_SHA256, RUNTIME_SIZE)
        self.check_cancelled()
        if not runtime.exists():
            self.update(phase="installing")
            runtime.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="extract-", dir=runtime.parent) as staging:
                with tarfile.open(archive) as bundle:
                    # Reject paths, symlinks, and devices that can escape the extraction directory.
                    bundle.extractall(staging, filter="data")
                extracted = Path(staging) / "llama-b10175"
                server = extracted / "llama-server"
                if not server.is_file():
                    raise ValueError("Runtime archive has no llama-server")
                server.chmod(server.stat().st_mode | 0o100)
                (extracted / ".archive-sha256").write_text(RUNTIME_SHA256 + "\n")
                self.check_cancelled()
                extracted.rename(runtime)
        if not os.access(runtime / "llama-server", os.X_OK):
            raise ValueError("Installed llama-server is missing or not executable")
        return {"hymt_model": str(model), "hymt_server": str(runtime / "llama-server")}
