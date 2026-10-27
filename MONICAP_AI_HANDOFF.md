# Monicap — AI 작업 인계 문서

작성일: 2026-10-27 (Asia/Seoul)
대상 코드: 이 저장소 (Monicap 2.0)
문서 목적: 다른 AI가 배경을 다시 질문하지 않고 현재 구현을 분석하고 다음 작업을 진행하도록 한다.

## 1. 배경과 목적

- Windows PC(서버)의 현재 화면을 LAN 너머 다른 PC(클라이언트)의 Python 프로그램에서 PNG로 받는 범용 화면 캡처 도구.
- 원래 오실로스코프(Tektronix MSO58B) 화면용 `ScopeCaptureAPI` 1.x로 시작했고, 2.0에서 특정 장비와 무관한 범용 도구 `Monicap`으로 이름과 문구를 바꿨다.
  동작/HTTP 규약은 그대로이고, 이름과 검색 service 문자열만 바뀌었다(아래 7절).
- 호출 프로그램은 Python. 타 언어 SDK, GUI는 요구되지 않았다.
- 일반적인 연결: LAN 직결(P2P) 또는 같은 서브넷. 공유기/DHCP가 항상 있다고 가정하지 않는다.

## 2. 핵심 설계 결정

1. 특정 프로그램/장비 API를 호출하지 않는다. 로그인된 Windows 사용자 세션에서 Pillow ImageGrab으로 화면 픽셀을 캡처한다.
2. 클라이언트는 `MonicapClient` 클래스를 import해서 사용한다. 내부 통신은 HTTP이며 호출자는 HTTP를 직접 다루지 않는다.
3. 캡처 중 추가 캡처 요청은 대기시키지 않고 즉시 Busy(409)로 거절한다.
4. 자동 재시도하지 않는다. 재시도하면 원한 시점과 다른 화면이 저장될 수 있다.
5. 서버에는 PNG를 쌓지 않는다. 메모리에서 인코딩해 반환한다.
6. 기존 파일을 덮어쓰지 않고, 검증된 완성 PNG만 최종 경로에 게시한다.

## 3. 파일

| 파일 | 역할 |
|---|---|
| monicap_server.py | Windows 캡처 서버, 단독 로컬 캡처 테스트(`--local-test`), 창 목록(`--list-windows`) |
| monicap_client.py | Python 클래스 API(`MonicapClient`), 편의 함수 `capture_screen`, CLI |
| monicap_discovery.py | 인증된 UDP 검색, NIC 열거, 서버 responder |
| example_auto_connect.py / example_integration.py | 자동/수동 연결 예제 |
| test_capture_api.py / test_discovery.py | 가짜 PNG·가짜 창·로컬 소켓 기반 테스트 26개 |
| README.md / README_KO.md | 개요, 설치·실행·네트워크·운영 안내 |

실행 시 생성: `capture_token.txt`(인증 토큰, 클라이언트에 복사), `capture_device_id.txt`(검색용 영구 UUID, 서버마다 고유),
`capture_server.log`(1MB × 백업 3개).

## 4. Python 공개 인터페이스

```python
MonicapClient(host, *, token=None, token_file=None, port=8765, timeout=5)
MonicapClient.auto_connect(*, token=None, token_file=None, name=None, device_id=None,
                           discovery_timeout=2, timeout=5, discovery_port=8766,
                           interface_names=None, interfaces=None, targets=None) -> MonicapClient
client.health() -> dict
client.capture_png(stable_ms=0, interval_ms=None, frames=None) -> bytes
client.capture_to_file(save_path, **같은 옵션) -> pathlib.Path
capture_screen(host, save_path, timeout=5, *, token=None, token_file=None, port=8765, stable_ms=0, ...)

discover_devices(timeout=2, *, token=None, token_file=None, discovery_port=8766,
                 interface_names=None, interfaces=None, targets=None) -> list[CaptureDevice]
```

