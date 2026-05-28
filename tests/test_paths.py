"""파일명·경로 생성 로직 테스트.

- meeting_YYYYMMDD_HHMMSS.wav 포맷
- recordings/ 폴더 기준
- 번들 모델 경로 해석 (PyInstaller _MEIPASS)
"""

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

from utils import generate_meeting_filename, get_model_path


class TestMeetingFilename:
    def test_format_pattern(self):
        dt = datetime(2025, 3, 15, 14, 30, 45)
        result = generate_meeting_filename(dt)
        assert result == "meeting_20250315_143045.wav"

    def test_midnight(self):
        dt = datetime(2025, 1, 1, 0, 0, 0)
        result = generate_meeting_filename(dt)
        assert result == "meeting_20250101_000000.wav"

    def test_returns_string(self):
        result = generate_meeting_filename(datetime.now())
        assert isinstance(result, str)
        assert result.startswith("meeting_")
        assert result.endswith(".wav")


class TestRecordingsPath:
    def test_full_path_includes_recordings_dir(self):
        dt = datetime(2025, 6, 1, 9, 0, 0)
        filename = generate_meeting_filename(dt)
        full_path = os.path.join("recordings", filename)
        assert full_path == os.path.join("recordings", "meeting_20250601_090000.wav")


class TestModelPath:
    def test_default_path_without_bundle(self):
        with patch.dict(os.environ, {}, clear=False):
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")
            path = get_model_path()
            assert "whisper-medium" in path

    def test_bundled_path_with_meipass(self):
        fake_base = "C:\\fake_bundle"
        with patch.object(sys, "_MEIPASS", fake_base, create=True):
            path = get_model_path()
            assert path.startswith(fake_base)
            assert "whisper-medium" in path
