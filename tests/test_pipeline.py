import asyncio

import pytest

from caption.config import Config
from caption.pipeline import Pipeline


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self):
        self.value += 0.6


def translating_config():
    return Config.parse({"translator": "hymt", "hymt_model": "test-model.gguf"})


async def tick():
    await asyncio.sleep(0)
    await asyncio.sleep(0)


@pytest.mark.parametrize(
    "text", ["明日は、誕生日。", "你好，世界。", "안녕하세요", "مرحبا", "Hello!"]
)
async def test_multilingual_text_is_preserved(text):
    clock = Clock()
    calls = []

    async def translate(value):
        calls.append(value)
        return "译文"

    pipeline = Pipeline(translating_config(), translate, clock)
    await pipeline.start()
    pipeline.observe(text)
    await tick()
    assert calls == []
    clock.advance()
    pipeline.observe(text)
    await tick()
    assert calls == [text]
    assert pipeline.snapshot()["translation"] == "译文"
    await pipeline.stop()


async def test_typing_and_blank_frames_clear_old_subtitles():
    clock = Clock()
    pipeline = Pipeline(Config(), None, clock)
    await pipeline.start()
    pipeline.observe("明")
    clock.advance()
    pipeline.observe("明日")
    assert pipeline.status.source == ""
    clock.advance()
    pipeline.observe("明日")
    assert pipeline.status.source == "明日"
    pipeline.observe("")
    assert pipeline.status.source == ""
    assert pipeline.status.phase == "waiting"
    await pipeline.stop()


async def test_source_mode_never_calls_translation():
    async def forbidden(_):
        raise AssertionError("Source mode sent dialogue to a translator")

    clock = Clock()
    pipeline = Pipeline(Config(), forbidden, clock)
    await pipeline.start()
    pipeline.observe("こんにちは")
    clock.advance()
    pipeline.observe("こんにちは")
    await tick()
    assert pipeline.status.phase == "source-only"
    await pipeline.stop()


async def test_latest_pending_replaces_old_and_stale_result_is_discarded():
    clock = Clock()
    first_release, last_release = asyncio.Event(), asyncio.Event()
    calls = []

    async def translate(text):
        calls.append(text)
        await (first_release if text == "A" else last_release).wait()
        return text + "译"

    pipeline = Pipeline(translating_config(), translate, clock)
    await pipeline.start()
    for text in ["A", "B", "C"]:
        pipeline.observe(text)
        clock.advance()
        pipeline.observe(text)
        await tick()
    assert calls == ["A"]
    first_release.set()
    await tick()
    assert calls == ["A", "C"]
    assert pipeline.status.translation == ""
    last_release.set()
    await tick()
    assert pipeline.status.translation == "C译"
    await pipeline.stop()


async def test_identical_dialogue_uses_cache():
    calls = []

    async def translate(text):
        calls.append(text)
        return "译文"

    clock = Clock()
    pipeline = Pipeline(translating_config(), translate, clock)
    await pipeline.start()
    for _ in range(2):
        pipeline.observe("")
        pipeline.observe("同じ台詞")
        clock.advance()
        pipeline.observe("同じ台詞")
        await tick()
    assert calls == ["同じ台詞"]
    assert pipeline.status.cache_hits == 1
    await pipeline.stop()


async def test_provider_failure_is_visible_and_stops_instead_of_falling_back():
    async def broken(_):
        raise ConnectionError("endpoint unavailable")

    clock = Clock()
    pipeline = Pipeline(translating_config(), broken, clock)
    await pipeline.start()
    pipeline.observe("台詞")
    clock.advance()
    pipeline.observe("台詞")
    await tick()
    assert not pipeline.status.running
    assert "endpoint unavailable" in pipeline.status.error
    assert pipeline.status.source == ""
    await pipeline.stop()


async def test_stop_cancels_translation():
    cancelled = asyncio.Event()

    async def slow(_):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    clock = Clock()
    pipeline = Pipeline(translating_config(), slow, clock)
    await pipeline.start()
    pipeline.observe("台詞")
    clock.advance()
    pipeline.observe("台詞")
    await tick()
    await pipeline.stop()
    assert cancelled.is_set()
    assert pipeline.status.phase == "stopped"
    assert pipeline.status.translation == ""


async def test_observed_japanese_full_stop_flicker_keeps_subtitle():
    clock = Clock()
    pipeline = Pipeline(Config(), None, clock)
    await pipeline.start()
    pipeline.observe("最後の夏")
    clock.advance()
    pipeline.observe("最後の夏。")
    assert pipeline.status.source == "最後の夏。"
    revision = pipeline.status.revision
    for text in ["最後の夏", "最後の夏。", "最後の夏"]:
        pipeline.observe(text)
        assert pipeline.status.source == "最後の夏。"
        assert pipeline.status.revision == revision
    pipeline.observe("最後の夏？")
    assert pipeline.status.source == ""
    assert pipeline.status.revision == revision + 1
    await pipeline.stop()
