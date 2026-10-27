# Monicap 2.0 — 범용 Windows 화면 캡처 (Python 호출, LAN 자동 검색, 화면 안정 대기·창 캡처)

Windows PC(서버)의 현재 화면을 다른 PC(클라이언트)의 Python 프로그램에서 PNG로 받습니다.
특정 장비/프로그램의 API를 호출하지 않고 Windows 화면 픽셀을 그대로 캡처합니다.

> 1.x(ScopeCaptureAPI)에서 이름이 바뀌었습니다: `scope_capture_server.py` → `monicap_server.py`,
> `scope_capture_client.py` → `monicap_client.py`, `scope_discovery.py` → `monicap_discovery.py`,
> `ScopeCaptureClient` → `MonicapClient`, `discover_scopes` → `discover_devices`, `ScopeDevice` → `CaptureDevice`,
> `capture_scope` → `capture_screen`. 검색 프로토콜 service 이름도 `monicap`으로 바뀌어 1.x 서버/클라이언트와는 자동 검색이 되지 않습니다.
> 서버와 클라이언트를 함께 2.0으로 바꾸세요.
>
> 2.0부터 토큰 인증(capture_token.txt, HMAC 검색 서명)을 없앴습니다. 토큰 파일을 복사할 필요가 없고 `token`/`token_file` 인수도 없습니다.

## 준비

- 서버(캡처할 Windows PC): Python 3.9 이상 + Pillow.
- 클라이언트 PC: Python 3.9 이상. 자동 NIC 검색을 사용하려면 psutil 설치.
- 두 PC에 이 폴더를 각각 복사합니다.
- LAN 직결 또는 같은 서브넷. 두 PC의 IPv4가 서로 통신 가능한 상태여야 합니다.
- 회사 정책으로 인터넷 설치가 안 되면 호환되는 wheel을 별도로 준비합니다.

## 1. 서버에서 로컬 캡처부터 확인

폴더에서 PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install Pillow
.\.venv\Scripts\python.exe monicap_server.py --local-test test.png
```

test.png를 열어 화면이 제대로 찍혔는지 확인합니다.
기존 test.png가 있으면 이름을 바꾸세요. 기존 파일은 덮어쓰지 않습니다.

### 1-1. 특정 창만 찍기 (선택)

작업표시줄·바탕화면 없이 특정 프로그램 창 영역만 찍으려면 먼저 창 제목을 확인합니다.

```powershell
.\.venv\Scripts\python.exe monicap_server.py --list-windows
.\.venv\Scripts\python.exe monicap_server.py --window "메모장" --local-test test_window.png
```

- `--window 제목일부`: 캡처할 때마다 제목에 이 글자가 들어간 창(대소문자 무시, 맨 앞 창 우선)을 찾아 그 영역만 찍습니다.
  창이 없거나 최소화돼 있으면 캡처를 거절하고 이유를 돌려줍니다(HTTP 503, 클라이언트 `CaptureError` 메시지).
- 서버를 띄운 터미널 창은 제목에 명령줄이 보여도 제외합니다.
- `--require-foreground`: 그 창이 맨 앞에 있을 때만 찍습니다. 그 프로그램의 대화상자도 별도 창이라 켜 두면 거절될 수 있습니다.
- health 응답의 `window` 항목에 창을 찾았는지, 맨 앞인지, 영역이 나옵니다.
- 창 영역 위에 겹친 알림/대화상자는 그대로 찍힙니다. `--bbox` 와 같이 쓸 수 없습니다.
- `--bbox LEFT TOP RIGHT BOTTOM`: 화면의 고정 영역만 찍습니다.

## 2. 서버에서 자동 검색 모드로 실행

```powershell
.\.venv\Scripts\python.exe monicap_server.py --discovery --name LAB_PC_01
```

- TCP 8765(캡처), UDP 8766(검색)을 사용합니다.
- `--name`을 생략하면 컴퓨터 이름을 사용합니다.
- --discovery 사용 시 --bind를 생략하면 0.0.0.0으로 모든 IPv4 인터페이스에서 대기합니다.
- --discovery 없이 --bind를 생략하면 127.0.0.1에서만 대기합니다.
- 첫 실행에 capture_device_id.txt(검색용 장비 ID)가 생성됩니다. 다른 서버 PC에 복사하지 마세요.
- 클라이언트 PC에 복사할 파일은 없습니다.
- Ctrl+C로 서버를 종료합니다.
- 자동 IP가 바뀌는 환경에서는 고정 --allow-ip를 붙이지 않습니다. 고정 IP일 때만 사용하세요.

## 3. 방화벽 설정

서버 PC에서 실제 유선 어댑터 이름을 확인합니다:

```powershell
Get-NetAdapter
```

필요하면 관리자 PowerShell에서 다음 규칙을 추가하세요. `$lan`은 실제 어댑터 이름으로 바꿉니다.
직결 네트워크가 Public으로 분류되어도 동작하도록 Profile Any를 사용하되 해당 인터페이스와 같은 서브넷으로 제한합니다.

```powershell
$lan = "이더넷"
New-NetFirewallRule -DisplayName "Monicap TCP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -InterfaceAlias $lan -RemoteAddress LocalSubnet -Profile Any
New-NetFirewallRule -DisplayName "Monicap Discovery UDP" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 8766 -InterfaceAlias $lan -RemoteAddress LocalSubnet -Profile Any
```

회사 보안 정책/기존 방화벽 규칙이 우선할 수 있습니다. 반복 생성하지 말고 기존 규칙을 확인하세요.
**인증이 없습니다.** 서버 포트(TCP 8765)에 닿을 수 있는 PC는 누구나 이 화면을 받을 수 있고, 검색(UDP 8766)에도 응답합니다.
신뢰하는 LAN에서만 사용하고, 방화벽 규칙을 위처럼 같은 서브넷으로 제한하거나 `--allow-ip 클라이언트IP`로 한 대만 허용하세요. 인터넷 포트는 절대 열지 마세요.

규칙 삭제:

```powershell
Remove-NetFirewallRule -DisplayName "Monicap TCP"
Remove-NetFirewallRule -DisplayName "Monicap Discovery UDP"
```

## 4. 클라이언트 PC에서 Python 자동 연결

```powershell
py -m pip install psutil
py example_auto_connect.py
```

다른 Python 프로그램에서 사용:

```python
from monicap_client import MonicapClient

