# Scope Capture API

Windows 기반 Tektronix MSO58B의 현재 화면을 외부 Python 프로그램에서 PNG로 받는 도구입니다.
TekScope API/VISA/SCPI를 호출하지 않고 Windows 화면 캡처를 사용합니다.

- Python 클래스 API: 연결 확인, PNG bytes 반환, 파일 저장
- LAN 직결 환경용 인증된 UDP 자동 검색
- 중복 캡처 요청 거절, 파일 덮어쓰기 방지
- 화면이 멈출 때까지 기다렸다 찍기(`stable_ms`), 지정 창(TekScope)만 찍기(`--window`)
- 테스트 26개 통과; 실제 MSO58B Windows 및 직결 LAN 검증은 별도 필요

## 안내

- [설치 및 사용법](README_KO.md)
- [다른 AI를 위한 인계 문서](ScopeCaptureAPI_AI_HANDOFF.md)
- [자동 연결 예제](example_auto_connect.py)
- [수동 연결 예제](example_integration.py)

## 빠른 시작

스코프에서 Python 3.9 이상과 Pillow를 준비하고 실행합니다.

```powershell
py -m pip install Pillow
py scope_capture_server.py --local-test test.png
py scope_capture_server.py --discovery --name MSO58B_01
# TekScope 창만 찍기 (창 제목 확인: --list-windows)
py scope_capture_server.py --discovery --name MSO58B_01 --window TekScope
```

생성된 `capture_token.txt`를 외부 PC에 별도로 복사합니다. 토큰은 저장소에 올리지 않습니다.
양쪽 IPv4가 서로 통신 가능해야 하며 TCP 8765 / UDP 8766 방화벽 설정은 한글 안내를 참고하세요.

외부 PC:

```powershell
py -m pip install psutil
```

```python
from scope_capture_client import ScopeCaptureClient

scope = ScopeCaptureClient.auto_connect(token_file="capture_token.txt")
scope.capture_to_file("capture.png")
# 화면이 멈출 때까지(100 ms 간격, 3장 연속 동일) 최대 2초 기다렸다 찍기
png = scope.capture_png(stable_ms=2000)
```

호출 프로그램 옆에 `scope_capture_client.py`와 `scope_discovery.py`를 둡니다.
최초 토큰 전달은 필요하며 자동 검색은 IP 설정을 변경하지 않습니다.

## 테스트

```powershell
py -m unittest -v test_capture_api.py test_discovery.py
```

HTTP 통신은 암호화되지 않으므로 신뢰하는 장비 LAN에서 사용합니다.
실제 화면 캡처는 로그인/잠금 해제된 Windows 세션에서 검증하세요.
