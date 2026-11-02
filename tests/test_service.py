import json

import pytest

from caption.config import Config
from caption.pipeline import Pipeline
from caption.service import Service


async def test_config_persists_without_runtime_or_secrets(tmp_path):
    service = Service(tmp_path, tmp_path / "settings", tmp_path / "runtime")
    data = Config().to_dict()
    data["source_language"] = "Japanese"
    await service.configure(data)
    new = Service(tmp_path, tmp_path / "settings", tmp_path / "runtime")
    assert new.config.to_dict() == data
    assert not new.snapshot()["status"]["running"]
    assert json.loads(service.settings_file.read_text("utf-8")) == data


async def test_missing_runtime_does_not_start_capture(tmp_path):
    service = Service(tmp_path, tmp_path, tmp_path)
    with pytest.raises(ValueError, match="Python runtime"):
        await service.start()
    assert service.worker is None


def test_corrupt_config_is_not_silently_reset(tmp_path):
    (tmp_path / "config.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        Service(tmp_path, tmp_path, tmp_path)


async def test_menu_open_clears_caption_without_stopping_session(tmp_path):
    service = Service(tmp_path, tmp_path, tmp_path)
    service.pipeline = Pipeline(Config(), None)
    await service.pipeline.start()
    service.pipeline.clock = lambda: 0
    service.pipeline.observe("dialogue")
    service.pipeline.clock = lambda: 1
    service.pipeline.observe("dialogue")
    assert service.pipeline.status.source == "dialogue"
    service.set_menu_open(True)
    assert service.pipeline.status.source == ""
    assert service.pipeline.status.translation == ""
    assert service.pipeline.status.running
    service.set_menu_open(False)
    assert service.menu_open is False
    await service.stop()


def test_invalid_menu_rpc_is_rejected(tmp_path):
    service = Service(tmp_path, tmp_path, tmp_path)
    with pytest.raises(ValueError, match="boolean"):
        service.set_menu_open("false")
