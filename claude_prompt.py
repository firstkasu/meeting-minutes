"""Anthropic API 호출 및 프롬프트 관리."""

import time

import anthropic

MODEL = "claude-opus-4-7"
MAX_RETRIES = 3
BASE_DELAY = 1.0

SYSTEM_PROMPT = """당신은 회의록 작성 전문가입니다. 전사된 회의 내용을 분석하여 다음 구조로 정리하세요:

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

반드시 한국어로 작성하세요. 전사 텍스트에서 파악할 수 없는 정보는 추측하지 마세요."""


def generate_minutes(
    transcript: str,
    api_key: str,
    *,
    _clock: object = None,
) -> str:
    """전사 텍스트로 회의록 본문을 생성. 실패 시 지수 백오프 재시도."""
    sleep_fn = getattr(_clock, "sleep", time.sleep) if _clock else time.sleep

    client = anthropic.Anthropic(api_key=api_key)
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"다음 회의 전사 내용을 정리해주세요:\n\n{transcript}"}],
            )
            return response.content[0].text
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                sleep_fn(delay)

    raise RuntimeError(f"API 호출 {MAX_RETRIES}회 실패: {last_error}")
