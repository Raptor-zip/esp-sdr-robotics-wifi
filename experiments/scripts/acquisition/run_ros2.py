#!/usr/bin/env python3
"""Actual PC-to-PC ROS 2 QoS matrix, run after rate/shape measurements."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import random
import secrets
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from board import Board
from run_operational import connect_other_pair
from run_two_team import ROOT, TOKEN, api, capture
from ros2_runtime import launch_role, stop_roles
from timed_capture import TimedReceiver


def role_states(path, children):
    result = {}
    for role, child in children.items():
        p = path/(role+'.json')
        result[role] = dict(exit_code=child.poll(), measurement=json.loads(p.read_text()) if p.exists() else None)
    return result


def save_result(path, result):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, indent=2)+'\n')
    temporary.replace(path.with_suffix('.json'))


def download_robot_traces(args, result):
    remote_directory = Path(result['context']['role_directory'])/'robot'
    remote_directory.mkdir(exist_ok=True)
    if args.trace_transport == 'http':
        hashes={}
        for role in ('echo','bulk'):
            for format in ('json','ndjson'):
                name=role+'.'+format
                request=Request(f'http://192.168.8.20:8134/trace?run_id={result["run_id"]}&role={role}&format={format}',
                                headers={'X-Lab-Token':TOKEN})
                for attempt in (1,2,3):
                    try:
                        with urlopen(request,timeout=12) as response:
                            size=int(response.headers['Content-Length'])
                            assert 0<=size<=32*1024*1024
                            data=response.read(size+1)
                            assert len(data)==size
                            digest=hashlib.sha256(data).hexdigest()
                            assert digest==response.headers['X-Trace-SHA256']
                        temporary=remote_directory/(name+'.tmp'); temporary.write_bytes(data)
                        temporary.replace(remote_directory/name); hashes[name]=digest
                        break
                    except (URLError,TimeoutError,OSError):
                        if attempt==3: raise
                        time.sleep(1)
        result['trace_download_transport']='authenticated experiment-Wi-Fi HTTP after measurement'
        result['trace_download_sha256']=hashes
        return
    assert args.robot_host,'--robot-host is required for SSH trace transport'
    ssh_options = ['-4', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
    if args.ssh_host_key_alias:
        ssh_options.extend(['-o', f'HostKeyAlias={args.ssh_host_key_alias}'])
    base = f'root@{args.robot_host}:/tmp/esp-sdr-team/ros2/run-{result["run_id"]}/'
    command = ['scp', '-q', *ssh_options, *(base+name for name in
               ('echo.json', 'echo.ndjson', 'bulk.json', 'bulk.ndjson')), str(remote_directory)]
    for attempt in (1, 2, 3):
        try:
            subprocess.run(command, check=True, timeout=30)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 3:
                raise
            time.sleep(1)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--pilot',action='store_true')
    p.add_argument('--experiment', choices=['qos', 'power'], default='qos')
    p.add_argument('--robot-host')
    p.add_argument('--trace-transport',choices=['http','ssh'],default='http')
    p.add_argument('--ssh-host-key-alias',help='Previously verified SSH host key alias when connecting by IP')
    p.add_argument('--seconds',type=int,default=30); args=p.parse_args()
    assert 1 <= args.seconds <= 30
    if args.experiment == 'power':
        subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'check_ros2.py'),
                        '--require-complete'], check=True)
    lock=(ROOT/'evidence/acquisition.lock').open('w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    boards=[]; receiver=None; children={}; capture_thread=None
    session_id='ros2-'+args.experiment+'-'+secrets.token_hex(4)
    cases=[]
    for rep in (1,2,3):
        if args.experiment == 'qos':
            group=[(rep,'off','best_effort',1,ch,'off') for ch in (6,7,11)]
            group += [(rep,'heavy',reliability,depth,ch,'off') for reliability in ('reliable','best_effort')
                      for depth in (1,10) for ch in (6,7,11)]
        else:
            group=[(rep,bulk,'best_effort',1,ch,power) for bulk in ('off','heavy')
                   for ch in (6,11) for power in ('on','off')]
        random.Random((17000 if args.experiment=='qos' else 18000)+rep).shuffle(group); cases.extend(group)
    if args.pilot: cases=[(1,'heavy','best_effort',1,11,'off' if args.experiment=='qos' else 'on')]
    try:
        for port,baud in [('/dev/ttyUSB0',115200),('/dev/ttyUSB1',115200),('/dev/ttyUSB2',460800)]:
            boards.append(Board(port,baud))
        client,other,legacy_controller=boards
        legacy_controller.command('STOP')
        receiver=TimedReceiver('/dev/ttyACM0')
        for rep,bulk,reliability,depth,ch,power in cases:
            label=(f'op-ros2-{bulk}-{reliability}-d{depth}-ch{ch}-r{rep}' if args.experiment=='qos'
                   else f'op-power-{bulk}-ps{power}-ch{ch}-r{rep}')
            name=f'{"pilot-" if args.pilot else ""}{label}'
            out=ROOT/'raw'/name
            if out.with_suffix('.json').exists():
                recorded=json.loads(out.with_suffix('.json').read_text())
                if not recorded.get('trace_download_complete', True):
                    download_robot_traces(args, recorded)
                    recorded['trace_download_complete']=True; save_result(out, recorded)
                print('KEEP',name,flush=True); continue
            print('START',name,flush=True)
            setup=connect_other_pair(client,other,ch,name)
            api('/stop_trial', {})
            power_before=api('/power_save',dict(state=power))
            run_id=secrets.randbelow(1_000_000_000)+900000
            directory=ROOT/'raw/ros2-roles'/f'{name}-run-{run_id}'
            directory.mkdir(parents=True,exist_ok=False)
            children={role:launch_role(role,run_id,args.seconds,bulk,reliability,depth,directory,
                      '/opt/ros/humble/setup.bash','192.168.8.1','192.168.8.20') for role in ('control','sink')}
            api('/configure',dict(run_id=run_id,bulk=bulk,reliability=reliability,depth=depth,seconds=args.seconds))
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                local=role_states(directory,children); remote=api()
                if any(s['exit_code'] is not None for s in local.values()) or any(s['exit_code'] is not None for s in remote['roles'].values()):
                    raise RuntimeError('ROS 2 role exited before measurement: inspect private role logs')
                if all(s['measurement'] and s['measurement']['ready'] for s in local.values()) and remote['ready']:
                    break
                time.sleep(.3)
            else: raise RuntimeError('ROS 2 endpoint matching timeout; inspect private DDS logs')
            load_ack=other.command(f'LOAD 1000 {args.seconds+14}'); time.sleep(3)
            context=dict(repeat=rep,bulk=bulk,reliability=reliability,depth=depth,
                         acquisition_session_id=session_id,
                         experiment=args.experiment,power_save=power,robot_power_before=power_before,
                         own_channel=6,own_width_mhz=20,other_channel=ch,other_width_mhz=20,
                         setup_attempts=len(setup),setup_history=setup,
                         other_load_ack=load_ack,
                         layout=dict(description='All boards and PCs on one desk, approximately 30 cm spacing, fixed throughout this series; exact pair distances and orientations not measured',source='user report',moving_people='negligible influence reported by user'),
                         board1_before=client.state(),board2_before=other.state(),
                         local_roles_before=local,robot_before=remote,
                         robot_diagnostics=api('/diagnostics'),
                         route_to_robot=subprocess.run(['ip','route','get','192.168.8.20'],capture_output=True,text=True,check=True).stdout,
                         controller_power_readback=subprocess.run(['iw','dev','wlp132s0f0','get','power_save'],capture_output=True,text=True,check=True).stdout,
                         before_ns=time.monotonic_ns(),wall_before_ns=time.time_ns(),
                         role_directory=str(directory))
            assert context['board1_before']['version']==context['board2_before']['version']==7
            assert context['board1_before']['primary']==context['board2_before']['primary']==ch
            errors=[]
            def record():
                try: capture(receiver,out,args.seconds,2442)
                except BaseException as error: errors.append(repr(error))
            thread=threading.Thread(target=record); capture_thread=thread; thread.start()
            (directory/'arm').touch(exist_ok=False); api('/arm',{})
            deadline=time.monotonic()+args.seconds+12
            while time.monotonic()<deadline:
                local=role_states(directory,children)
                # Keep HTTP supervisor polling out of the 30-second radio
                # measurement. Local files prove completion without sending
                # extra Wi-Fi TCP bursts or waking the PS-enabled robot STA.
                if any(s['exit_code'] not in (None,0) for s in local.values()):
                    raise RuntimeError('ROS 2 role failed during measurement; retain partial traces')
                if all(s['measurement'] and s['measurement']['done'] and s['exit_code']==0 for s in local.values()):
                    remote=api()
                    if any(s['exit_code'] not in (None,0) for s in remote['roles'].values()):
                        raise RuntimeError('ROS 2 robot role failed; retain partial traces')
                    if remote['done']:
                        break
                time.sleep(.25)
            else: raise RuntimeError('ROS 2 bounded measurement did not finish: inspect retained private traces')
            thread.join(timeout=15)
            if thread.is_alive() or errors: raise RuntimeError('SDR capture failed: '+repr(errors))
            context.update(board1_after=client.state(),board2_after=other.state(),local_roles_after=local,robot_after=remote,
                           robot_power_after=api('/power_save',{}),
                           after_ns=time.monotonic_ns(),wall_after_ns=time.time_ns())
            elapsed=(context['after_ns']-context['before_ns'])/1e9
            result=dict(run_id=run_id,seconds=args.seconds,
                        other_delivered_mbps=(context['board1_after']['rx_bytes']-context['board1_before']['rx_bytes'])*8/elapsed/1e6,
                        context=context,sdr_errors=errors,
                        trace_download_complete=False,
                        semantics='Actual ROS 2 control echo and synthetic Image/PointCloud2; PC AP to robot STA; independent other-team saturated TCP; separate control and bulk processes')
            # Keep measured results before transfer. A failed SCP is retried
            # as a transfer; it never causes a bad RF trial to be repeated.
            save_result(out,result); download_robot_traces(args,result)
            result['trace_download_complete']=True; save_result(out,result)
            api('/stop_trial',{}); other.command('LOAD 0 0'); stop_roles(children.values()); children={}
            api('/power_save',dict(state='off'))
            print('RESULT',name,'otherMbps',result['other_delivered_mbps'],'roles_complete',True,flush=True)
    finally:
        stop_roles(children.values())
        if capture_thread is not None and capture_thread.is_alive():
            capture_thread.join(timeout=args.seconds+15)
        try: api('/stop_trial',{})
        except Exception: pass
        try: api('/power_save',dict(state='off'))
        except Exception: pass
        for board in boards[:2]:
            try: board.command('STOP')
            except Exception: pass
        for board in boards: board.close()
        if receiver:
            try: receiver.command('FREQ 2412'); receiver.command('BANDWIDTH 0'); receiver.command('GAIN HARDWARE'); receiver.close()
            except Exception: pass


if __name__=='__main__': main()
