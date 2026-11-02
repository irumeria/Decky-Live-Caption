import asyncio
import hashlib
import io
import tarfile
import threading

import pytest

from caption import downloads
from caption.downloads import DownloadCancelled, ModelInstaller


def response(monkeypatch, body):
    monkeypatch.setattr(downloads.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body))


def test_verified_download_and_existing_file_reuse(tmp_path, monkeypatch):
    response(monkeypatch, b"model")
    installer = ModelInstaller(tmp_path)
    path = tmp_path / "model.gguf"
    digest = hashlib.sha256(b"model").hexdigest()
    installer.fetch("https://example.invalid/model", path, digest, 5)
    assert path.read_bytes() == b"model"
    response(monkeypatch, b"must not download again")
    installer.fetch("https://example.invalid/model", path, digest, 5)
    assert installer.state["received"] == 5


@pytest.mark.parametrize("body, size", [(b"wrong", 5), (b"longer", 5), (b"tiny", 5)])
def test_invalid_download_never_installs(tmp_path, monkeypatch, body, size):
    response(monkeypatch, body)
    installer = ModelInstaller(tmp_path)
    with pytest.raises(ValueError):
        installer.fetch("https://example.invalid/model", tmp_path / "model", "0" * 64, size)
    assert list(tmp_path.iterdir()) == []


def test_existing_modified_model_is_not_overwritten(tmp_path):
    path = tmp_path / "model"
    path.write_bytes(b"user model")
    with pytest.raises(ValueError, match="Existing file"):
        ModelInstaller(tmp_path).fetch("https://example.invalid", path, "0" * 64, 10)
    assert path.read_bytes() == b"user model"


def test_cancel_removes_partial_download(tmp_path, monkeypatch):
    response(monkeypatch, b"model")
    installer = ModelInstaller(tmp_path)
    installer.cancelled.set()
    with pytest.raises(DownloadCancelled):
        installer.fetch("https://example.invalid", tmp_path / "model", "0" * 64, 5)
    assert list(tmp_path.iterdir()) == []


async def test_job_failure_surfaces_without_unhandled_task(tmp_path, monkeypatch):
    installer = ModelInstaller(tmp_path)

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(installer, "install", fail)
    installer.start()
    await installer.task
    assert installer.state["phase"] == "error"
    assert installer.state["error"] == "disk full"
    assert not installer.state["active"]


async def test_duplicate_job_rejected_and_close_joins_writer(tmp_path, monkeypatch):
    installer = ModelInstaller(tmp_path)
    entered = threading.Event()

    def wait_for_cancel():
        entered.set()
        installer.cancelled.wait(2)
        installer.check_cancelled()

    monkeypatch.setattr(installer, "install", wait_for_cancel)
    installer.start()
    while not entered.is_set():
        await asyncio.sleep(0.001)
    with pytest.raises(ValueError, match="already active"):
        installer.start()
    await installer.close()
    assert installer.task.done()
    assert installer.state["phase"] == "cancelled"


def test_runtime_archive_cannot_escape_staging(tmp_path, monkeypatch):
    installer = ModelInstaller(tmp_path)

    def fake_fetch(url, destination, digest, size):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".gguf":
            destination.write_bytes(b"model")
        else:
            with tarfile.open(destination, "w:gz") as archive:
                member = tarfile.TarInfo("../../outside")
                member.size = 4
                archive.addfile(member, io.BytesIO(b"evil"))

    monkeypatch.setattr(installer, "fetch", fake_fetch)
    with pytest.raises(tarfile.FilterError):
        installer.install()
    assert not (tmp_path / "runtime/llama-b10175-managed").exists()
    assert not (tmp_path / "outside").exists()
