"""Authenticated, scoped trace retrieval with source content hashes."""
import hashlib
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/acquisition'))
from ros2_robot import Robot, RosHandler


class TraceTransferTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(); root = Path(self.directory.name)
        run = root/'run-37'; run.mkdir()
        self.payload = b'{"seq":0,"kind":"command_echoed"}\n'
        (run/'echo.ndjson').write_bytes(self.payload)
        self.node = Robot.__new__(Robot); self.node.root = root
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), RosHandler)
        self.server.node = self.node; self.server.token = 'synthetic-test-token'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, query, token='synthetic-test-token'):
        return urlopen(Request(self.base+'/trace?'+query, headers={'X-Lab-Token':token}), timeout=2)

    def test_payload_and_source_hash(self):
        with self.request('run_id=37&role=echo&format=ndjson') as response:
            data = response.read()
            self.assertEqual(data, self.payload)
            self.assertEqual(int(response.headers['Content-Length']), len(data))
            self.assertEqual(response.headers['X-Trace-SHA256'], hashlib.sha256(data).hexdigest())

    def test_authentication_is_required(self):
        with self.assertRaises(HTTPError) as raised:
            self.request('run_id=37&role=echo&format=ndjson', token='wrong')
        self.assertEqual(raised.exception.code, 403)

    def test_path_escape_and_duplicate_parameters_are_rejected(self):
        for query in ('run_id=37&role=../echo&format=ndjson',
                      'run_id=-1&role=echo&format=ndjson',
                      'run_id=37&role=echo&format=../../secret',
                      'run_id=37&run_id=38&role=echo&format=ndjson'):
            with self.subTest(query=query):
                with self.assertRaises(HTTPError) as raised:
                    self.request(query)
                self.assertEqual(raised.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
