"""녹음·믹싱·전사 유틸리티."""

import os
import sys
from datetime import datetime

import numpy as np
from scipy import signal as scipy_signal

MODEL_DIR_NAME = "whisper-medium"


def format_duration(seconds: float) -> str:
    total = int(seconds)
    if total >= 3600:
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    m, s = divmod(total, 60)
    return f"{m}분 {s}초"


def assemble_minutes(body: str, duration_seconds: float, transcript: str) -> str:
    duration_str = format_duration(duration_seconds)
    return (
        f"{body}\n\n"
        f"## 전체 회의 시간\n- {duration_str}\n\n"
        f"## 전체 녹음 내용 (상세)\n- {transcript}\n"
    )


def generate_meeting_filename(dt: datetime) -> str:
    return dt.strftime("meeting_%Y%m%d_%H%M%S.wav")


def get_model_path() -> str:
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, MODEL_DIR_NAME)


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """다채널 오디오를 모노로 다운믹스 (채널 평균)."""
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1).astype(np.float32)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """scipy를 사용해 리샘플."""
    if orig_sr == target_sr:
        return audio
    num_samples = int(len(audio) * target_sr / orig_sr)
    resampled = scipy_signal.resample(audio, num_samples)
    return resampled.astype(np.float32)


def mix_audio(
    mic: np.ndarray,
    mic_sr: int,
    loopback: np.ndarray,
    loopback_sr: int,
) -> tuple[np.ndarray, int]:
    """마이크와 루프백 오디오를 믹싱.

    Returns:
        (mixed, sample_rate) — 모노 float32 배열과 출력 샘플레이트
    """
    target_sr = max(mic_sr, loopback_sr)

    mic_mono = _to_mono(mic)
    loopback_mono = _to_mono(loopback)

    mic_resampled = _resample(mic_mono, mic_sr, target_sr)
    loopback_resampled = _resample(loopback_mono, loopback_sr, target_sr)

    max_len = max(len(mic_resampled), len(loopback_resampled))
    if len(mic_resampled) < max_len:
        mic_resampled = np.pad(mic_resampled, (0, max_len - len(mic_resampled)))
    if len(loopback_resampled) < max_len:
        loopback_resampled = np.pad(loopback_resampled, (0, max_len - len(loopback_resampled)))

    mixed = (mic_resampled + loopback_resampled).astype(np.float32)
    return mixed, target_sr
