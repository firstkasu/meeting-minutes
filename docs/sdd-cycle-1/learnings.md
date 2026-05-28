# 5. Build · learnings.md

빌드 도중 실제로 부딪힌 함정과 해결책 모음. 다음 사이클에서 시간을 줄여줄 것들.

## 환경 / 도구

- **Windows Store Python stub은 실제 Python이 아님** — `python.exe`가 있어 보여도 실행하면 exit code 49로 죽음. `uv venv --python 3.11`로 깔끔하게 격리.
- **PowerShell heredoc 인용 처리**가 까다로워서 git commit 메시지를 직접 PowerShell 안에 쓰면 깨짐. `Bash` 도구로 `git commit -F-` + heredoc이 가장 안정적.

## 오디오 / WASAPI

- **별도 스레드에서 WASAPI를 호출하면 `Error 0x800401f0`** (CO_E_NOTINITIALIZED). 스레드 진입 직후 `comtypes.CoInitializeEx(COINIT_MULTITHREADED)`를 호출해야 함. Streamlit은 매 입력마다 rerun + 녹음을 별도 스레드에 두므로 거의 확정적으로 만남.
- **`soundcard`의 `data discontinuity` 경고**는 작은 blocksize에서 일상적으로 뜬다. 무시해도 됨.
- **블루투스 헤드셋은 loopback 캡처가 누락**될 가능성이 크다. 안내 외엔 대응 방법이 없음.

## 브라우저 보안 (시스템 오디오 캡처)

- **다이얼로그는 절대 우회 불가.** Chrome/Edge/Firefox/Safari 전부 사용자 클릭을 강제. `displaySurface: "monitor"` + `systemAudio: "include"`로 **기본값만** 바꿀 수 있다 (다이얼로그는 그대로 뜸).
- **세 가지 상태를 구분해야 한다**:
  - `ok` — 공유 + 오디오 토글 ON
  - `cancelled` — 다이얼로그 닫음
  - `no_audio` — 공유는 했지만 오디오 토글 OFF (audio track이 0개로 돌아옴)
  세 케이스에 같은 메시지를 띄우면 사용자가 헷갈린다. 특히 `no_audio` 케이스를 안 잡으면 "취소하셨다"고 잘못 안내함.
- **레벨 미터 경고는 디바운스 필수.** RAF로 매 프레임 평가하면 짧은 침묵에도 깜빡거림. **2초 연속** 무음일 때만 경고를 띄우는 디바운스 패턴이 깔끔.

## LLM (Gemini)

- **`google.generativeai`는 deprecated.** 새 SDK는 `google-genai` (Python) / `@google/genai` (Node). Pytest의 `FutureWarning`으로 알게 됨.
- **`gemini-2.5-flash`가 자주 503 UNAVAILABLE을 반환.** 단순 재시도만으로는 부족하고, **모델 fallback**(`2.5-flash → 2.0-flash → flash-latest`)이 필요.
- **JSON 응답 강제**: `generationConfig.responseMimeType: "application/json"`. 안 쓰면 ` ```json `를 둘러 쓰는 경우가 있어 파싱 깨짐.
- **Gemini가 무음/짧은 오디오를 받으면** "회의록을 작성할 수 없습니다"는 본문을 돌려준다. 빈 전사 처리를 클라이언트가 별도로 안내해야 사용자 혼란이 없음.

## Vercel / Serverless

- **Hobby 플랜 함수 timeout 10초**. 오디오 + Gemini 호출에 절대 부족. **Pro 60초 권장**이지만 그래도 5분 회의는 위험 → **1분 미만**으로 안내.
- **함수가 timeout/크래시되면 JSON이 아니라 HTML 에러 페이지를 반환**. 클라이언트가 `res.json()`을 그대로 호출하면 `Unexpected token 'A'` 에러. **응답을 텍스트로 먼저 받아 try/parse 후 status별 한국어 메시지**로 변환하는 게 정답.
- **`maxDuration`은 route 파일에서 export**로 설정. `vercel.json`에도 명시하면 더 안전.
- **모델별 AbortController timeout**을 28초로 두면 3개 모델을 시도해도 60초 안에 들어옴. 한 모델이 멈춰도 다음 모델로 즉시 fallback.

## 네트워크 (지역 의존)

- **한국 → Google API 업로드가 매우 느림** (~1KB/s 관측). 로컬 테스트에서 500KB 업로드에 8분 걸린 사례. **Vercel(GCP 인접 망)에서는 수십 ms~수초**로 정상화. 로컬에서 느리다고 코드를 의심하지 말 것.

## TypeScript / Next.js

- **`fetch(..., { body: Buffer })`는 TS 타입 에러.** `body: new Uint8Array(buffer)`로 감싸야 함.
- **`@ts-expect-error`로 `systemAudio: "include"`** (Chrome 전용 옵션) 통과.
- **빌드가 `tsconfig.json`을 자동 수정**(`.next/types/**/*.ts` 추가). 신경 안 써도 됨.

## UX / 디자인

- **한국어 가독성은 Pretendard가 압도적.** CDN 한 줄로 끝.
- **그라데이션 텍스트 + 흰 배경**이 보라/인디고 그라데이션 배경보다 깔끔. 결국 흰색으로 회귀.
- **버튼 호버 시 `translateY(-1px)` + 그림자 강화**가 모던 웹에서 표준.
- **녹음 중 펄스 애니메이션**(`@keyframes`)이 "지금 동작 중"을 직관적으로 알림.

## 메타 (개발 프로세스)

- **요구사항이 중간에 LLM 제공자 교체로 바뀜.** 처음부터 LLM 호출을 모듈로 분리해 둔 덕분에 갈아끼우는 작업이 1파일 교체 + import 수정으로 끝남. 추상화 비용을 일찍 지불한 보람.
- **로컬판이 거의 완성된 시점에 "Vercel에 올려야 함" 요구가 들어옴.** 로컬판을 버리지 않고 **같은 저장소에 웹판을 공존**시킴(같은 `.env` 키, 같은 LLM, 다른 진입점). Vercel은 `package.json`을 보고 Next.js 빌드, Python 파일은 무시.
- **TDD 31개 테스트**가 LLM 교체(Anthropic → Gemini) 때 안전망 역할. 테스트만 통과하면 회의록 조립·재시도 로직이 깨지지 않았다는 확신.
- **버그 보고에서 "취소한 적 없는데 취소했다고 뜬다"** 같은 사용자의 반박이 진짜 버그를 드러냄. 내부 상태 변수를 더 세분화해야 한다는 신호로 받아들이기.
