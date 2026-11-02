import math

import pytest

from caption.config import Config
from runtime.worker import capture_command, find_gamescope_node


def test_defaults_roundtrip():
    assert Config.parse(Config().to_dict()) == Config()


@pytest.mark.parametrize(
    "data",
    [
        {"fps": 0},
        {"fps": True},
        {"fps": 1.5},
        {"stable_ms": -1},
        {"roi_x": math.nan},
        {"roi_width": 2},
        {"roi_y": 0.95},
        {"subtitle_top": 0.7},
        {"subtitle_left": 0.5},
        {"subtitle_opacity": 1.1},
        {"subtitle_opacity": math.nan},
        {"subtitle_width": 0},
        {"translator": "cloud-fallback"},
        {"show_source": "yes"},
        {"source_language": ""},
        {"model_dir": None},
        {"unknown": 2},
    ],
)
def test_external_configuration_rejects_invalid_values(data):
    with pytest.raises((ValueError, TypeError)):
        Config.parse(data)


def test_subtitle_can_sit_beside_ocr_without_overlap():
    Config.parse(
        {
            "roi_x": 0.5,
            "roi_width": 0.5,
            "subtitle_left": 0,
            "subtitle_width": 0.4,
            "subtitle_top": 0.65,
        }
    )


def test_selects_gamescope_not_camera():
    objects = [
        {
            "type": "PipeWire:Interface:Node",
            "id": 10,
            "info": {"props": {"node.name": "camera", "media.class": "Video/Source"}},
        },
        {
            "type": "PipeWire:Interface:Node",
            "id": 42,
            "info": {"props": {"node.name": "gamescope", "media.class": "Video/Source"}},
        },
    ]
    assert find_gamescope_node(objects) == 42
    with pytest.raises(RuntimeError, match="No Gamescope"):
        find_gamescope_node(objects[:1])


def test_capture_uses_memory_not_screenshot_files():
    command = capture_command(42, 2)
    assert "path=42" in command
    assert "fdsink" in command
    assert "filesink" not in command
    assert "video/x-raw,framerate=2/1" in command
