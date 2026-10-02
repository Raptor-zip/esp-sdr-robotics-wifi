#!/usr/bin/env python3
"""Temporary 64-byte UDP reflector on the Wi-Fi client; bounded by SIGTERM."""
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('0.0.0.0',5140))
while True:
 data,peer=s.recvfrom(2048)
 if len(data)==64:s.sendto(data,peer)
