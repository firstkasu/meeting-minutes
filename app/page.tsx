"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface MeetingResult {
  minutes: string;
  transcript: string;
  duration: number;
}

function formatDuration(seconds: number): string {
  const s = Math.floor(seconds);
  if (s >= 3600) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  }
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}분 ${sec}초`;
}

function renderMarkdown(md: string): string {
  const escape = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = md.split("\n");
  const html: string[] = [];
  let inList = false;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (line.startsWith("# ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h1>${escape(line.slice(2))}</h1>`);
    } else if (line.startsWith("## ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h2>${escape(line.slice(3))}</h2>`);
    } else if (line.startsWith("### ")) {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push(`<h3>${escape(line.slice(4))}</h3>`);
    } else if (line.startsWith("- ")) {
      if (!inList) { html.push("<ul>"); inList = true; }
      const content = escape(line.slice(2)).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
      html.push(`<li>${content}</li>`);
    } else if (line.trim() === "") {
      if (inList) { html.push("</ul>"); inList = false; }
      html.push("");
    } else {
      if (inList) { html.push("</ul>"); inList = false; }
      const content = escape(line).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
      html.push(`<p>${content}</p>`);
    }
  }
  if (inList) html.push("</ul>");
  return html.join("\n");
}

export default function Home() {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MeetingResult | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamsRef = useRef<MediaStream[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamsRef.current.forEach(stream => {
      stream.getTracks().forEach(track => track.stop());
    });
    streamsRef.current = [];
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  }, []);

  const startRecording = async () => {
    setError(null);
    setResult(null);
    chunksRef.current = [];

    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamsRef.current.push(micStream);

      let systemStream: MediaStream | null = null;
      try {
        const displayStream = await navigator.mediaDevices.getDisplayMedia({
          audio: true,
          video: true,
        });
        streamsRef.current.push(displayStream);
        const audioTracks = displayStream.getAudioTracks();
        if (audioTracks.length > 0) {
          systemStream = new MediaStream(audioTracks);
        }
      } catch {
        // 사용자가 화면 공유를 거부함 → 마이크만 녹음
      }

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;
      const dest = audioContext.createMediaStreamDestination();

      audioContext.createMediaStreamSource(micStream).connect(dest);
      if (systemStream) {
        audioContext.createMediaStreamSource(systemStream).connect(dest);
      }

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";

      const recorder = new MediaRecorder(
        dest.stream,
        mimeType ? { mimeType, audioBitsPerSecond: 64000 } : { audioBitsPerSecond: 64000 }
      );

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(1000);
      mediaRecorderRef.current = recorder;
      startTimeRef.current = Date.now();
      setRecording(true);
      setElapsed(0);

      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    } catch (err) {
      setError(`녹음 시작 실패: ${err instanceof Error ? err.message : String(err)}`);
      cleanup();
    }
  };

  const stopRecording = async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) return;

    setRecording(false);
    setProcessing(true);

    const duration = (Date.now() - startTimeRef.current) / 1000;

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      try { recorder.stop(); } catch { resolve(); }
    });

    cleanup();

    const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });

    if (audioBlob.size === 0) {
      setError("녹음된 오디오가 없습니다.");
      setProcessing(false);
      return;
    }

    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    formData.append("duration", duration.toString());

    try {
      const res = await fetch("/api/process", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setResult({
        minutes: data.minutes || "",
        transcript: data.transcript || "",
        duration,
      });
    } catch (err) {
      setError(`처리 실패: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setProcessing(false);
    }
  };

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  const downloadMarkdown = () => {
    if (!result) return;
    const content = `${result.minutes}\n\n## 전체 회의 시간\n- ${formatDuration(result.duration)}\n\n## 전체 녹음 내용 (상세)\n- ${result.transcript}\n`;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const now = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    a.href = url;
    a.download = `meeting_${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="container">
      <h1>🎙️ 회의 녹음 & 정리</h1>

      <div className="info">
        <strong>안내:</strong> &quot;회의 시작&quot;을 누르면 마이크 권한을 요청합니다. 화면 공유 다이얼로그에서 회의 탭(예: Zoom)을 선택하고 <strong>&quot;탭 오디오 공유&quot;</strong>를 체크하면 시스템 오디오도 함께 녹음됩니다. 거부하면 마이크만 녹음됩니다. (최대 5분 권장)
      </div>

      <div className="buttons">
        <button
          onClick={startRecording}
          disabled={recording || processing}
          className="btn btn-start"
        >
          🎙️ 회의 시작
        </button>
        <button
          onClick={stopRecording}
          disabled={!recording}
          className="btn btn-stop"
        >
          ⏹️ 회의 종료
        </button>
      </div>

      {recording && (
        <div className="status recording">
          🔴 녹음 중... <code>{formatDuration(elapsed)}</code>
        </div>
      )}

      {processing && (
        <div className="status processing">
          ⏳ 처리 중... (Gemini가 전사 + 회의록 생성)
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <div className="success">✅ 회의록 생성 완료!</div>

          <div
            className="minutes-content"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(result.minutes) }}
          />

          <h2>전체 회의 시간</h2>
          <p className="duration">{formatDuration(result.duration)}</p>

          <details className="transcript-details">
            <summary>전체 녹음 내용 (상세)</summary>
            <div className="transcript">{result.transcript || "(전사 내용 없음)"}</div>
          </details>

          <button onClick={downloadMarkdown} className="btn btn-download">
            📥 회의록 다운로드 (.md)
          </button>
        </div>
      )}
    </main>
  );
}
