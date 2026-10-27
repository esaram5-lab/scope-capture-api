"""Run on the client PC; edit SERVER_IP first."""
from datetime import datetime
from pathlib import Path
from monicap_client import MonicapClient, CaptureBusy, CaptureError

SERVER_IP = '192.168.0.10'


def main():
    client = MonicapClient(SERVER_IP, timeout=5)
    print(client.health())
    # Call after the screen you want to capture is shown.
    filename = datetime.now().strftime('screen_%Y%m%d_%H%M%S_%f.png')
    try:
        print('Saved:', client.capture_to_file(Path('captures') / filename))
    except CaptureBusy:
        print('Capture busy. This request was not queued.')
    except (CaptureError, OSError) as error:
        print('Capture failed:', error)


if __name__ == '__main__':
    main()
