export const maxDuration = 60;
export const dynamic = "force-dynamic";

const SYSTEM_PROMPT = `당신은 회의 녹음을 분석하는 전문가입니다.
주어진 음성을 한국어로 정확히 전사한 후, 구조화된 회의록을 작성합니다.

반드시 다음 JSON 형식으로만 응답하세요:
{
  "transcript": "전체 전사 텍스트 (음성을 그대로 한국어 텍스트로)",
  "minutes": "회의록 마크다운 (아래 구조를 정확히 따름)"
}

회의록 마크다운 구조 (정확히 이 형식):
# 대제목 (회의 주제 요약, 한 줄로 명확하게)

## 논의 내용
- bullet point로 주요 논의사항 정리
- 화자 구분이 가능하면 화자별로 구분

## 액션 아이템
- **담당자**: [이름] - [구체적인 액션] (기한: ~YYYY-MM-DD)

## 추후 계획
- 단기 계획
- 중장기 계획
- 다음 미팅 안건 제안

반드시 한국어로 작성하세요. 전사 텍스트에서 파악할 수 없는 정보는 추측하지 말고 "정보 없음"으로 표기하세요.`;

const MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"];
const BASE_URL = "https://generativelanguage.googleapis.com/v1beta";
const PER_MODEL_TIMEOUT_MS = 28000;

const isRetryable = (status: number) =>
  status === 429 || status === 500 || status === 503 || status === 504;

async function uploadToFileAPI(
  apiKey: string,
  buffer: Buffer,
  mimeType: string
): Promise<string> {
  const startRes = await fetch(
    `${BASE_URL}/files?key=${apiKey}`,
    {
      method: "POST",
      headers: {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": buffer.length.toString(),
        "X-Goog-Upload-Header-Content-Type": mimeType,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ file: { display_name: "meeting_audio" } }),
    }
  );

  if (!startRes.ok) {
    throw new Error(`File API start failed: ${startRes.status} ${await startRes.text()}`);
  }

  const uploadUrl = startRes.headers.get("X-Goog-Upload-URL");
  if (!uploadUrl) throw new Error("Upload URL not returned");

  const uploadRes = await fetch(uploadUrl, {
    method: "POST",
    headers: {
      "Content-Length": buffer.length.toString(),
      "X-Goog-Upload-Offset": "0",
      "X-Goog-Upload-Command": "upload, finalize",
    },
    body: new Uint8Array(buffer),
  });

  if (!uploadRes.ok) {
    throw new Error(`File upload failed: ${uploadRes.status} ${await uploadRes.text()}`);
  }

  const fileData = await uploadRes.json();
  return fileData.file.uri as string;
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const audioFile = formData.get("audio") as File | null;
    const durationStr = formData.get("duration") as string | null;
    const duration = durationStr ? parseFloat(durationStr) : 0;

    if (!audioFile) {
      return Response.json({ error: "오디오 파일이 없습니다." }, { status: 400 });
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return Response.json(
        { error: "GEMINI_API_KEY 환경변수가 설정되지 않았습니다." },
        { status: 500 }
      );
    }

    const buffer = Buffer.from(await audioFile.arrayBuffer());
    const mimeType = audioFile.type || "audio/webm";
    const sizeBytes = buffer.length;

    let audioPart: object;
    if (sizeBytes > 18 * 1024 * 1024) {
      const fileUri = await uploadToFileAPI(apiKey, buffer, mimeType);
      audioPart = { fileData: { mimeType, fileUri } };
    } else {
      audioPart = { inlineData: { mimeType, data: buffer.toString("base64") } };
    }

    const geminiBody = {
      systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: [
        {
          parts: [
            audioPart,
            { text: "이 회의 녹음을 전사하고 회의록을 작성해주세요." },
          ],
        },
      ],
      generationConfig: {
        responseMimeType: "application/json",
        temperature: 0.3,
      },
    };

    let geminiRes: Response | null = null;
    let lastError: { kind: string; detail: string; model: string } | null = null;

    for (const model of MODELS) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), PER_MODEL_TIMEOUT_MS);
      try {
        const res = await fetch(
          `${BASE_URL}/models/${model}:generateContent?key=${apiKey}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(geminiBody),
            signal: controller.signal,
          }
        );

        if (res.ok) {
          geminiRes = res;
          break;
        }

        const errText = await res.text();
        lastError = { kind: `HTTP_${res.status}`, detail: errText, model };
        console.error(`Gemini ${model} failed:`, res.status, errText.slice(0, 200));

        if (!isRetryable(res.status)) break;
      } catch (err) {
        const isAbort = err instanceof Error && err.name === "AbortError";
        lastError = {
          kind: isAbort ? "TIMEOUT" : "NETWORK",
          detail: err instanceof Error ? err.message : String(err),
          model,
        };
        console.error(`Gemini ${model} ${lastError.kind}:`, lastError.detail);
      } finally {
        clearTimeout(timer);
      }
    }

    if (!geminiRes) {
      return Response.json(
        {
          error: `Gemini API 호출 실패. 마지막 오류 [${lastError?.model} / ${lastError?.kind}]: ${lastError?.detail.slice(0, 300)}`,
        },
        { status: 503 }
      );
    }

    const geminiData = await geminiRes.json();
    const text = geminiData?.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!text) {
      return Response.json(
        { error: "Gemini에서 빈 응답을 받았습니다." },
        { status: 500 }
      );
    }

    let parsed: { minutes?: string; transcript?: string };
    try {
      parsed = JSON.parse(text);
    } catch {
      return Response.json(
        { error: "Gemini 응답 JSON 파싱 실패", raw: text.slice(0, 500) },
        { status: 500 }
      );
    }

    return Response.json({
      minutes: parsed.minutes || "",
      transcript: parsed.transcript || "",
      duration,
    });
  } catch (error) {
    console.error("Processing error:", error);
    return Response.json(
      { error: `처리 실패: ${error instanceof Error ? error.message : String(error)}` },
      { status: 500 }
    );
  }
}
