"""Windows desktop capture over LAN. No Tektronix API or SCPI calls."""
import argparse
import ctypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import socket
import uuid
import threading
import time


def capture_desktop(bbox=None):
    if os.name != 'nt':
        raise RuntimeError('Desktop capture is supported only on Windows.')
    # Fail rather than return a misleading desktop while locked/disconnected.
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.OpenInputDesktop.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
    user32.OpenInputDesktop.restype = ctypes.c_void_p
    user32.SwitchDesktop.argtypes = [ctypes.c_void_p]
    user32.SwitchDesktop.restype = ctypes.c_bool
    user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    desktop = user32.OpenInputDesktop(0, False, 0x0100)
    if not desktop:
        raise RuntimeError('Interactive desktop unavailable. Unlock the scope Windows session.')
    try:
        if not user32.SwitchDesktop(desktop):
            raise RuntimeError('Desktop locked or unavailable.')
    finally:
        user32.CloseDesktop(desktop)
    from PIL import ImageGrab
    with ImageGrab.grab(bbox=bbox, all_screens=False) as image:
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()


class CaptureServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, address, token, capture, allowed_ip=None):
        self.token = token
        self.capture = capture
        self.allowed_ip = allowed_ip
        self.capture_lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'ScopeCapture/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        # Do not log paths or headers, which may contain credentials.
        pass

    def respond(self, status, data, content_type='application/json', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def message(self, status, message):
        self.respond(status, json.dumps({'message': message}).encode())

    def authorized(self):
        if self.server.allowed_ip and self.client_address[0] != self.server.allowed_ip:
            self.message(403, 'Client IP not allowed')
            return False
        supplied = self.headers.get('Authorization', '')
        expected = 'Bearer ' + self.server.token
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            self.message(401, 'Invalid token')
            return False
        return True

    def do_GET(self):
        try:
            if not self.authorized():
                return
            if self.path != '/health':
                self.message(404, 'Not found')
                return
            self.respond(200, json.dumps({
                'status': 'ok', 'busy': self.server.capture_lock.locked(),
                'desktop_checked': False,
            }).encode())
        except (OSError, TimeoutError):
            pass

    def do_POST(self):
        started = time.monotonic()
        try:
            if not self.authorized():
                return
            if self.path != '/capture':
                self.message(404, 'Not found')
                return
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length', '0') != '0':
                self.message(400, 'Capture request must have an empty body')
                return
            if not self.server.capture_lock.acquire(blocking=False):
                self.message(409, 'Capture busy; request was not queued')
                return
            try:
                captured_at = datetime.now(timezone.utc).isoformat()
                try:
                    data = self.server.capture()
                except Exception:
                    logging.exception('Capture failed')
                    self.message(503, 'Desktop capture failed; check scope server log and unlocked session')
                    return
                self.respond(200, data, 'image/png', {'X-Capture-Started-UTC': captured_at})
                logging.info('capture OK client=%s bytes=%d seconds=%.3f',
                             self.client_address[0], len(data), time.monotonic() - started)
            finally:
                self.server.capture_lock.release()
        except (OSError, TimeoutError):
            logging.warning('Client disconnected or timed out')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', help='Default: 0.0.0.0 with --discovery, otherwise 127.0.0.1')
    parser.add_argument('--discovery', action='store_true', help='Enable authenticated UDP discovery')
    parser.add_argument('--discovery-port', type=int, default=8766)
    parser.add_argument('--name', default=socket.gethostname())
    parser.add_argument('--device-id-file', type=Path, default=Path(__file__).with_name('capture_device_id.txt'))
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--allow-ip', help='Only allow this controller IPv4')
    parser.add_argument('--token-file', type=Path, default=Path(__file__).with_name('capture_token.txt'))
    parser.add_argument('--bbox', nargs=4, type=int, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'))
    parser.add_argument('--local-test', type=Path, help='Save one local PNG and exit; no server')
    args = parser.parse_args()
    args.bind = args.bind or ('0.0.0.0' if args.discovery else '127.0.0.1')
    if not 1 <= args.port <= 65535 or not 1 <= args.discovery_port <= 65535:
        parser.error('Ports must be between 1 and 65535')
    if args.bbox and (args.bbox[2] <= args.bbox[0] or args.bbox[3] <= args.bbox[1]):
        parser.error('bbox requires RIGHT > LEFT and BOTTOM > TOP')
    if os.name != 'nt':
        parser.error('Run this server on the scope Windows desktop')
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    capture = lambda: capture_desktop(tuple(args.bbox) if args.bbox else None)
    if args.local_test:
        data = capture()
        args.local_test.parent.mkdir(parents=True, exist_ok=True)
        with args.local_test.open('xb') as output:
            output.write(data)
        print('Saved:', args.local_test)
        return
    log = RotatingFileHandler(Path(__file__).with_name('capture_server.log'),
                              maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[log, logging.StreamHandler()],
                        format='%(asctime)s %(levelname)s %(message)s')
    if not args.token_file.exists():
        with args.token_file.open('x', encoding='utf-8') as output:
            output.write(secrets.token_urlsafe(32))
        print('Created token file:', args.token_file)
    token = args.token_file.read_text(encoding='utf-8').strip()
    if len(token) < 24 or not token.isascii() or any(c.isspace() for c in token):
        parser.error('Token must be at least 24 ASCII characters without whitespace')
    with CaptureServer((args.bind, args.port), token, capture, args.allow_ip) as server:
        responder = None
        if args.discovery:
            from scope_discovery import DiscoveryResponder
            if not args.device_id_file.exists():
                with args.device_id_file.open('x', encoding='utf-8') as output:
                    output.write(str(uuid.uuid4()))
            device_id = args.device_id_file.read_text(encoding='utf-8').strip()
            responder = DiscoveryResponder(
                token, args.name, device_id, args.port, port=args.discovery_port,
                allowed_ip=args.allow_ip, api_bind=args.bind,
            ).start()
            logging.info('Discovery enabled UDP=%d name=%s id=%s', responder.port, args.name, device_id)
        logging.info('Listening on %s:%d; Ctrl+C stops server', args.bind, args.port)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            logging.info('Stopped')
        finally:
            if responder:
                responder.close()


if __name__ == '__main__':
    main()