client = MonicapClient.auto_connect(
    discovery_timeout=2,
    timeout=5,
)
print(client.host)  # 자동으로 찾은 서버 IP
client.capture_to_file(r"D:\captures\capture.png")
# png_bytes = client.capture_png()  # 별도의 새 캡처를 bytes로 받기
```

호출 프로그램 옆에 monicap_client.py와 monicap_discovery.py를 두세요.
같은 LAN에서 `--discovery`로 실행 중인 Monicap 서버를 찾아 바로 연결합니다. 별도 페어링/토큰은 없습니다.

## 5. 인터페이스 지정 / 여러 서버 선택

```python
from monicap_discovery import list_interfaces, discover_devices
from monicap_client import MonicapClient

print(list_interfaces())
found = discover_devices(
    timeout=2,
    interface_names=["이더넷"],  # 실제 이름 사용. 생략하면 활성 IPv4 NIC 모두 검색
)
for device in found:
    print(device.name, device.device_id, device.host, device.port)

client = MonicapClient.auto_connect(
    name="LAB_PC_01",  # 또는 device_id="실제 장비 ID"
    interface_names=["이더넷"],
)
```

자동 열거는 유선뿐 아니라 활성 Wi-Fi/가상 NIC도 포함합니다. 유선만 원하면 interface_names로 제한하세요.
서버가 여러 대면 자동 연결은 임의로 하나를 선택하지 않고 오류를 반환합니다.

## 6. IP 조건

자동 검색은 IP를 설정하거나 네트워크 설정을 바꾸지 않습니다.
DHCP가 없는 직결 자동 IP 구성에서는 169.254.x.x / 16 주소가 생길 수 있습니다.
케이블 연결 직후 아직 주소가 없으면 기다린 뒤 다시 검색하세요. ipconfig로 양쪽 주소를 확인합니다.

고정 IP를 선호하면 예를 들어 클라이언트 192.168.50.1, 서버 192.168.50.2, 마스크 255.255.255.0으로 구성할 수 있습니다.
다른 NIC와 주소 대역이 겹치지 않게 정하세요. 자동 검색은 고정 IP에서도 가능합니다.
각 NIC의 서브넷 broadcast와 255.255.255.255에 검색 패킷을 보냅니다. 라우터 너머 검색은 지원하지 않습니다.
IP가 바뀐 뒤에는 auto_connect를 다시 호출합니다. 이미 생성한 클라이언트의 host는 자동 갱신되지 않습니다.

psutil 없이 직접 NIC 정보를 제공하는 고급 사용법:

```python
from monicap_discovery import NetworkInterface
client = MonicapClient.auto_connect(
    interfaces=[NetworkInterface("LAN", "169.254.10.20", "255.255.0.0")],
)
```

## 7. 수동 IP 호출

```python
client = MonicapClient("192.168.50.2", timeout=5)
print(client.health())
client.capture_to_file("capture.png")
```

이 방식은 psutil이 필요 없습니다. CLI:

```powershell
py monicap_client.py --host 192.168.50.2 --health
py monicap_client.py --host 192.168.50.2 --output capture.png
```

## 7-1. 화면이 멈출 때까지 기다렸다 찍기 (stable)

```python
png = client.capture_png(stable_ms=2000)                     # 최대 2초
png = client.capture_png(stable_ms=2000, interval_ms=100, frames=3)
client.capture_to_file("capture.png", stable_ms=2000)
```

- 서버가 interval_ms(기본 100, 20~1000) 간격으로 계속 찍어 frames(기본 3, 2~10)장이 연속으로 똑같으면 그 화면을 돌려줍니다.
  화면 갱신을 고정 대기로 짐작하지 않아도 됩니다.
- stable_ms(최대 10000) 안에 멈추지 않으면 `CaptureUnstable` (HTTP 504). 화면을 저장하지 않습니다.
  동영상·애니메이션·깜박이는 커서처럼 계속 바뀌는 화면은 멈추지 않습니다. 이런 경우 `--window`/`--bbox`로 범위를 줄이세요.
- 바뀐 직후 첫 장이 아직 이전 화면일 수 있으니, 화면을 바꾼 직후라면 짧은 대기(0.2~0.5초)를 함께 두는 것이 안전합니다.
- 응답 헤더 `X-Capture-Frames`(찍은 장수), `X-Capture-Stable-Ms`(멈출 때까지 걸린 시간)는 서버 로그에도 남습니다.
- 클라이언트 timeout 에 stable_ms 가 자동으로 더해집니다. 옵션을 지원하지 않는 서버면 404 → "update monicap_server.py".
- CLI: `py monicap_client.py --host 192.168.50.2 --output capture.png --stable-ms 2000`

## 8. 오류 처리와 동작 제약

```python
from monicap_discovery import DiscoveryError
from monicap_client import MonicapClient, CaptureError, CaptureBusy, CaptureUnstable

