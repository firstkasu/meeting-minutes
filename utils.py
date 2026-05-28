"""녹음·믹싱·전사 유틸리티."""

import os
import sys
import threading
from datetime import datetime

import numpy as np
import soundcard as sc
import soundfile as sf
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


RECORD_SR = 48000
RECORD_BLOCKSIZE = 1024


def _record_stream(
    stop_event: threading.Event,
    mic_chunks: list,
    loopback_chunks: list,
    mic_sr_holder: list,
    loopback_sr_holder: list,
    error_holder: list,
):
    """별도 스레드에서 마이크 + 루프백 동시 녹음."""
    try:
        mic_device = sc.default_microphone()
        speaker = sc.default_speaker()
        # WASAPI loopback: 블루투스 장치에서는 loopback 캡처가 누락될 수 있음
        loopback_device = sc.get_microphone(speaker.id, include_loopback=True)

        mic_sr = RECORD_SR
        loopback_sr = RECORD_SR
        mic_sr_holder.append(mic_sr)
        loopback_sr_holder.append(loopback_sr)

        with mic_device.recorder(samplerate=mic_sr, blocksize=RECORD_BLOCKSIZE) as mic_rec, \
             loopback_device.recorder(samplerate=loopback_sr, blocksize=RECORD_BLOCKSIZE) as lb_rec:
            while not stop_event.is_set():
                mic_data = mic_rec.record(numframes=RECORD_BLOCKSIZE)
                lb_data = lb_rec.record(numframes=RECORD_BLOCKSIZE)
                mic_chunks.append(mic_data)
                loopback_chunks.append(lb_data)
    except Exception as e:
        error_holder.append(str(e))


def start_recording() -> dict:
    """녹음 시작. session_state에 저장할 상태 dict 반환."""
    stop_event = threading.Event()
    mic_chunks = []
    loopback_chunks = []
    mic_sr_holder = []
    loopback_sr_holder = []
    error_holder = []

    thread = threading.Thread(
        target=_record_stream,
        args=(stop_event, mic_chunks, loopback_chunks, mic_sr_holder, loopback_sr_holder, error_holder),
        daemon=True,
    )
    thread.start()

    return {
        "thread": thread,
        "stop_event": stop_event,
        "mic_chunks": mic_chunks,
        "loopback_chunks": loopback_chunks,
        "mic_sr_holder": mic_sr_holder,
        "loopback_sr_holder": loopback_sr_holder,
        "error_holder": error_holder,
        "start_time": datetime.now(),
    }


def stop_recording(state: dict, output_dir: str = "recordings") -> tuple[str, float]:
    """녹음 중지, WAV 저장. (파일경로, 녹음시간초) 반환."""
    state["stop_event"].set()
    state["thread"].join(timeout=5)

    if state["error_holder"]:
        raise RuntimeError(f"녹음 오류: {state['error_holder'][0]}")

    duration = (datetime.now() - state["start_time"]).total_seconds()
    mic_sr = state["mic_sr_holder"][0] if state["mic_sr_holder"] else RECORD_SR
    lb_sr = state["loopback_sr_holder"][0] if state["loopback_sr_holder"] else RECORD_SR

    mic_audio = np.concatenate(state["mic_chunks"]) if state["mic_chunks"] else np.zeros(0, dtype=np.float32)
    lb_audio = np.concatenate(state["loopback_chunks"]) if state["loopback_chunks"] else np.zeros(0, dtype=np.float32)

    mixed, out_sr = mix_audio(mic_audio, mic_sr, lb_audio, lb_sr)

    os.makedirs(output_dir, exist_ok=True)
    filename = generate_meeting_filename(state["start_time"])
    filepath = os.path.join(output_dir, filename)
    sf.write(filepath, mixed, out_sr)

    return filepath, duration


def transcribe(audio_path: str) -> str:
    """faster-whisper로 한국어 전사."""
    from faster_whisper import WhisperModel

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    model_dir = get_model_path()
    if os.path.isdir(model_dir):
        model = WhisperModel("medium", device=device, compute_type=compute_type, download_root=model_dir)
    else:
        model = WhisperModel("medium", device=device, compute_type=compute_type)

    segments, _ = model.transcribe(audio_path, language="ko")
    return " ".join(seg.text.strip() for seg in segments)
