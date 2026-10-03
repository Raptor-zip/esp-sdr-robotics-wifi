"""DDS interface restriction and bounded child lifecycle, shared by both PCs."""
import os
from pathlib import Path
import subprocess


def cyclone_configuration(local_address, peer_address):
    # Static discovery peers and one experimental IPv4 interface prevent DDS
    # from selecting the Ethernet internet uplink or Tailscale transport.
    return (f'<CycloneDDS><Domain id="any"><General><Interfaces>'
            f'<NetworkInterface address="{local_address}"/>'
            '</Interfaces><AllowMulticast>false</AllowMulticast></General>'
            '<Discovery><ParticipantIndex>auto</ParticipantIndex>'
            '<MaxAutoParticipantIndex>20</MaxAutoParticipantIndex><Peers>'
            f'<Peer address="{peer_address}"/></Peers></Discovery>'
            '</Domain></CycloneDDS>')


def launch_role(role, run_id, seconds, bulk, reliability, depth, output,
                setup, local_address, peer_address):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(ROS_DOMAIN_ID='77', RMW_IMPLEMENTATION='rmw_cyclonedds_cpp',
               ROS_LOCALHOST_ONLY='0',
               CYCLONEDDS_URI=cyclone_configuration(local_address, peer_address))
    command = ['bash', '-c', 'source "$1"; shift; exec "$@"', 'ros2-role', str(setup),
               'python3', str(Path(__file__).with_name('ros2_probe.py')), role,
               '--run-id', str(run_id), '--seconds', str(seconds), '--bulk', bulk,
               '--reliability', reliability, '--depth', str(depth),
               '--output', str(output), '--arm', str(output/'arm'), '--timeout', '100']
    with (output/(role+'.log')).open('w') as log:
        return subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)


def stop_roles(children):
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=5)
