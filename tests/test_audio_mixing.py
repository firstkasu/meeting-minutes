"""오디오 믹싱 순수 로직 테스트.

mix_audio(mic, mic_sr, loopback, loopback_sr) → (mixed_np_array, sample_rate)
- 서로 다른 샘플레이트 → 공통 SR로 리샘플
- 서로 다른 채널 수 → 모노로 다운믹스
- 서로 다른 길이 → 짧은 쪽 zero-pad
"""

import numpy as np
import pytest

from utils import mix_audio


def _sine(freq: float, duration: float, sr: int, channels: int = 1) -> np.ndarray:
    """테스트용 사인파 생성."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    mono = (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)
    if channels == 1:
        return mono
    return np.column_stack([mono] * channels)


class TestMixAudioSameFormat:
    """동일 SR·채널·길이인 경우 단순 합산."""

    def test_same_mono(self):
        sr = 16000
        a = _sine(440, 1.0, sr, channels=1)
        b = _sine(880, 1.0, sr, channels=1)
        mixed, out_sr = mix_audio(a, sr, b, sr)

        assert out_sr == sr
        assert mixed.ndim == 1
        assert len(mixed) == len(a)
        np.testing.assert_allclose(mixed, a + b, atol=1e-5)

    def test_same_stereo_downmixed_to_mono(self):
        sr = 44100
        a = _sine(440, 0.5, sr, channels=2)
        b = _sine(880, 0.5, sr, channels=2)
        mixed, out_sr = mix_audio(a, sr, b, sr)

        assert mixed.ndim == 1, "출력은 항상 모노여야 함"


class TestMixAudioDifferentSampleRate:
    """SR이 다를 때 공통 SR로 리샘플."""

    def test_resample_to_higher_sr(self):
        a = _sine(440, 1.0, 16000, channels=1)
        b = _sine(440, 1.0, 44100, channels=1)
        mixed, out_sr = mix_audio(a, 16000, b, 44100)

        assert out_sr == 44100, "높은 SR 쪽으로 맞춰야 함"
        expected_len = int(44100 * 1.0)
        assert abs(len(mixed) - expected_len) <= 1

    def test_resample_preserves_energy(self):
        """리샘플 후 에너지가 크게 변하지 않는지 확인."""
        a = _sine(440, 1.0, 16000, channels=1)
        b = np.zeros(44100, dtype=np.float32)
        mixed, _ = mix_audio(a, 16000, b, 44100)

        energy_original = np.sum(a ** 2) / len(a)
        energy_mixed = np.sum(mixed ** 2) / len(mixed)
        assert abs(energy_original - energy_mixed) / energy_original < 0.05


class TestMixAudioDifferentChannels:
    """채널 수가 다를 때 모노로 다운믹스."""

    def test_mono_and_stereo(self):
        sr = 16000
        mono = _sine(440, 1.0, sr, channels=1)
        stereo = _sine(880, 1.0, sr, channels=2)
        mixed, out_sr = mix_audio(mono, sr, stereo, sr)

        assert mixed.ndim == 1
        assert out_sr == sr

    def test_stereo_downmix_is_channel_mean(self):
        """스테레오 다운믹스가 채널 평균인지 확인."""
        sr = 16000
        stereo = np.column_stack([
            np.ones(sr, dtype=np.float32) * 0.4,
            np.ones(sr, dtype=np.float32) * 0.6,
        ])
        silence = np.zeros(sr, dtype=np.float32)
        mixed, _ = mix_audio(silence, sr, stereo, sr)

        np.testing.assert_allclose(mixed, np.full(sr, 0.5, dtype=np.float32), atol=1e-5)


class TestMixAudioDifferentLength:
    """길이가 다를 때 긴 쪽에 맞춰 zero-pad."""

    def test_shorter_padded(self):
        sr = 16000
        short = _sine(440, 0.5, sr)
        long = _sine(880, 1.0, sr)
        mixed, _ = mix_audio(short, sr, long, sr)

        assert len(mixed) == len(long), "긴 쪽 길이에 맞춰야 함"

    def test_padded_tail_equals_longer_signal(self):
        """짧은 신호가 끝난 뒤 구간은 긴 신호만 남아야 함."""
        sr = 16000
        short = _sine(440, 0.5, sr)  # 8000 samples
        long = _sine(880, 1.0, sr)   # 16000 samples
        mixed, _ = mix_audio(short, sr, long, sr)

        tail = mixed[len(short):]
        np.testing.assert_allclose(tail, long[len(short):], atol=1e-5)


class TestMixAudioComplex:
    """SR·채널·길이 모두 다른 복합 케이스."""

    def test_all_different(self):
        mic = _sine(440, 0.8, 16000, channels=1)       # 16kHz 모노 0.8s
        loopback = _sine(880, 1.2, 48000, channels=2)   # 48kHz 스테레오 1.2s
        mixed, out_sr = mix_audio(mic, 16000, loopback, 48000)

        assert out_sr == 48000
        assert mixed.ndim == 1
        expected_len = int(48000 * 1.2)
        assert abs(len(mixed) - expected_len) <= 1

    def test_output_dtype_float32(self):
        a = _sine(440, 0.5, 16000)
        b = _sine(880, 0.5, 44100)
        mixed, _ = mix_audio(a, 16000, b, 44100)

        assert mixed.dtype == np.float32
