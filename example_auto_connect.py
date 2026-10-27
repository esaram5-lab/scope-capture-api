"""Client PC: pip install psutil, then copy the server PC's capture_token.txt here."""
from datetime import datetime
from pathlib import Path
from monicap_client import MonicapClient
from monicap_discovery import list_interfaces, discover_devices


def main():
    token_file = Path(__file__).with_name('capture_token.txt')
    print('IPv4 interfaces:', list_interfaces())
    # Optional: interface_names=['Ethernet'] or ['이더넷'] using an actual name above.
    client = MonicapClient.auto_connect(
        token_file=token_file,
        discovery_timeout=2,
        timeout=5,
        # name='LAB_PC_01',
    )
    print('Connected:', client.host, client.port)
    name = datetime.now().strftime('screen_%Y%m%d_%H%M%S_%f.png')
    print('Saved:', client.capture_to_file(Path('captures') / name))


if __name__ == '__main__':
    main()
