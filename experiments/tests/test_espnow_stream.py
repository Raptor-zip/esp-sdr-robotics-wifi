"""UART integrity cases; synthetic records are never physical measurements."""
import io
from pathlib import Path
import sys
import unittest
import zlib

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/acquisition'))
from espnow_stream import collect


class FragmentedPort(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(5, size))


class FakeBoard:
    def __init__(self, payload, corrupt=False):
        crc = zlib.crc32(payload) ^ int(corrupt)
        self.port = FragmentedPort(f'EVT {len(payload)} {crc:08x}\n'.encode()+payload)

    def command(self, command):
        if command != 'RUN 37 20 1':
            raise AssertionError(command)
        return 'OK RUN'


class IntegrityTests(unittest.TestCase):
    def record(self, run_id=37):
        return np.array([[1, 0, 1000, 0], [2, 0, 2000, 1000],
                         [3, 1, 1000000, 19], [4, 20, 3000000, run_id]], dtype='<u4').tobytes()

    def test_fragmented_payload_and_end(self):
        result = collect(FakeBoard(self.record()), 37, 20, 1)
        self.assertEqual(result['events'].shape, (4, 4))
        self.assertTrue(result['all_crcs_verified'])
        self.assertEqual(list(result['block_event_counts']), [4])

    def test_corrupt_block_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'CRC mismatch'):
            collect(FakeBoard(self.record(), corrupt=True), 37, 20, 1)

    def test_wrong_run_is_rejected(self):
        with self.assertRaises(AssertionError):
            collect(FakeBoard(self.record(run_id=38)), 37, 20, 1)


if __name__ == '__main__':
    unittest.main()