try:
    client = MonicapClient.auto_connect()
    client.capture_to_file("capture.png")
except DiscoveryError as error:
    print("검색/선택/연결 확인 실패:", error)
except CaptureBusy:
    print("다른 캡처 진행 중: 이번 요청은 실행되지 않았습니다")
except CaptureUnstable:
    print("화면이 stable_ms 안에 멈추지 않았습니다")
except (CaptureError, OSError, ValueError) as error:
    print("캡처/설정/저장 오류:", error)
```

- 모든 호출은 동기 방식. GUI에서는 작업 스레드에서 실행합니다.
- 같은 서버 프로세스는 한 번에 하나만 캡처합니다. 겹친 요청은 Busy로 거절하고 큐에 넣지 않습니다.
- 캡처 요청은 자동 재시도하지 않습니다. 검색 요청만 제한 시간 내 반복 전송합니다.
- health는 서버 응답 여부만 확인하며 실제 캡처 가능 여부는 확인하지 않습니다.
- PNG 구조/CRC 확인 후 임시 파일에서 최종 파일로 저장합니다. 이미 있는 파일은 덮어쓰지 않습니다.
- timeout은 네트워크 대기 제한입니다. 엄격한 전체 실행시간 제한/서버 캡처 강제 취소는 아닙니다.
- Windows 캡처가 멈춰 Busy가 지속되면 서버를 재시작해야 합니다.
- 서버 PC는 로그인/잠금 해제 상태여야 합니다. 화면 위의 다른 창과 알림도 그대로 찍힙니다.
- 주 모니터 기본 캡처. --bbox LEFT TOP RIGHT BOTTOM으로 영역 지정, --window 제목으로 창 영역만 캡처 가능.
  창이 보조 모니터에 있으면 주 모니터 밖이라 거절됩니다.
- PNG는 서버 메모리에서만 생성. 로그는 capture_server.log, 1MB × 현재 파일 및 백업 3개.

## 9. 자동 실행

작업 스케줄러: '로그온할 때', '사용자가 로그온한 경우에만 실행'.
프로그램은 가상환경 python.exe 절대 경로, 인수는 서버 파일 절대 경로와 --discovery --name LAB_PC_01,
시작 위치는 이 폴더로 지정합니다. 처음에는 수동 실행으로 확인하세요.

## 10. 테스트 범위

```powershell
py -m unittest -v test_capture_api.py test_discovery.py
```

26개 자동 테스트: 기본 캡처 API 6개 + 화면 안정 대기·창 캡처 11개 + 검색 9개.
창 찾기(user32 EnumWindows/DwmGetWindowAttribute)는 가짜 창 목록으로만 시험했습니다.
가짜 PNG/로컬 HTTP·UDP 소켓, NIC 열거 mock으로 검증했습니다.
실제 Windows 화면, Windows NIC broadcast/방화벽, APIPA 직결은 실환경에서 따로 확인해야 합니다.
다른 AI에게는 이 폴더와 MONICAP_AI_HANDOFF.md를 함께 전달하세요.
