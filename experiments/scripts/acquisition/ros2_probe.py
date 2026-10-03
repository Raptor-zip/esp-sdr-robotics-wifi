#!/usr/bin/env python3
"""Actual ROS 2 control echo and synthetic Image/PointCloud2 load.

Run one role per process, with DDS restricted to the experimental interface.
Every latency subtraction is within one process clock. Message headers are
sequence identifiers; clocks on the two computers are not assumed synchronized.
"""
import argparse
from array import array
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.utilities import get_rmw_implementation_identifier
from sensor_msgs.msg import Image, PointCloud2, PointField
from std_msgs.msg import UInt64MultiArray


def profile(reliability, depth):
    return QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=depth,
                      reliability=(ReliabilityPolicy.RELIABLE if reliability == 'reliable'
                                   else ReliabilityPolicy.BEST_EFFORT),
                      durability=DurabilityPolicy.VOLATILE)


class Probe(Node):
    def __init__(self, args):
        super().__init__(f'c5_lab_{args.role}_{args.run_id}')
        self.args = args
        self.origin_ns = time.monotonic_ns()
        self.arm_ns = None
        self.sequence = 0
        self.last_bulk_slot = -1
        self.sent = 0
        self.received = 0
        self.publish_calls = 0
        self.cpu_start_ns = time.process_time_ns()
        self.paths = args.output
        self.paths.mkdir(parents=True, exist_ok=True)
        self.trace = (self.paths / (args.role + '.ndjson')).open('w')
        self.pubs, self.subs = [], []
        base = f'/c5_lab/run_{args.run_id}'
        control_qos = profile('reliable', 10)
        bulk_qos = profile(args.reliability, args.depth)
        if args.role == 'control':
            self.publisher = self.create_publisher(UInt64MultiArray, base + '/command', control_qos)
            self.subscription = self.create_subscription(UInt64MultiArray, base + '/response', self.response, control_qos)
            self.pubs.append(self.publisher); self.subs.append(self.subscription)
        elif args.role == 'echo':
            self.publisher = self.create_publisher(UInt64MultiArray, base + '/response', control_qos)
            self.subscription = self.create_subscription(UInt64MultiArray, base + '/command', self.echo, control_qos)
            self.pubs.append(self.publisher); self.subs.append(self.subscription)
        elif args.role == 'bulk':
            self.image_pub = self.create_publisher(Image, base + '/image', bulk_qos)
            self.cloud_pub = self.create_publisher(PointCloud2, base + '/cloud', bulk_qos)
            self.pubs.extend([self.image_pub, self.cloud_pub])
            self.image = Image(height=360, width=640, encoding='rgb8', is_bigendian=0, step=1920,
                               data=bytes([0x35]) * (640 * 360 * 3))
            self.cloud = PointCloud2(height=1, width=4096,
                fields=[PointField(name=name, offset=index * 4, datatype=PointField.FLOAT32, count=1)
                        for index, name in enumerate(('x', 'y', 'z', 'intensity'))],
                is_bigendian=False, point_step=16, row_step=4096 * 16,
                data=array('f', [0., 0., 0., 1.] * 4096).tobytes(), is_dense=True)
        else:
            self.image_sub = self.create_subscription(Image, base + '/image', self.image_received, bulk_qos)
            self.cloud_sub = self.create_subscription(PointCloud2, base + '/cloud', self.cloud_received, bulk_qos)
            self.subs.extend([self.image_sub, self.cloud_sub])
        self.steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(.001, self.tick, clock=self.steady_clock)
        self.create_timer(.5, self.status, clock=self.steady_clock)
        self.status()

    def event(self, kind, **fields):
        self.trace.write(json.dumps(dict(kind=kind, **fields), separators=(',', ':')) + '\n')

    def status(self, done=False):
        self.trace.flush()
        now = time.monotonic_ns()
        counts = dict(publisher_matched_subscriptions=[p.get_subscription_count() for p in self.pubs],
                      subscriber_publishers_in_graph=[self.count_publishers(s.topic_name) for s in self.subs])
        endpoint_qos = {kind:[dict(reliability=int(x.qos_profile.reliability),
                                  history=int(x.qos_profile.history), depth=x.qos_profile.depth,
                                  durability=int(x.qos_profile.durability)) for x in endpoints]
                        for kind,endpoints in [('publishers',self.pubs),('subscribers',self.subs)]}
        graph_qos = {x.topic_name:[dict(reliability=int(info.qos_profile.reliability),
                                       history=int(info.qos_profile.history), depth=info.qos_profile.depth,
                                       durability=int(info.qos_profile.durability))
                                  for info in self.get_publishers_info_by_topic(x.topic_name)]
                     for x in self.pubs+self.subs}
        ready = all(n > 0 for values in counts.values() for n in values)
        if self.args.bulk == 'off' and self.args.role in ('bulk', 'sink'):
            ready = True
        data = dict(role=self.args.role, run_id=self.args.run_id, ready=ready, done=done,
                    counts=counts, endpoint_qos=endpoint_qos, graph_publisher_qos=graph_qos,
                    origin_ns=self.origin_ns, arm_ns=self.arm_ns,
                    monotonic_ns=now, process_cpu_ns=time.process_time_ns() - self.cpu_start_ns,
                    sent=self.sent, received=self.received, publish_calls=self.publish_calls,
                    requested_seconds=self.args.seconds, control_hz=100, bulk_hz=10,
                    bulk=self.args.bulk, bulk_reliability=self.args.reliability, bulk_depth=self.args.depth,
                    control_reliability='reliable', control_depth=10,
                    image_payload_bytes=640*360*3, cloud_payload_bytes=4096*16,
                    requested_sensor_payload_mbps=0 if self.args.bulk == 'off' else 60.53888,
                    ros_distro=os.environ.get('ROS_DISTRO'), rmw=get_rmw_implementation_identifier(),
                    domain_id=os.environ.get('ROS_DOMAIN_ID'),
                    dds_configuration=os.environ.get('CYCLONEDDS_URI'),
                    semantics='Actual ROS 2 standard topics; separate control and sensor processes; synthetic sensor content; RTT uses the controller clock only')
        p = self.paths / (self.args.role + '.json')
        temporary = p.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(data, indent=2) + '\n'); temporary.replace(p)

    def tick(self):
        now = time.monotonic_ns()
        if self.arm_ns is None:
            if not self.args.arm.exists():
                return
            self.arm_ns = now
            self.event('arm', time_ns=now)
        elapsed = now - self.arm_ns
        if elapsed >= self.args.seconds * 1e9:
            return
        if self.args.role == 'control':
            due = self.arm_ns + self.sequence * 10_000_000
            if now < due:
                return
            seq = self.sequence; self.sequence += 1
            message = UInt64MultiArray(data=[self.args.run_id, seq, due, now, 0, 0, 1, 2])
            before = time.monotonic_ns(); self.publisher.publish(message); after = time.monotonic_ns()
            self.sent += 1; self.publish_calls += 1
            self.event('command_sent', seq=seq, planned_ns=due, sent_ns=now,
                       publish_start_ns=before, publish_end_ns=after)
        elif self.args.role == 'bulk' and self.args.bulk != 'off':
            slot = int(elapsed // 100_000_000)
            if slot <= self.last_bulk_slot:
                return
            self.last_bulk_slot = slot
            for kind, message, publisher in [('image', self.image, self.image_pub),
                                             ('cloud', self.cloud, self.cloud_pub)]:
                if time.monotonic_ns() - self.arm_ns >= self.args.seconds * 1e9:
                    break
                message.header.frame_id = f'c5:{self.args.run_id}:{slot}'
                message.header.stamp = self.get_clock().now().to_msg()
                before = time.monotonic_ns(); publisher.publish(message); after = time.monotonic_ns()
                self.sent += 1; self.publish_calls += 1
                self.event('sensor_published', topic=kind, seq=slot,
                           planned_ns=self.arm_ns+slot*100_000_000,
                           publish_start_ns=before, publish_end_ns=after,
                           payload_bytes=len(message.data))

    def echo(self, message):
        received = time.monotonic_ns()
        if len(message.data) != 8 or message.data[0] != self.args.run_id:
            return
        self.received += 1
        seq = int(message.data[1]); message.data[4] = received
        before = time.monotonic_ns(); message.data[5] = before
        self.publisher.publish(message); after = time.monotonic_ns()
        self.sent += 1; self.publish_calls += 1
        self.event('command_echoed', seq=seq, received_ns=received,
                   publish_start_ns=before, publish_end_ns=after)

    def response(self, message):
        now = time.monotonic_ns()
        if len(message.data) != 8 or message.data[0] != self.args.run_id:
            return
        self.received += 1
        self.event('response_received', seq=int(message.data[1]), received_ns=now,
                   command_sent_ns=int(message.data[3]),
                   echo_pre_publish_ns=int(message.data[5])-int(message.data[4]))

    def sensor_received(self, message, topic):
        now = time.monotonic_ns()
        parts = message.header.frame_id.split(':')
        if len(parts) != 3 or parts[0] != 'c5' or int(parts[1]) != self.args.run_id:
            return
        self.received += 1
        self.event('sensor_received', topic=topic, seq=int(parts[2]), received_ns=now,
                   payload_bytes=len(message.data))

    def image_received(self, message):
        self.sensor_received(message, 'image')

    def cloud_received(self, message):
        self.sensor_received(message, 'cloud')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('role', choices=['control', 'echo', 'bulk', 'sink'])
    p.add_argument('--run-id', type=int, required=True)
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--bulk', choices=['off', 'heavy'], default='heavy')
    p.add_argument('--reliability', choices=['reliable', 'best_effort'], default='best_effort')
    p.add_argument('--depth', type=int, choices=[1, 10], default=1)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--arm', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=100)
    args = p.parse_args()
    assert 0 < args.seconds <= 600 and args.timeout > args.seconds+1
    rclpy.init(); node = None; deadline = time.monotonic()+args.timeout
    try:
        node = Probe(args)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.01)
            if node.arm_ns is not None and time.monotonic_ns()-node.arm_ns >= (args.seconds+2)*1e9:
                break
        if node.arm_ns is None:
            raise RuntimeError('ROS 2 role was never armed before timeout')
        node.status(done=True)
    finally:
        if node is not None:
            node.trace.flush(); node.trace.close(); node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
