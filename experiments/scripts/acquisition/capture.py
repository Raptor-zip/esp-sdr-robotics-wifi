#!/usr/bin/env python3
"""Save actual C5 I/Q snapshots and their provenance; never synthesizes data."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import termios
import time
import zlib

import numpy as np
import serial


class Receiver:
    def __init__(self, device):
        self.device = device
        self.port = serial.Serial(device, 2000000, timeout=3, write_timeout=3)
        try:
            self.port.timeout = .2
            for attempt in range(4):
                marker = f'SYNC {time.time_ns() // 1000000}'.encode()
                self.port.write(b'\n\n' + marker + b'\n')
                pending = b''
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    pending = (pending + self.port.read(4096))[-8192:]
                    if marker + b'\n' in pending:
                        break
                else:
                    continue
                break
            else:
                raise TimeoutError('Cannot synchronize the C5 receiver')
            self.port.timeout = 3
            self.identity = self.command('INFO', 'C5SDR ')
            self.limits = self.command('LIMITS?', 'LIMITS ')
        except BaseException:
            self.restore_and_close()
            raise

    def command(self, text, prefix='OK'):
        self.port.write((text + '\n').encode('ascii'))
        end = time.monotonic() + 5
        while time.monotonic() < end:
            line = self.port.readline().decode('ascii', errors='replace').strip()
            if line.startswith(prefix):
                return line
            if line.startswith('ERR '):
                raise RuntimeError(f'{text}: {line}')
        raise TimeoutError(f'No {prefix!r} reply to {text}')

    def capture(self, count, rate):
        start = time.monotonic()
        header = self.command(f'CAP16 {count} {rate}', 'DATA ')
        _, n, crc, us = header.split()
        payload = bytearray()
        while len(payload) < int(n) * 2:
            part = self.port.read(int(n) * 2 - len(payload))
            if not part:
                raise TimeoutError('Truncated I/Q payload')
            payload.extend(part)
        actual = zlib.crc32(payload) & 0xffffffff
        if actual != int(crc, 16):
            raise RuntimeError('I/Q CRC mismatch')
        return np.frombuffer(payload, np.int8).copy().reshape(-1, 2), {
            'host_start_monotonic': start,
            'host_end_monotonic': time.monotonic(),
            'capture_us': int(us), 'crc32': crc,
        }

    def close(self):
        try:
            self.command('RELEASE')
        finally:
            self.restore_and_close()

    def restore_and_close(self):
        # pyserial sets VMIN=0; Chrome inherits it and mistakes read()==0
        # for a lost device. Restore blocking-byte semantics before close.
        try:
            attrs = termios.tcgetattr(self.port.fileno())
            attrs[6][termios.VMIN] = 1
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(self.port.fileno(), termios.TCSANOW, attrs)
        finally:
            self.port.close()


def measure(receiver, output, *, frequency=2412, rate=0, count=16380,
            frames=150, bandwidth=0, gain='HARDWARE', label='', context=None):
    fs = [80000000, 40000000, 20000000, 10000000, 8000000, 4000000][rate]
    receiver.command(f'FREQ {frequency}')
    receiver.command(f'BANDWIDTH {bandwidth}')
    receiver.command(f'GAIN {gain}')
    gain_before = receiver.command('GAIN?', 'GAIN ')
    shots, timing = [], []
    utc = dt.datetime.now(dt.timezone.utc).isoformat()
    for _ in range(frames):
        iq, metadata = receiver.capture(count, rate)
        shots.append(iq)
        timing.append(metadata)
    gain_after = receiver.command('GAIN?', 'GAIN ')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, iq=np.stack(shots))
    metadata = dict(label=label, utc_start=utc, identity=receiver.identity,
                    limits=receiver.limits, frequency_mhz=frequency,
                    sample_rate_hz=fs, rate_index=rate, samples=count,
                    frames=frames, bandwidth_mhz=bandwidth, gain=gain,
                    gain_before=gain_before, gain_after=gain_after,
                    timing=timing, context=context or {})
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(f'{output.name}: {frames} CRC-validated snapshots', flush=True)
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='/dev/ttyACM0')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frequency', type=int, default=2412)
    p.add_argument('--rate', type=int, default=0, choices=range(6))
    p.add_argument('--frames', type=int, default=150)
    p.add_argument('--bandwidth', type=int, default=0)
    p.add_argument('--gain', default='HARDWARE')
    p.add_argument('--label', default='')
    a = p.parse_args()
    r = Receiver(a.port)
    try:
        measure(r, a.output, frequency=a.frequency, rate=a.rate,
                frames=a.frames, bandwidth=a.bandwidth, gain=a.gain, label=a.label)
    finally:
        r.close()


if __name__ == '__main__':
    main()
