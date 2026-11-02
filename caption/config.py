import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
    python: str = "/home/deck/homebrew/data/DeckyLiveCaption/venv/bin/python"
    model_dir: str = ""
    source_language: str = "Japanese"
    target_language: str = "Simplified Chinese"
    translator: str = "source"
    hymt_server: str = "/home/deck/homebrew/data/DeckyLiveCaption/runtime/llama-b10175/llama-server"
    hymt_model: str = (
        "/home/deck/homebrew/data/DeckyLiveCaption/models/hy-mt2-1.8b-q4/Hy-MT2-1.8B-Q4_K_M.gguf"
    )
    hymt_gpu_layers: int = 99
    hymt_threads: int = 2
    fps: int = 2
    stable_ms: int = 500
    min_confidence: float = 0.5
    roi_x: float = 0.05
    roi_y: float = 0.65
    roi_width: float = 0.9
    roi_height: float = 0.3
    font_size: int = 18
    subtitle_left: float = 0.05
    subtitle_width: float = 0.9
    subtitle_opacity: float = 0.68
    subtitle_top: float = 0.02
    subtitle_height: float = 0.22
    show_source: bool = True

    @classmethod
    def parse(cls, data):
        # Configuration comes from editable JSON and UI controls, not trusted internal state.
        config = cls(**data)
        for key in (
            "python",
            "model_dir",
            "source_language",
            "target_language",
            "translator",
            "hymt_server",
            "hymt_model",
        ):
            if not isinstance(getattr(config, key), str):
                raise ValueError(f"{key} must be text")
        limits = {
            "fps": (1, 4),
            "stable_ms": (250, 3000),
            "font_size": (14, 48),
            "min_confidence": (0, 1),
            "roi_x": (0, 1),
            "roi_y": (0, 1),
            "roi_width": (0.01, 1),
            "roi_height": (0.01, 1),
            "subtitle_top": (0, 0.85),
            "subtitle_height": (0.05, 0.4),
            "subtitle_left": (0, 0.95),
            "subtitle_width": (0.05, 1),
            "subtitle_opacity": (0, 1),
            "hymt_gpu_layers": (0, 99),
            "hymt_threads": (1, 8),
        }
        for key, (low, high) in limits.items():
            value = getattr(config, key)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{key} must be between {low} and {high}")
        for key in ("fps", "stable_ms", "font_size", "hymt_gpu_layers", "hymt_threads"):
            if type(getattr(config, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if type(config.show_source) is not bool:
            raise ValueError("show_source must be a boolean")
        if config.roi_x + config.roi_width > 1 or config.roi_y + config.roi_height > 1:
            raise ValueError("The OCR region must stay inside the screen")
        if (
            config.subtitle_top + config.subtitle_height > 1
            or config.subtitle_left + config.subtitle_width > 1
        ):
            raise ValueError("The subtitle box must stay inside the screen")
        # The composed PipeWire frame can contain our own subtitle. Reject overlap, not text.
        if (
            config.subtitle_top < config.roi_y + config.roi_height
            and config.subtitle_top + config.subtitle_height > config.roi_y
            and config.subtitle_left < config.roi_x + config.roi_width
            and config.subtitle_left + config.subtitle_width > config.roi_x
        ):
            raise ValueError("Move the subtitle box outside the OCR region")
        if not config.source_language.strip() or not config.target_language.strip():
            raise ValueError("Source and target languages must not be empty")
        if config.translator not in ("source", "hymt"):
            raise ValueError("Unknown translation backend")
        return config

    def to_dict(self):
        return asdict(self)
