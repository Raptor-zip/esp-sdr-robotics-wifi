#!/usr/bin/env python3
"""Authenticated, bounded ROS 2 experiment supervisor on the robot laptop."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ros2_runtime import launch_role, stop_roles
from team_traffic import Handler
from operational_traffic import PacedTraffic


class Robot:
    def __init__(self, root, setup, local):
        self.root = root; self.setup = setup; self.local = local
        self.stop = threading.Event(); self.lock = threading.RLock()
        self.children = {}; self.current = None; self.run_id = None
        self.mode = 'ros'; self.paced = None; self.paced_threads = []
        addresses = json.loads(subprocess.run(['ip', '-j', 'address', 'show'], capture_output=True,
                                             text=True, check=True, timeout=5).stdout)
        self.interface = next(item['ifname'] for item in addresses
                              if any(address.get('local') == local for address in item['addr_info']))

    def power_save(self, state=None):
        if state is not None:
            assert state in ('on', 'off')
            subprocess.run(['iw', 'dev', self.interface, 'set', 'power_save', state],
                           capture_output=True, text=True, check=True, timeout=5)
        result = subprocess.run(['iw', 'dev', self.interface, 'get', 'power_save'],
                                capture_output=True, text=True, check=True, timeout=5).stdout.strip()
        actual = result.lower().removeprefix('power save: ').strip()
        assert actual in ('on', 'off')
        if state is not None:
            assert actual == state, 'Power-save setting did not match readback'
        return dict(state=actual, interface=self.interface, raw=result)

    def stop_trial(self):
        with self.lock:
            stop_roles(self.children.values())
            return self.snapshot()

    def configure(self, run_id, bulk, reliability, depth, seconds):
        assert self.mode == 'ros'
        assert bulk in ('off', 'heavy') and reliability in ('reliable', 'best_effort')
        assert depth in (1, 10) and 0 < seconds <= 60
        assert isinstance(run_id, int) and 0 < run_id < 2**31
        with self.lock:
            self.stop_trial()
            self.current = self.root/f'run-{run_id}'
            self.current.mkdir(parents=True, exist_ok=False)
            self.run_id = run_id
            self.children = {role: launch_role(role, run_id, seconds, bulk, reliability, depth,
                            self.current, self.setup, self.local, '192.168.8.1')
                             for role in ('echo', 'bulk')}
            return self.snapshot()

    def switch_mode(self, mode):
        assert mode in ('ros', 'paced')
        with self.lock:
            if mode == self.mode:
                return self.snapshot()
            if mode == 'paced':
                self.stop_trial()
                self.paced = PacedTraffic(self.local)
                self.paced_threads = [threading.Thread(target=target,daemon=True)
                                      for target in (self.paced.echo,self.paced.sender)]
                for thread in self.paced_threads:
                    thread.start()
            else:
                self.stop_paced()
            self.mode = mode
            return self.snapshot()

    def stop_paced(self):
        if self.paced is not None:
            self.paced.stop.set()
            for thread in self.paced_threads:
                thread.join(timeout=3)
            assert not any(thread.is_alive() for thread in self.paced_threads)
            self.paced = None; self.paced_threads = []

    def arm(self):
        with self.lock:
            assert self.mode == 'ros'
            assert self.current is not None and self.snapshot()['ready']
            (self.current/'arm').touch(exist_ok=False)
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            if self.mode == 'paced':
                return dict(self.paced.snapshot(), supervisor_version=2, supervisor_mode='paced')
            states = {}
            for role, child in self.children.items():
                p = self.current/(role+'.json')
                states[role] = dict(exit_code=child.poll(), measurement=json.loads(p.read_text()) if p.exists() else None)
            return dict(supervisor_version=2, supervisor_mode='ros', run_id=self.run_id, ready=len(states)==2 and all(s['measurement'] and s['measurement']['ready'] and s['exit_code'] is None for s in states.values()),
                        done=len(states)==2 and all(s['measurement'] and s['measurement']['done'] and s['exit_code']==0 for s in states.values()),
                        roles=states, semantics='Actual ROS 2 echo plus synthetic Image and PointCloud2 in separate processes')

    def trace(self, run_id, role, format):
        assert isinstance(run_id, int) and 0 < run_id < 2**31
        assert role in ('echo', 'bulk') and format in ('json', 'ndjson')
        path = self.root/f'run-{run_id}'/(role+'.'+format)
        data = path.read_bytes()
        assert len(data) <= 32*1024*1024
        return data


class RosHandler(Handler):
    def do_GET(self):
        if urlsplit(self.path).path != '/trace':
            super().do_GET(); return
        if not self.auth():
            self.respond({'error':'unauthorized'},403); return
        try:
            query=parse_qs(urlsplit(self.path).query, strict_parsing=True)
            assert set(query)=={'run_id','role','format'} and all(len(value)==1 for value in query.values())
            format=query['format'][0]
            data=self.server.node.trace(int(query['run_id'][0]),query['role'][0],format)
            self.send_response(200)
            self.send_header('Content-Type','application/json' if format=='json' else 'application/x-ndjson')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('X-Trace-SHA256',hashlib.sha256(data).hexdigest())
            self.end_headers(); self.wfile.write(data)
        except FileNotFoundError:
            self.respond({'error':'trace not found'},404)
        except Exception as error:
            self.respond({'error':repr(error)},400)

    def do_POST(self):
        if not self.auth():
            self.respond({'error':'unauthorized'},403); return
        try:
            data=json.loads(self.rfile.read(min(4096,int(self.headers.get('Content-Length','0')))))
            if self.path=='/configure':
                node=self.server.node
                self.respond(node.paced.configure(**data) if node.mode=='paced' else node.configure(**data))
            elif self.path=='/arm': self.respond(self.server.node.arm())
            elif self.path=='/stop_trial': self.respond(self.server.node.stop_trial())
            elif self.path=='/power_save': self.respond(self.server.node.power_save(**data))
            elif self.path=='/switch_mode': self.respond(self.server.node.switch_mode(**data))
            elif self.path=='/stop': self.respond({'stopping':True}); self.server.node.stop.set()
            else: self.respond({'error':'unknown request'},404)
        except Exception as error:
            self.respond({'error':repr(error)},400)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--local',default='192.168.8.20')
    p.add_argument('--seconds',type=float,default=3600)
    p.add_argument('--root',type=Path,default=Path('/tmp/esp-sdr-team/ros2'))
    p.add_argument('--setup',type=Path,default=Path('/opt/ros/jazzy/setup.bash'))
    args=p.parse_args(); node=Robot(args.root,args.setup,args.local)
    server=ThreadingHTTPServer((args.local,8134),RosHandler)
    server.daemon_threads=True; server.node=node; server.token=os.environ['TEAM_LAB_TOKEN']
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        print('READY ROS2 ROBOT SUPERVISOR',flush=True); node.stop.wait(args.seconds)
    finally:
        node.stop.set(); node.stop_trial(); node.stop_paced(); server.shutdown(); server.server_close()


if __name__=='__main__': main()
