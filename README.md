# 회의 녹음 & 정리 시스템

회의를 녹음하면 자동으로 전사하고 구조화된 회의록을 만들어주는 도구.
**로컬 Python (Streamlit)** 버전과 **웹 (Next.js + Vercel)** 버전 두 가지가 같은 저장소에 있습니다.

## 🌐 웹 버전 (Vercel 배포)

브라우저에서 녹음 → Gemini API로 전사 + 회의록 생성.

### Vercel 배포 방법

1. [vercel.com](https://vercel.com)에서 이 저장소를 import
2. **Framework Preset**: Next.js (자동 감지)
3. **Environment Variables** 에 `GEMINI_API_KEY` 추가
   - [Google AI Studio](https://aistudio.google.com/apikey)에서 발급
4. Deploy 클릭

### 로컬 개발

```bash
npm install
echo "GEMINI_API_KEY=your-key-here" > .env.local
npm run dev
# http://localhost:3000
```

### 사용법

1. **회의 시작** 클릭 → 마이크 권한 허용
2. 화면 공유 다이얼로그가 뜨면 회의 탭(Zoom/Meet 등)을 선택하고 **"탭 오디오 공유"** 체크 → 시스템 오디오도 함께 녹음됨 (거부하면 마이크만 녹음)
3. **회의 종료** 클릭 → Gemini가 전사 + 회의록 생성
4. 결과 확인 후 다운로드 가능

### 제약

- Vercel Hobby 플랜: 함수 timeout 10초 → 5분 이상 오디오 처리 어려움. Pro 플랜(60초) 권장
- 요청 body 크기: 4.5MB → WebM Opus 64kbps로 약 5분 가능
- 시스템 오디오 캡처는 Chrome/Edge에서 탭 공유 + 탭 오디오 옵션 사용

## 🖥️ 로컬 Python 버전 (Streamlit)

Windows에서 WASAPI loopback으로 시스템 오디오 + 마이크를 직접 캡처. 오프라인 동작 가능.

### 설치 & 실행

```bash
uv venv --python 3.11 .venv
.venv\Scripts\activate
uv pip install -r requirements.txt

# whisper medium 모델 다운로드
python -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8', download_root='whisper-medium')"

# .env에 GEMINI_API_KEY 설정
echo GEMINI_API_KEY=your-key-here > .env

streamlit run streamlit_app.py
```

### 테스트

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

### 파일 구조

```
# 웹 버전 (Vercel)
├── app/                   # Next.js App Router
│   ├── page.tsx          # 녹음 UI
│   ├── layout.tsx
│   ├── globals.css
│   └── api/process/route.ts  # Gemini API 호출
├── package.json
├── tsconfig.json
├── next.config.ts
├── vercel.json

# 로컬 버전 (Streamlit)
├── streamlit_app.py
├── utils.py               # 녹음·믹싱·전사
├── llm_prompt.py          # Gemini 호출
├── requirements.txt
├── build.spec             # PyInstaller --onedir
├── tests/                 # pytest (31개)
└── whisper-medium/        # faster-whisper 모델 (gitignore)
```

## API 키

[Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 발급.
