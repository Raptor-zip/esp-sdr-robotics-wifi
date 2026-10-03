"""Synthetic clock/loss cases; these are not physical experiment results."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_ros2 import summarize_control, summarize_sensors


class ClockAndLossTests(unittest.TestCase):
    def test_unsent_lost_duplicate_and_grace(self):
        arm = 1_000_000_000
        trace = [dict(kind='command_sent', seq=seq, planned_ns=arm+seq*10_000_000,
                      sent_ns=arm+seq*10_000_000, publish_start_ns=arm+seq*10_000_000,
                      publish_end_ns=arm+seq*10_000_000+1_000_000) for seq in range(3)]
        for seq, received_ms in [(0, 5), (1, 40), (1, 45)]:
            trace.append(dict(kind='response_received', seq=seq, received_ns=arm+received_ms*1_000_000,
                              command_sent_ns=arm+seq*10_000_000, echo_pre_publish_ns=1000))
        arrays, result = summarize_control(trace, dict(arm_ns=arm), 1)
        self.assertEqual((result['planned'], result['published'], result['unsent_planned']), (100, 3, 97))
        self.assertEqual((result['unique_responses'], result['duplicate_responses'], result['lost_published']), (2, 1, 1))
        self.assertEqual(result['planned_deadline20_pct'], 99)
        self.assertAlmostEqual(result['published_deadline20_pct'], 200/3)
        self.assertEqual(result['maximum_response_gap_ms'], 960)
        self.assertEqual(result['longest_planned_deadline20_run'], 99)
        self.assertEqual(arrays['received_ns'][1], 40_000_000)
        self.assertEqual(arrays['received_ns'][2], -1)

    def test_sensor_clocks_and_window_edges(self):
        source_arm = 90_000_000_000; sink_arm = 20_000_000_000
        source = [dict(kind='sensor_published', topic='image', seq=seq,
                       planned_ns=source_arm+seq*100_000_000,
                       publish_start_ns=source_arm+seq*100_000_000,
                       publish_end_ns=source_arm+seq*100_000_000+2_000_000,
                       payload_bytes=691200) for seq in (0, 2)]
        sink = [dict(kind='sensor_received', topic='image', seq=seq,
                     received_ns=sink_arm+offset, payload_bytes=691200)
                for seq, offset in [(0, 100_000_000), (0, 110_000_000), (2, 1_500_000_000)]]
        arrays, result = summarize_sensors(source, sink, dict(bulk=dict(arm_ns=source_arm), sink=dict(arm_ns=sink_arm)), 1)
        image = result['image']
        self.assertEqual((image['published'], image['received_callbacks'], image['unique_received']), (2, 3, 2))
        self.assertEqual(image['received_within_window'], 1)
        self.assertEqual(image['maximum_update_gap_ms'], 900)
        self.assertAlmostEqual(image['delivered_payload_mbps'], 5.5296)
        self.assertEqual(image['publication_p99_ms'], 2)
        self.assertEqual(list(arrays['image_received_ns']), [100_000_000, 110_000_000, 1_500_000_000])
        self.assertEqual(result['cloud']['maximum_update_gap_ms'], 1000)


if __name__ == '__main__':
    unittest.main()
