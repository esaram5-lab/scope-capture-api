import io
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import zlib

from scope_capture_server import CaptureServer
from scope_capture_client import ScopeCaptureClient, CaptureError, CaptureBusy, validate_png


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)

PNG = (b'\x89PNG\r\n\x1a\n'
       + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
       + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b''))


class Tests(unittest.TestCase):
    def setUp(self):
        self.server = CaptureServer(('127.0.0.1', 0), 'test-token', lambda: PNG)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01})
        self.thread.start()
        self.client = ScopeCaptureClient('127.0.0.1', token='test-token', port=self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_bytes_save_preservation(self):
        self.assertEqual(self.client.health()['status'], 'ok')
        self.assertEqual(self.client.capture_png(), PNG)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / '한글' / 'screen.png'
            self.assertEqual(self.client.capture_to_file(dest), dest)
            self.assertEqual(dest.read_bytes(), PNG)
            with self.assertRaises(FileExistsError):
                self.client.capture_to_file(dest)
            self.assertEqual(dest.read_bytes(), PNG)
            self.assertEqual(list(dest.parent.iterdir()), [dest])

    def test_auth_and_ip(self):
        self.client.token = 'bad'
        with self.assertRaisesRegex(CaptureError, '401'):
            self.client.capture_png()
        self.client.token = 'test-token'
        self.server.allowed_ip = '192.0.2.1'
        with self.assertRaisesRegex(CaptureError, '403'):
            self.client.health()

    def test_overlap_rejected_not_queued(self):
        entered, release = threading.Event(), threading.Event()
        calls, result = [], []
        def capture():
            calls.append(1)
            entered.set()
            release.wait(2)
            return PNG
        self.server.capture = capture
        first = threading.Thread(target=lambda: result.append(self.client.capture_png()))
        first.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.client.health()['busy'])
            with self.assertRaises(CaptureBusy):
                self.client.capture_png()
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            first.join(2)
        self.assertEqual(result, [PNG])

    def test_capture_failure_releases_lock(self):
        def fail():
            raise RuntimeError('simulated locked desktop')
        self.server.capture = fail
        with self.assertRaisesRegex(CaptureError, '503'):
            self.client.capture_png()
        self.server.capture = lambda: PNG
        self.assertEqual(self.client.capture_png(), PNG)

    def test_timeout_then_recovery(self):
        release = threading.Event()
        self.server.capture = lambda: (release.wait(2), PNG)[1]
        self.client.timeout = 0.05
        try:
            with self.assertRaises(CaptureError):
                self.client.capture_png()
        finally:
            release.set()
        # Wait for the in-progress handler to release its capture lock.
        self.assertTrue(self.server.capture_lock.acquire(timeout=2))
        self.server.capture_lock.release()
        self.server.capture = lambda: PNG
        self.client.timeout = 2
        self.assertEqual(self.client.capture_png(), PNG)

    def test_corrupt_png_never_saved(self):
        self.server.capture = lambda: PNG[:-4]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'bad.png'
            with self.assertRaises(CaptureError):
                self.client.capture_to_file(target)
            self.assertFalse(target.exists())
        broken = bytearray(PNG)
        broken[20] ^= 1
        with self.assertRaises(CaptureError):
            validate_png(bytes(broken))


if __name__ == '__main__':
    unittest.main()
