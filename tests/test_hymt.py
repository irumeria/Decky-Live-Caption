import pytest

from caption.config import Config
from caption.hymt import LocalHyMT, translation_payload, translation_result


def test_hymt_config_and_private_prompt():
    config = Config.parse({"translator": "hymt", "hymt_gpu_layers": 0})
    payload = translation_payload(config, "明日は誕生日。")
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"].endswith("明日は誕生日。")
    assert payload["stream"] is False
    assert payload["max_tokens"] == 512


@pytest.mark.parametrize(
    "field,value", [("hymt_threads", 0), ("hymt_gpu_layers", -1), ("hymt_threads", 2.5)]
)
def test_invalid_user_hymt_limits(field, value):
    with pytest.raises(ValueError):
        Config.parse({field: value})


def test_hymt_result_rejects_truncation():
    with pytest.raises(RuntimeError, match="did not finish"):
        translation_result(
            {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
        )
    assert (
        translation_result(
            {"choices": [{"finish_reason": "stop", "message": {"content": " 明天是生日。 "}}]}
        )
        == "明天是生日。"
    )


async def test_missing_local_model_fails_before_spawning(tmp_path):
    config = Config.parse({"hymt_server": str(tmp_path / "missing")})
    model = LocalHyMT(config)
    with pytest.raises(FileNotFoundError):
        await model.start()
    assert model.process is None
    await model.close()
