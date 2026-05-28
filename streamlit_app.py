"""회의 녹음·전사·회의록 생성 Streamlit 앱."""

import os
from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv

from utils import (
    start_recording,
    stop_recording,
    transcribe,
    format_duration,
    assemble_minutes,
)
from llm_prompt import generate_minutes

load_dotenv()

st.set_page_config(page_title="회의 녹음 & 정리", page_icon="🎙️", layout="centered")
st.title("회의 녹음 & 정리")

if "recording" not in st.session_state:
    st.session_state.recording = False
if "rec_state" not in st.session_state:
    st.session_state.rec_state = None
if "result" not in st.session_state:
    st.session_state.result = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "error" not in st.session_state:
    st.session_state.error = None

if st.session_state.recording:
    st_autorefresh(interval=1000, key="timer_refresh")

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "🎙️ 회의 시작",
        disabled=st.session_state.recording or st.session_state.processing,
        use_container_width=True,
    ):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.session_state.error = "GEMINI_API_KEY가 .env에 설정되지 않았습니다."
        else:
            st.session_state.error = None
            st.session_state.result = None
            try:
                st.session_state.rec_state = start_recording()
                st.session_state.recording = True
                st.rerun()
            except Exception as e:
                st.session_state.error = f"녹음 시작 실패: {e}"

with col2:
    if st.button(
        "⏹️ 회의 종료",
        disabled=not st.session_state.recording,
        use_container_width=True,
    ):
        st.session_state.recording = False
        st.session_state.processing = True
        st.rerun()

if st.session_state.error:
    st.error(st.session_state.error)

if st.session_state.recording and st.session_state.rec_state:
    elapsed = (datetime.now() - st.session_state.rec_state["start_time"]).total_seconds()
    st.markdown(f"### 🔴 녹음 중... `{format_duration(elapsed)}`")

    if st.session_state.rec_state["error_holder"]:
        st.session_state.recording = False
        st.session_state.error = f"녹음 오류: {st.session_state.rec_state['error_holder'][0]}"
        st.rerun()

if st.session_state.processing and st.session_state.rec_state:
    with st.spinner("녹음 저장 중..."):
        try:
            filepath, duration = stop_recording(st.session_state.rec_state)
        except Exception as e:
            st.session_state.error = f"녹음 저장 실패: {e}"
            st.session_state.processing = False
            st.session_state.rec_state = None
            st.rerun()

    with st.spinner("음성 전사 중... (시간이 걸릴 수 있습니다)"):
        try:
            transcript = transcribe(filepath)
        except Exception as e:
            st.session_state.error = f"전사 실패: {e}"
            st.session_state.processing = False
            st.session_state.rec_state = None
            st.rerun()

    txt_path = filepath.replace(".wav", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    api_key = os.getenv("GEMINI_API_KEY")
    with st.spinner("회의록 생성 중..."):
        try:
            body = generate_minutes(transcript, api_key)
        except RuntimeError as e:
            body = None
            st.session_state.error = f"회의록 생성 실패 (전사 원본은 보존됨: {txt_path}): {e}"

    if body:
        full_doc = assemble_minutes(body, duration, transcript)
        md_path = filepath.replace(".wav", ".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(full_doc)

        st.session_state.result = {
            "body": body,
            "duration": duration,
            "transcript": transcript,
            "wav_path": filepath,
            "md_path": md_path,
            "txt_path": txt_path,
        }

    st.session_state.processing = False
    st.session_state.rec_state = None
    st.rerun()

if st.session_state.result:
    r = st.session_state.result
    st.success("회의록 생성 완료!")
    st.markdown(r["body"])
    st.markdown(f"## 전체 회의 시간\n- {format_duration(r['duration'])}")

    with st.expander("전체 녹음 내용 (상세)"):
        st.text(r["transcript"])

    st.caption(f"📁 WAV: `{r['wav_path']}` | MD: `{r['md_path']}` | TXT: `{r['txt_path']}`")
