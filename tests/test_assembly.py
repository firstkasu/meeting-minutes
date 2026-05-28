"""회의록 조립 로직 테스트.

- 본문 + "## 전체 회의 시간" + "## 전체 녹음 내용 (상세)" 결합
- 초 → HH:MM:SS / N분 N초 포맷 변환
"""

import pytest

from utils import format_duration, assemble_minutes


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(45) == "0분 45초"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2분 5초"

    def test_hours(self):
        assert format_duration(3661) == "01:01:01"

    def test_zero(self):
        assert format_duration(0) == "0분 0초"

    def test_exact_minute(self):
        assert format_duration(60) == "1분 0초"

    def test_exact_hour(self):
        assert format_duration(3600) == "01:00:00"


class TestAssembleMinutes:
    def test_contains_all_sections(self):
        body = "# 테스트 회의\n\n## 논의 내용\n- 항목1"
        transcript = "안녕하세요 회의를 시작하겠습니다"
        result = assemble_minutes(body, 125.0, transcript)

        assert "# 테스트 회의" in result
        assert "## 전체 회의 시간" in result
        assert "2분 5초" in result
        assert "## 전체 녹음 내용 (상세)" in result
        assert transcript in result

    def test_section_order(self):
        body = "# 회의 제목"
        transcript = "전사 내용"
        result = assemble_minutes(body, 60.0, transcript)

        idx_body = result.index("# 회의 제목")
        idx_time = result.index("## 전체 회의 시간")
        idx_transcript = result.index("## 전체 녹음 내용 (상세)")
        assert idx_body < idx_time < idx_transcript

    def test_preserves_body_content(self):
        body = "# 제목\n\n## 논의 내용\n- A\n- B\n\n## 액션 아이템\n- X"
        result = assemble_minutes(body, 30.0, "텍스트")
        assert "- A\n- B" in result
        assert "- X" in result

    def test_empty_transcript(self):
        result = assemble_minutes("# 제목", 10.0, "")
        assert "## 전체 녹음 내용 (상세)" in result
