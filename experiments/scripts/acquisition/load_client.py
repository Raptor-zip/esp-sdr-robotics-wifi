#!/usr/bin/env python3
"""Request paced TCP downlink from the experimental AP and save byte counts."""
import argparse
import json
import socket
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--host', default='10.78.0.1')
p.add_argument('--seconds', type=float, default=18)
p.add_argument('--mbps', type=float, default=20)
p.add_argument('--output', default='/tmp/sdr-load-result.json')
a = p.parse_args()
start = time.monotonic()
total = 0
with socket.create_connection((a.host, 5001), timeout=10) as s:
    s.settimeout(a.seconds + 10)
    s.sendall((json.dumps({'seconds': a.seconds, 'mbps': a.mbps}) + '\n').encode())
    while True:
        data = s.recv(65536)
        if not data:
            break
        total += len(data)
elapsed = time.monotonic() - start
result = dict(bytes_received=total, elapsed_s=elapsed,
              actual_mbps=total * 8 / elapsed / 1e6,
              requested_mbps=a.mbps, requested_seconds=a.seconds)
Path(a.output).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
