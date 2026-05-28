"""Gemini API 재시도 로직 테스트.

- 지수 백오프 동작
- 최종 실패 시 RuntimeError + 전사 원본 보존 가능
- 중간 실패 후 성공
"""

from unittest.mock import MagicMock
import pytest

from llm_prompt import generate_minutes, MAX_RETRIES, BASE_DELAY


def _ok_response(text="# 회의록"):
    resp = MagicMock()
    resp.text = text
    return resp


def _make_factory(side_effects):
    """mock client factory: client.models.generate_content에 side_effect 주입."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = side_effects
    factory = lambda api_key: mock_client
    return factory, mock_client


class TestRetrySuccess:
    def test_first_try_success(self):
        factory, mock_client = _make_factory([_ok_response("# 성공")])
        clock = MagicMock()

        result = generate_minutes("전사 텍스트", "fake-key", _clock=clock, _client_factory=factory)

        assert result == "# 성공"
        assert mock_client.models.generate_content.call_count == 1
        clock.sleep.assert_not_called()

    def test_retry_then_success(self):
        factory, mock_client = _make_factory([
            Exception("서버 에러"),
            _ok_response("# 재시도 성공"),
        ])
        clock = MagicMock()

        result = generate_minutes("전사", "fake-key", _clock=clock, _client_factory=factory)

        assert result == "# 재시도 성공"
        assert mock_client.models.generate_content.call_count == 2
        clock.sleep.assert_called_once_with(BASE_DELAY)


class TestRetryFailure:
    def test_all_retries_exhausted(self):
        errors = [Exception(f"에러 {i}") for i in range(MAX_RETRIES)]
        factory, _ = _make_factory(errors)
        clock = MagicMock()

        with pytest.raises(RuntimeError, match="API 호출.*실패"):
            generate_minutes("전사", "fake-key", _clock=clock, _client_factory=factory)

    def test_transcript_preserved_on_failure(self):
        transcript = "이것은 보존되어야 할 전사 텍스트입니다"
        errors = [Exception("fail")] * MAX_RETRIES
        factory, _ = _make_factory(errors)
        clock = MagicMock()

        with pytest.raises(RuntimeError):
            generate_minutes(transcript, "fake-key", _clock=clock, _client_factory=factory)

        assert transcript == "이것은 보존되어야 할 전사 텍스트입니다"


class TestExponentialBackoff:
    def test_delays_are_exponential(self):
        errors = [Exception("fail")] * MAX_RETRIES
        factory, _ = _make_factory(errors)
        clock = MagicMock()

        with pytest.raises(RuntimeError):
            generate_minutes("전사", "fake-key", _clock=clock, _client_factory=factory)

        expected_delays = [BASE_DELAY * (2 ** i) for i in range(MAX_RETRIES - 1)]
        actual_delays = [c.args[0] for c in clock.sleep.call_args_list]
        assert actual_delays == expected_delays
