# 2. Specify · spec.md

## 1. 범위와 제약

| 항목 | 값 |
|---|---|
| 사용 목적 | 테스트용 |
| 대상 환경 | Windows 11 (로컬판), 최신 Chrome/Edge (웹판) |
| 회의 최대 시간 | 로컬판 5분 미만, 웹판 1분 미만 (Vercel timeout 제약) |
| 언어 | UI·전사·회의록 모두 한국어 |

## 2. 시스템 두 가지

### 2.1 로컬판 (Streamlit, Python)
- 마이크 + WASAPI loopback으로 시스템 오디오 직접 캡처
- `faster-whisper medium` 한국어 전사 (오프라인 가능, 모델 동봉)
- Gemini API로 회의록 생성
- PyInstaller `--onedir` 패키징 (Python 미설치 환경 실행)

### 2.2 웹판 (Next.js, Vercel)
- 브라우저 `MediaRecorder` + Web Audio API로 마이크 + 시스템 오디오(getDisplayMedia) 믹싱
- Gemini API에 오디오를 **직접** 보내 전사 + 회의록을 **한 번에** 생성 (faster-whisper 안 씀)
- Vercel Serverless Function으로 배포

## 3. 동작 요구사항

### 3.1 회의 시작 (공통)
- 마이크 + 시스템 오디오 동시 녹음
- 로컬판: `recordings/meeting_YYYYMMDD_HHMMSS.wav` 저장
- "녹음 중..." 상태 + 실시간 경과 시간 표시 (1초 갱신)
- 웹판: 마이크/시스템 오디오 각각 실시간 레벨 미터 표시

### 3.2 회의 종료 (공통)
- 녹음 중지
- 전사 텍스트는 회의록 생성 **이전에** 무조건 로컬 저장 (`.txt`)
- LLM API 호출 → 구조화된 회의록 생성
- LLM 실패 시에도 전사 원본·녹음 WAV 보존 + 명확한 에러 메시지

### 3.3 회의록 출력 형식 (LLM 응답)
```markdown
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
```

### 3.4 저장 파일 추가 섹션
회의록 본문 아래에 다음 섹션을 합쳐 저장:
```markdown
## 전체 회의 시간
- HH:MM:SS (또는 N분 N초)

## 전체 녹음 내용 (상세)
- (전사 전문 그대로)
```

### 3.5 화면 표시
- 회의록 본문 + "전체 회의 시간" 즉시 표시
- "전체 녹음 내용 (상세)"는 접힘 영역(`st.expander` / `<details>`)

## 4. 아키텍처 결정

| 결정 | 사유 |
|---|---|
| 로컬판: Streamlit 단일 구조, MCP 미사용 | 의존성 최소, 데모 용이 |
| 로컬판: 녹음은 별도 스레드 (`threading.Event`로 중지) | Streamlit이 매 입력마다 rerun → UI 블로킹 방지 |
| 웹판: Next.js App Router | Vercel 1급 지원, React 19 안정성 |
| LLM 호출 모듈 분리 (`llm_prompt.py` / `app/api/process/route.ts`) | 모델·제공자 교체 용이 |
| 모델명 상수 분리 (`MODEL = "gemini-2.5-flash"`) | 한 곳에서 변경 |
| Gemini 모델 fallback (`2.5-flash → 2.0-flash → flash-latest`) | 503 UNAVAILABLE 대응 |
| 웹판: 오디오는 WebM Opus 64kbps | Vercel 4.5MB body 제한 안에서 5분 가능 |

## 5. 데이터 보호 / 실패 처리

- 전사 원본 `.txt`는 LLM 호출 **이전에** 디스크 저장
- LLM 호출 실패 시 지수 백오프 재시도 (1s, 3s)
- 모든 재시도·모델 fallback 실패해도 녹음 WAV + 전사 `.txt`는 남음
- 웹판: 응답이 JSON이 아니면(Vercel timeout 시 HTML 에러 페이지) 텍스트로 먼저 파싱 후 상태코드별 한국어 메시지

## 6. 오디오 캡처 세부

### 6.1 로컬판 (WASAPI loopback via `soundcard`)
- 별도 드라이버 설치 없이 동작
- 마이크 + 스피커 출력 두 스트림을 **하나의 WAV로 믹싱**
- 믹싱 시: 샘플레이트 리샘플 / 채널 다운믹스(모노) / 길이 zero-pad
- 블루투스 이어폰에서 loopback 캡처 누락 가능 → 주석·README 안내
- 별도 녹음 스레드에서 `comtypes.CoInitializeEx()` 필수 (멀티스레드 COM 초기화)

### 6.2 웹판 (브라우저 `getDisplayMedia`)
- `displaySurface: "monitor"` + `systemAudio: "include"` 옵션으로 다이얼로그 기본값 "전체 화면 + 시스템 오디오"
- 다이얼로그 자체는 브라우저 보안상 우회 불가 (사용자 클릭 1회 필수)
- 사용자 옵션: "시스템 오디오도 녹음" 체크박스 (끄면 다이얼로그 미표시, 마이크만)
- 세 가지 상태 구분:
  - `ok`: 화면 공유 + 시스템 오디오 토글 ON
  - `cancelled`: 다이얼로그 취소
  - `no_audio`: 공유는 했지만 시스템 오디오 토글 OFF
- 시스템 오디오 무음 경고: 2초 연속 무음일 때만 표시 (디바운스)

## 7. UI / 디자인 명세 (웹판)

- 한국어 가독성 최상: **Pretendard Variable** 폰트
- 흰색 배경, 카드 기반 레이아웃, 옅은 그림자
- 보라 그라데이션 텍스트 타이틀
- 두 버튼 그라데이션 + 호버 시 살짝 떠오름
- 녹음 중: 빨간 펄스 애니메이션
- 모바일 반응형

## 8. 키·시크릿
- `.env`에 `GEMINI_API_KEY` 보관
- `.env`는 `.gitignore`로 제외
- Vercel은 Environment Variables 대시보드에 등록
- 발급: https://aistudio.google.com/apikey

## 9. 검증 전략

### 9.1 자동 테스트 (pytest, 로컬판만)
- 오디오 믹싱 (다양한 SR·채널·길이 케이스)
- 파일명/경로 생성 (`meeting_YYYYMMDD_HHMMSS.wav`, `_MEIPASS` 번들 경로)
- 회의록 조립 (본문 + 시간 + 전사 결합, 초→포맷 변환)
- LLM 재시도 (지수 백오프 / 최종 실패 / 전사 원본 보존)
- 31개 테스트 작성·통과 기준

### 9.2 수동 검증 체크리스트
- 실제 마이크 + WASAPI loopback 캡처
- faster-whisper 한국어 전사 품질
- Streamlit/Next.js UI 흐름
- PyInstaller 클린 환경 빌드 결과

## 10. 테스트용 외부 영상
- https://www.youtube.com/shorts/r1A7klnkxwY
- https://www.youtube.com/shorts/gF1x6fjTx2w
