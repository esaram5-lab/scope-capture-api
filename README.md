# Monicap

Windows PC의 현재 화면을 LAN 너머 다른 PC의 Python 프로그램에서 PNG로 받는 범용 화면 캡처 도구입니다.
특정 장비/프로그램의 API를 쓰지 않고 Windows 화면 픽셀을 그대로 캡처합니다.

- Python 클래스 API: 연결 확인, PNG bytes 반환, 파일 저장
- 직결/같은 서브넷 LAN용 UDP 자동 검색 (토큰·인증 설정 없음)
- 중복 캡처 요청 거절, 파일 덮어쓰기 방지
- 화면이 멈출 때까지 기다렸다 찍기(`stable_ms`), 특정 창만 찍기(`--window`), 영역 지정(`--bbox`)
- 테스트 26개 통과; 실제 Windows 화면 및 LAN 환경 검증은 별도 필요

## 안내

- [설치 및 사용법](README_KO.md)
- [다른 AI를 위한 인계 문서](MONICAP_AI_HANDOFF.md)
- [자동 연결 예제](example_auto_connect.py)
- [수동 연결 예제](example_integration.py)

## 빠른 시작

캡처할 Windows PC(서버)에서 Python 3.9 이상과 Pillow를 준비하고 실행합니다.

```powershell
py -m pip install Pillow
py monicap_server.py --local-test test.png
py monicap_server.py --discovery --name LAB_PC_01
# 특정 창만 찍기 (창 제목 확인: --list-windows)
py monicap_server.py --discovery --name LAB_PC_01 --window "메모장"
```

양쪽 IPv4가 서로 통신 가능해야 하며 TCP 8765 / UDP 8766 방화벽 설정은 한글 안내를 참고하세요.

클라이언트 PC:

```powershell
py -m pip install psutil
```

```python
from monicap_client import MonicapClient

client = MonicapClient.auto_connect()
client.capture_to_file("capture.png")
# 화면이 멈출 때까지(100 ms 간격, 3장 연속 동일) 최대 2초 기다렸다 찍기
png = client.capture_png(stable_ms=2000)
```

호출 프로그램 옆에 `monicap_client.py`와 `monicap_discovery.py`를 둡니다.
자동 검색은 IP 설정을 변경하지 않습니다.

## 테스트

```powershell
py -m unittest -v test_capture_api.py test_discovery.py
```

인증이 없어 서버 포트에 닿는 누구나 화면을 받을 수 있습니다. 신뢰하는 LAN에서만 쓰고, 방화벽을 같은 서브넷으로 제한하거나 `--allow-ip`로 클라이언트 IP를 지정하세요.
실제 화면 캡처는 로그인/잠금 해제된 Windows 세션에서 검증하세요.
