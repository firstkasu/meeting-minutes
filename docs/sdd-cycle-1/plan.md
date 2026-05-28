# 4. Plan · plan.md

## 작업 원칙
- **TDD 우선**: 순수 로직은 테스트 → 구현 → 통과 → 커밋 순서
- **위험한 구간을 뒤로 미루지 않음**: 가장 불확실한 것(WASAPI loopback, PyInstaller, Vercel timeout)을 일찍 검증
- **사용자 승인 사이클**: 한 기능 끝나면 사용자에게 확인 → 다음 기능
- **의미 있는 단위로 git 커밋**

## 산출물 파일 트리

### 로컬판 (Python)
```
streamlit_app.py            # Streamlit UI
utils.py                    # 녹음·믹싱·전사
llm_prompt.py               # LLM 호출 (Gemini)
requirements.txt
.env / .env.example
build.spec                  # PyInstaller --onedir
test_loopback_manual.py     # WASAPI 수동 검증
tests/
  test_audio_mixing.py      # 10 tests
  test_paths.py             # 6 tests
  test_assembly.py          # 10 tests
  test_api_retry.py         # 5 tests
whisper-medium/             # 동봉 모델 (gitignore)
recordings/                 # 결과물 (gitignore)
```

### 웹판 (Next.js)
```
package.json
tsconfig.json
next.config.ts
vercel.json
app/
  layout.tsx
  page.tsx                  # 녹음 UI + 결과 표시
  globals.css               # Pretendard, 흰 배경, 카드
  api/process/route.ts      # Gemini 호출 (오디오 → 전사 + 회의록 JSON)
```

## 단계별 빌드 순서

### 1단계: 순수 로직 (TDD)
| 모듈 | 테스트 → 구현 → 검증 |
|---|---|
| `mix_audio` | SR/채널/길이 다른 두 배열 입력 → 공통 포맷 모노 출력 |
| `generate_meeting_filename`, `get_model_path` | 포맷·`_MEIPASS` 번들 경로 분기 |
| `format_duration`, `assemble_minutes` | 초→포맷, 본문+시간+전사 결합 |
| `generate_minutes` (Gemini 재시도) | mock으로 지수 백오프·실패 보존 |

### 2단계: WASAPI loopback 수동 검증 (이른 단계에 검증)
- 5초 녹음 → WAV에 마이크 + 스피커 소리 둘 다 들어가는지 직접 재생 확인
- 블루투스 헤드셋은 누락 가능성 안내

### 3단계: 녹음 모듈(스레드)
- `start_recording`/`stop_recording`: `threading.Event`로 안전한 중지
- `comtypes.CoInitializeEx()` 호출 (멀티스레드 COM 초기화 — WASAPI 호출 전 필수)
- `mic_chunks`, `loopback_chunks`를 누적 → `mix_audio` → WAV 저장

### 4단계: 전사 (`faster-whisper` medium)
- GPU(CUDA) 자동 감지, 없으면 CPU
- `download_root=whisper-medium`으로 동봉 모델 우선 사용

### 5단계: Streamlit UI
- `st.session_state`에 스레드 핸들·시작 시각·중지 플래그 보관
- `st_autorefresh(interval=1000)`로 경과 시간 갱신
- 결과: 본문 즉시 표시 + `st.expander`로 전사 전문

### 6단계: PyInstaller `--onedir`
- `.spec`에 CTranslate2·ONNX runtime·soundcard DLL · 동봉 medium 모델 명시
- Python 미설치 클린 환경에서 실행 검증
- SmartScreen 경고 README 안내

### 7단계 (피벗): Vercel 웹판 추가
- 같은 저장소에 Next.js 앱 공존 (Python 파일은 Vercel이 무시)
- 브라우저 MediaRecorder + Web Audio API로 마이크 + `getDisplayMedia` 믹싱
- Gemini API에 오디오 직접 전달 → 전사 + 회의록 한 번에 JSON으로 받기
- `app/api/process/route.ts`:
  - `maxDuration = 60` (Pro 플랜 기준)
  - 모델 fallback: `2.5-flash → 2.0-flash → flash-latest`
  - 모델당 28s AbortController timeout
  - >18MB 오디오는 Files API로 우회

## 위험 요소와 대응

| 위험 | 대응 |
|---|---|
| WASAPI loopback이 블루투스에서 누락 | README + 화면 안내, 유선 권장 |
| 별도 스레드에서 WASAPI 호출 시 COM 미초기화 (`0x800401f0`) | `comtypes.CoInitializeEx()` 진입 시 호출 |
| Streamlit rerun이 스레드 핸들 잃음 | `st.session_state`에 보관, 모든 상태 거기에 |
| Gemini 503 UNAVAILABLE (과부하) | 모델 fallback + 지수 백오프 재시도 |
| Vercel hobby timeout 10초 | 1분 미만 회의 제약, Pro 플랜 권장 |
| Vercel 함수 크래시 시 JSON 아닌 HTML 반환 → 클라이언트 `Unexpected token 'A'` | 응답을 텍스트로 먼저 받아 status별 한국어 메시지로 변환 |
| 브라우저 시스템 오디오 다이얼로그 우회 불가 | "전체 화면 + 시스템 오디오" 기본값으로 다이얼로그 띄움, 토글로 mic-only 모드 제공 |
| 시스템 오디오 무음 경고 깜빡임 | 2초 연속 무음 디바운스 |
| 사용자가 화면은 공유했지만 시스템 오디오 토글 OFF | `ok` / `cancelled` / `no_audio` 3-state 구분해 정확한 안내 |
| 한국→Google API 업로드 느림 (로컬 ~1KB/s) | Vercel 서버에서 호출하므로 GCP 인접 망 이용 |

## 검증 게이트

- 각 단계 끝 시점에 `pytest tests/` 전부 통과
- 수동 체크리스트:
  - 로컬: 5초 녹음 → 재생해서 마이크 + 스피커 소리 확인
  - 웹: 1분 녹음 → Vercel에서 회의록 생성 확인
- 빌드 검증:
  - 로컬: PyInstaller 클린 환경 실행
  - 웹: `npm run build` 통과