- 수동 host는 IPv4 리터럴만. token_file 미지정 시 모듈 옆 `capture_token.txt`.
- 예외: `CaptureError`(통신/응답/PNG 검증), `CaptureBusy`(409), `CaptureUnstable`(504), `DiscoveryError`, `FileExistsError`, 기타 OSError/ValueError.
- `CaptureDevice` 필드: device_id, name, host, port, interface, local_address.
- auto_connect: 다른 device_id가 여러 개면 예외, 같은 장비의 여러 경로는 health 성공 순서로 선택.

## 5. HTTP 규약

헤더 `Authorization: Bearer <token>`. 클라이언트는 프록시/redirect를 쓰지 않는다. HTTPS 없음(신뢰 LAN 전제).

| 요청 | 응답 |
|---|---|
| GET /health | 200 JSON: status='ok', busy, desktop_checked=false, features=['stable','window'], (`--window` 시) window={title, found, matched, foreground, rect} |
| POST /capture?stable_ms=&interval_ms=&frames= | 200 image/png, 헤더 X-Capture-Started-UTC, (stable 시) X-Capture-Frames, X-Capture-Stable-Ms |

상태 코드: 400 잘못된 옵션/본문, 401 토큰, 403 --allow-ip 불일치, 404 경로, 409 Busy, 503 캡처/창 오류(이유 메시지 포함), 504 화면 미안정.

## 6. 서버 세부

- ThreadingHTTPServer + 단일 capture_lock(non-blocking). 연결 소켓 timeout 10초.
- `ImageGrab.grab(bbox, all_screens=False)` — 주 모니터만. `--bbox`로 영역, `--window TITLE`로 창 영역(캡처마다 다시 찾음).
- `WindowTarget`: EnumWindows z-order 순, 제목 부분 일치(대소문자 무시), 보이고 최소화 안 된 창. 자기 콘솔 창과 제목에
  `monicap_server`가 들어간 창은 제외. 영역은 DWMWA_EXTENDED_FRAME_BOUNDS(실패 시 GetWindowRect)를 주 화면으로 자른 값.
  `--require-foreground`면 맨 앞 창이어야 함. 문제는 `WindowError` → 503.
- `capture_until_stable`: interval_ms 간격으로 grab, frames장 연속 동일하면 그 프레임만 PNG 인코딩. 비교 키는 `(size, tobytes())`.
- 시작 시 DPI awareness 설정. OpenInputDesktop/SwitchDesktop으로 잠금 여부 확인.

## 7. 1.x → 2.0 이름 변경 표

| 1.x | 2.0 |
|---|---|
| scope_capture_server.py / scope_capture_client.py / scope_discovery.py | monicap_server.py / monicap_client.py / monicap_discovery.py |
| ScopeCaptureClient | MonicapClient |
| discover_scopes / ScopeDevice | discover_devices / CaptureDevice |
| capture_scope | capture_screen |
| 검색 service `'scope-capture'` | `'monicap'` (1.x와 검색 비호환) |
| HTTP Server 헤더 `ScopeCapture/1.0` | `Monicap/2.0` |

HTTP 경로·옵션·상태 코드, 토큰/장비 ID 파일명, 포트(8765/8766)는 그대로다.
`esaram5-lab/scope_tech`의 `scope_capture/` 폴더에는 1.2 사본이 들어 있으며 이번 변경과 별개다.

## 8. 검증 범위

- `python -m unittest -v test_capture_api.py test_discovery.py`: 26개 통과(가짜 PNG, 가짜 grab/창 목록, 루프백 HTTP/UDP, mock psutil).
- 실패 시나리오 테스트의 ERROR/WARNING 로그는 의도한 오류 주입 결과다.
- 미검증: 실제 Windows 화면 캡처·DPI·잠금/원격 세션, 실제 창 열거/DWM 경계, Windows NIC broadcast/방화벽, APIPA 직결, 장시간 연속 캡처.

## 9. 한계

- OS 캡처가 영구 정지하면 capture_lock이 계속 유지될 수 있다(서버 재시작 필요).
- 보조 모니터는 캡처하지 않는다. 보조 모니터의 창은 `--window`에서 off screen으로 거절된다.
- 동시 연결 수 상한 없음. 라우터 너머 검색, IPv6, 자동 IP 구성 미지원.
- 실환경 테스트를 통과했다고 주장하지 않는다.
