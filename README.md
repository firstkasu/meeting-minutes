# 회의 녹음 & 정리 시스템

Windows 11에서 동작하는 로컬 회의 녹음·전사·회의록 자동 생성 도구.

- **회의 시작** → 마이크 + 시스템 오디오(WASAPI loopback) 동시 녹음
- **회의 종료** → faster-whisper 전사 → Claude API 회의록 생성

## 실행 방법

### 1. 환경 설정

```bash
# uv 사용 시
uv venv --python 3.11 .venv
.venv\Scripts\activate
uv pip install -r requirements.txt

# 또는 pip 사용 시
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API 키 설정

`.env.example`을 `.env`로 복사 후 Anthropic API 키 입력:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### 3. faster-whisper 모델 준비

medium 모델을 프로젝트 루트의 `whisper-medium/` 폴더에 배치:

```bash
# 자동 다운로드 (최초 1회, 인터넷 필요)
python -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8')"
```

다운로드된 모델을 `whisper-medium/`으로 복사하면 오프라인 사용 가능.

### 4. 앱 실행

```bash
streamlit run streamlit_app.py
```

브라우저에서 `http://localhost:8501` 자동 열림.

## WASAPI Loopback 원리 및 제약

- Windows WASAPI loopback을 사용하여 **스피커 출력을 캡처**합니다.
- 별도 드라이버(VB-Cable 등) 설치 불필요.
- 화상회의(Zoom/Meet/Teams)에서 상대방 목소리 + 내 목소리 모두 녹음됩니다.

### 알려진 제약

- **블루투스 이어폰/헤드셋**: loopback 캡처가 누락될 수 있습니다. 유선 스피커/이어폰 권장.
- **배타적 모드**: 일부 앱이 오디오 장치를 배타적으로 점유하면 캡처 실패 가능.

## PyInstaller 빌드 (--onedir)

```bash
pip install pyinstaller
pyinstaller build.spec
```

빌드 결과: `dist/MeetingRecorder/` 폴더.

### 빌드 전 확인

- `whisper-medium/` 폴더에 모델 파일이 있어야 번들에 포함됩니다.
- CTranslate2, ONNX Runtime DLL이 자동 수집됩니다.

### 클린 환경 실행 검증

1. Python이 설치되지 않은 다른 PC (또는 venv 비활성 상태)에서 테스트
2. `dist/MeetingRecorder/MeetingRecorder.exe` 실행
3. 브라우저가 자동으로 열리며 앱 동작 확인

### SmartScreen 경고

코드 서명이 없으므로 Windows SmartScreen에서 "알 수 없는 앱" 경고가 뜹니다.
"추가 정보" → "실행"을 클릭하면 정상 실행됩니다.

## 수동 검증 체크리스트

### 녹음 (loopback + 마이크)

- [ ] 스피커에서 소리 재생 중 녹음 → WAV에 스피커 소리 포함
- [ ] 마이크에 말하며 녹음 → WAV에 내 목소리 포함
- [ ] 동시 녹음 → 두 소리 모두 포함
- [ ] 블루투스 헤드셋 → loopback 누락 가능 확인

### 전사 (faster-whisper)

- [ ] 한국어 음성 → 한국어 텍스트로 전사
- [ ] medium 모델 로드 성공 (GPU/CPU 자동 감지)
- [ ] 전사 텍스트 `.txt`로 저장 확인

### Streamlit UI

- [ ] "회의 시작" 클릭 → "녹음 중..." + 경과시간 표시
- [ ] "회의 종료" 클릭 → 전사 → 회의록 생성 → 결과 표시
- [ ] 경과시간 1초마다 갱신
- [ ] 녹음 중 "회의 시작" 비활성화
- [ ] 결과에 회의록 본문 + 전체 회의 시간 표시
- [ ] "전체 녹음 내용 (상세)" expander로 접힘

### PyInstaller 패키징

- [ ] `pyinstaller build.spec` 빌드 성공
- [ ] Python 미설치 환경에서 exe 실행 성공
- [ ] Streamlit 서버 기동 + 브라우저 열림
- [ ] 녹음·전사·회의록 생성 정상 동작

## 파일 구조

```
├── streamlit_app.py       # Streamlit 메인 앱
├── utils.py               # 녹음·믹싱·전사 유틸리티
├── claude_prompt.py       # Anthropic API 호출·프롬프트
├── .env.example           # API 키 템플릿
├── build.spec             # PyInstaller 빌드 설정
├── requirements.txt       # Python 의존성
├── test_loopback_manual.py # loopback 수동 테스트
├── tests/                 # pytest 테스트
│   ├── test_audio_mixing.py
│   ├── test_paths.py
│   ├── test_assembly.py
│   └── test_api_retry.py
├── recordings/            # 녹음 파일 (자동 생성)
└── whisper-medium/        # faster-whisper 모델 (수동 배치)
```
