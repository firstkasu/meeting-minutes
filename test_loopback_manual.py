"""수동 검증: WASAPI loopback + 마이크 동시 녹음 (5초).

실행법: python test_loopback_manual.py
결과: recordings/test_loopback.wav 생성

검증 체크리스트:
  [ ] 스피커에서 소리 재생 중 실행 → WAV에 스피커 소리 들림
  [ ] 마이크에 말하면서 실행 → WAV에 내 목소리 들림
  [ ] 둘 다 동시에 → WAV에 두 소리 합쳐서 들림
  [ ] 블루투스 이어폰 연결 시 → loopback 누락될 수 있음 (알려진 제약)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from utils import start_recording, stop_recording

print("=== WASAPI Loopback + 마이크 동시 녹음 테스트 (5초) ===")
print("스피커에서 음악/영상을 재생하면서 마이크에도 말해보세요.")
print("녹음 시작...")

state = start_recording()
time.sleep(5)

print("녹음 중지 및 저장...")
filepath, duration = stop_recording(state)
print(f"완료! 파일: {filepath} ({duration:.1f}초)")
print("이 파일을 재생해서 스피커+마이크 소리가 모두 들리는지 확인하세요.")
