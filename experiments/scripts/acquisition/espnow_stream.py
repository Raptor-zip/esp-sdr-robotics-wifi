"""Read continuous ESP-NOW UART event blocks with CRC and end verification."""
import time
import zlib

import numpy as np


def read_exact(port, size, timeout=3):
    data = bytearray(); deadline = time.monotonic()+timeout
    while len(data) < size and time.monotonic() < deadline:
        data.extend(port.read(size-len(data)))
    if len(data) != size:
        raise RuntimeError(f'ESP-NOW UART block truncated: {len(data)} of {size} bytes')
    return bytes(data)


def collect(board, run_id, hz, seconds):
    assert hz in (20, 50, 100, 200) and 1 <= seconds <= 1200
    host_start = time.monotonic_ns()
    acknowledgement = board.command(f'RUN {run_id} {hz} {seconds}')
    assert acknowledgement == 'OK RUN'
    deadline = time.monotonic()+seconds+15
    blocks = []; timing = []
    while time.monotonic() < deadline:
        line = board.port.readline()
        if not line:
            continue
        if not line.startswith(b'EVT '):
            raise RuntimeError('Unexpected ESP-NOW UART data: '+repr(line))
        _, size, crc = line.decode('ascii').strip().split()
        size = int(size); assert 16 <= size <= 2048 and size % 16 == 0
        payload = read_exact(board.port, size)
        if zlib.crc32(payload) != int(crc, 16):
            raise RuntimeError('ESP-NOW UART event block CRC mismatch')
        events = np.frombuffer(payload, dtype='<u4').reshape(-1, 4).copy()
        assert np.all((events[:, 0] >= 1) & (events[:, 0] <= 4))
        blocks.append(events); timing.append(time.monotonic_ns()-host_start)
        finish = events[events[:, 0] == 4]
        if len(finish):
            assert len(finish) == 1 and events[-1, 0] == 4
            assert finish[0, 1] == hz*seconds and finish[0, 3] == run_id
            assert (seconds+2)*1e6 <= finish[0, 2] < (seconds+8)*1e6, 'Incomplete or late continuous window'
            all_events = np.concatenate(blocks)
            return dict(events=all_events, host_start_ns=host_start,
                        host_end_ns=time.monotonic_ns(), block_received_ns=np.array(timing, dtype=np.int64),
                        block_event_counts=np.array([len(block) for block in blocks], dtype=np.int64),
                        all_crcs_verified=True, acknowledgement=acknowledgement)
    raise RuntimeError('ESP-NOW continuous UART recording exceeded bounded duration')
