"""Loopback-only proof that one supervisor can release/restart traffic sockets."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/acquisition'))
from ros2_robot import Robot, RosHandler


class PacedLifecycleTests(unittest.TestCase):
    def setUp(self):
        # This exercises actual sockets on loopback, never the experiment WLAN.
        self.node = Robot.__new__(Robot)
        self.node.local = '127.0.0.2'; self.node.lock = threading.RLock()
        self.node.children = {}; self.node.current = None; self.node.run_id = None
        self.node.stop = threading.Event(); self.node.mode = 'ros'
        self.node.paced = None; self.node.paced_threads = []
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), RosHandler)
        self.server.node = self.node; self.server.token = 'loopback-test-token'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.node.stop_paced()
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def post(self, path, data):
        request = Request(self.base+path, data=json.dumps(data).encode(),
                          headers={'X-Lab-Token': 'loopback-test-token'}, method='POST')
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def tcp(self):
        until = time.monotonic()+2
        while True:
            try:
                return socket.create_connection((self.node.local, 5003), timeout=.2)
            except OSError:
                if time.monotonic() >= until:
                    raise
                time.sleep(.01)

    def test_switch_release_and_reuse_real_sockets(self):
        for run_id in (17, 18):
            with self.subTest(run_id=run_id):
                state = self.post('/switch_mode', {'mode': 'paced'})
                self.assertEqual((state['supervisor_mode'], state['helper_version']), ('paced', 2))
                self.post('/configure', {'run_id': run_id, 'requested_mbps': .1, 'seconds': 2})
                with self.tcp() as client:
                    client.settimeout(2)
                    self.assertGreater(len(client.recv(8192)), 0)
                    until = time.monotonic()+2
                    while True:
                        state = self.node.snapshot()
                        if state['sent_payload_bytes'][0] > 0 or time.monotonic() >= until:
                            break
                        time.sleep(.001)
                    self.assertEqual(state['run_id'], run_id)
                    self.assertGreater(state['sent_payload_bytes'][0], 0)
                    self.assertEqual(state['configuration_generation'], state['tcp_connection_generation'])
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                        udp.settimeout(.2); payload = bytes(range(64))
                        until = time.monotonic()+2
                        while True:
                            udp.sendto(payload, (self.node.local, 5140))
                            try:
                                echoed, _ = udp.recvfrom(2048)
                                break
                            except socket.timeout:
                                if time.monotonic() >= until:
                                    raise
                        self.assertEqual(echoed, payload)
                    state = self.post('/switch_mode', {'mode': 'ros'})
                self.assertEqual(state['supervisor_mode'], 'ros')
                self.assertIsNone(self.node.paced)
                self.assertFalse(self.node.paced_threads)
                with self.assertRaises(OSError):
                    socket.create_connection((self.node.local, 5003), timeout=.2)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as available:
                    available.bind((self.node.local, 5140))


if __name__ == '__main__':
    unittest.main()
