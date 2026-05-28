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
  const [micActive, setMicActive] = useState(false);
  const [systemActive, setSystemActive] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [systemLevel, setSystemLevel] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamsRef = useRef<MediaStream[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserMicRef = useRef<AnalyserNode | null>(null);
  const analyserSysRef = useRef<AnalyserNode | null>(null);
  const meterRafRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (meterRafRef.current !== null) {
      cancelAnimationFrame(meterRafRef.current);
      meterRafRef.current = null;
    }
    streamsRef.current.forEach(stream => {
      stream.getTracks().forEach(track => track.stop());
    });
    streamsRef.current = [];
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserMicRef.current = null;
    analyserSysRef.current = null;
    setMicActive(false);
    setSystemActive(false);
    setMicLevel(0);
    setSystemLevel(0);
  }, []);

  const computeLevel = (analyser: AnalyserNode): number => {
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    return Math.min(1, Math.sqrt(sum / data.length) * 3);
  };

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
          video: {
            displaySurface: "monitor",
          } as MediaTrackConstraints,
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
          // @ts-expect-error - systemAudio is a Chrome-specific option
          systemAudio: "include",
          selfBrowserSurface: "include",
          surfaceSwitching: "exclude",
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
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      const dest = audioContext.createMediaStreamDestination();

      const micSrc = audioContext.createMediaStreamSource(micStream);
      const micAnalyser = audioContext.createAnalyser();
      micAnalyser.fftSize = 512;
      micSrc.connect(micAnalyser);
      micSrc.connect(dest);
      analyserMicRef.current = micAnalyser;
      setMicActive(true);

      if (systemStream) {
        const sysSrc = audioContext.createMediaStreamSource(systemStream);
        const sysGain = audioContext.createGain();
        sysGain.gain.value = 1.5;
        const sysAnalyser = audioContext.createAnalyser();
        sysAnalyser.fftSize = 512;
        sysSrc.connect(sysAnalyser);
        sysSrc.connect(sysGain);
        sysGain.connect(dest);
        analyserSysRef.current = sysAnalyser;
        setSystemActive(true);
      }

      const tickMeter = () => {
        if (analyserMicRef.current) setMicLevel(computeLevel(analyserMicRef.current));
        if (analyserSysRef.current) setSystemLevel(computeLevel(analyserSysRef.current));
        meterRafRef.current = requestAnimationFrame(tickMeter);
      };
      meterRafRef.current = requestAnimationFrame(tickMeter);

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
      <header className="hero">
        <h1>🎙️ AI 회의 녹음 & 정리</h1>
        <p>버튼 한 번으로 회의를 녹음하고 자동으로 회의록을 만들어 드려요</p>
      </header>

      <section className="card">
      <div className="info">
        <strong>📌 사용 방법:</strong>
        <ol>
          <li>&quot;회의 시작&quot; 클릭 → 마이크 권한 허용</li>
          <li>화면 공유 다이얼로그가 뜨면 <strong>&quot;전체 화면&quot;</strong>이 자동 선택됨 → <strong>&quot;공유&quot; 클릭</strong> (시스템 오디오 자동 포함)</li>
          <li>회의 종료 후 &quot;회의 종료&quot; 클릭</li>
        </ol>
        <small>※ 브라우저 보안 정책상 시스템 오디오 캡처에는 화면 공유 다이얼로그 1회 클릭이 필수입니다 (없앨 수 없음). Chrome/Edge 권장.</small>
      </div>

      <div className="notice">
        <strong>⚠️ 테스트 버전 안내</strong>
        <ul>
          <li>이 버전은 <strong>5분 미만의 회의만</strong> 처리 가능합니다 (서버 제약).</li>
          <li>가볍게 만들기 위해 <strong>최고 성능의 전사 도구는 사용하지 않았습니다.</strong> 전사 정확도가 다소 떨어질 수 있습니다.</li>
        </ul>
      </div>

      <div className="tools">
        <strong>사용된 기술 스택</strong>
        <ul>
          <li><strong>녹음:</strong> 브라우저 MediaRecorder API (WebM Opus 64kbps), Web Audio API (마이크 + 시스템 오디오 믹싱)</li>
          <li><strong>전사 + 회의록 생성:</strong> Google Gemini 2.5 Flash (음성 → 한국어 텍스트 → 구조화된 회의록을 한 번에 처리)</li>
          <li><strong>프론트엔드:</strong> Next.js 15 + React 19 + TypeScript</li>
          <li><strong>배포:</strong> Vercel (Serverless Functions, 60초 timeout)</li>
        </ul>
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
        <>
          <div className="status recording">
            🔴 녹음 중... <code>{formatDuration(elapsed)}</code>
          </div>
          <div className="meters">
            <div className="meter-row">
              <span className="meter-label">
                마이크 {micActive ? "✅" : "❌"}
              </span>
              <div className="meter-bar">
                <div className="meter-fill" style={{ width: `${micLevel * 100}%` }} />
              </div>
            </div>
            <div className="meter-row">
              <span className="meter-label">
                시스템 오디오 {systemActive ? "✅" : "❌"}
              </span>
              <div className="meter-bar">
                <div className="meter-fill" style={{ width: `${systemLevel * 100}%` }} />
              </div>
            </div>
            {!systemActive && (
              <div className="meter-warn">
                ⚠️ 시스템 오디오가 캡처되지 않았습니다. 다시 시작 시 화면 공유 다이얼로그에서 <strong>&quot;탭 오디오 공유&quot;</strong> 또는 <strong>&quot;시스템 오디오 공유&quot;</strong> 체크박스를 켜주세요.
              </div>
            )}
            {systemActive && systemLevel < 0.02 && elapsed > 2 && (
              <div className="meter-warn">
                ⚠️ 시스템 오디오 트랙은 연결되었지만 소리가 감지되지 않습니다. 공유한 탭에서 실제로 소리가 재생 중인지 확인해주세요.
              </div>
            )}
          </div>
        </>
      )}

      {processing && (
        <div className="status processing">
          ⏳ 처리 중... (Gemini가 전사 + 회의록 생성)
        </div>
      )}

      {error && <div className="error">{error}</div>}

      </section>

      {result && (
        <section className="result">
          <div className="success">✅ 회의록 생성 완료</div>

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
        </section>
      )}
    </main>
  );
}
