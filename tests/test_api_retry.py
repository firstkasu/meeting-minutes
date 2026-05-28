"""Anthropic API 재시도 로직 테스트.

- 지수 백오프 동작
- 최종 실패 시 RuntimeError + 전사 원본 보존 가능
- 중간 실패 후 성공
"""

from unittest.mock import MagicMock, patch, call
import pytest

from claude_prompt import generate_minutes, MAX_RETRIES, BASE_DELAY


def _make_mock_client(side_effects):
    """anthropic.Anthropic mock — messages.create에 side_effect 주입."""
    mock_client_cls = MagicMock()
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.messages.create.side_effect = side_effects
    return mock_client_cls, mock_client


def _ok_response(text="# 회의록"):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


class TestRetrySuccess:
    def test_first_try_success(self):
        mock_cls, mock_inst = _make_mock_client([_ok_response("# 성공")])
        clock = MagicMock()

        with patch("claude_prompt.anthropic.Anthropic", mock_cls):
            result = generate_minutes("전사 텍스트", "fake-key", _clock=clock)

        assert result == "# 성공"
        assert mock_inst.messages.create.call_count == 1
        clock.sleep.assert_not_called()

    def test_retry_then_success(self):
        mock_cls, mock_inst = _make_mock_client([
            Exception("서버 에러"),
            _ok_response("# 재시도 성공"),
        ])
        clock = MagicMock()

        with patch("claude_prompt.anthropic.Anthropic", mock_cls):
            result = generate_minutes("전사", "fake-key", _clock=clock)

        assert result == "# 재시도 성공"
        assert mock_inst.messages.create.call_count == 2
        clock.sleep.assert_called_once_with(BASE_DELAY)


class TestRetryFailure:
    def test_all_retries_exhausted(self):
        errors = [Exception(f"에러 {i}") for i in range(MAX_RETRIES)]
        mock_cls, _ = _make_mock_client(errors)
        clock = MagicMock()

        with patch("claude_prompt.anthropic.Anthropic", mock_cls):
            with pytest.raises(RuntimeError, match="API 호출.*실패"):
                generate_minutes("전사", "fake-key", _clock=clock)

    def test_transcript_preserved_on_failure(self):
        """API 실패해도 전사 원본은 호출자가 보존할 수 있어야 함."""
        transcript = "이것은 보존되어야 할 전사 텍스트입니다"
        errors = [Exception("fail")] * MAX_RETRIES
        mock_cls, _ = _make_mock_client(errors)
        clock = MagicMock()

        with patch("claude_prompt.anthropic.Anthropic", mock_cls):
            with pytest.raises(RuntimeError):
                generate_minutes(transcript, "fake-key", _clock=clock)

        assert transcript == "이것은 보존되어야 할 전사 텍스트입니다"


class TestExponentialBackoff:
    def test_delays_are_exponential(self):
        errors = [Exception("fail")] * MAX_RETRIES
        mock_cls, _ = _make_mock_client(errors)
        clock = MagicMock()

        with patch("claude_prompt.anthropic.Anthropic", mock_cls):
            with pytest.raises(RuntimeError):
                generate_minutes("전사", "fake-key", _clock=clock)

        expected_delays = [BASE_DELAY * (2 ** i) for i in range(MAX_RETRIES - 1)]
        actual_delays = [c.args[0] for c in clock.sleep.call_args_list]
        assert actual_delays == expected_delays
