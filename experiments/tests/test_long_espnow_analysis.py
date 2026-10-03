"""Separate scheduler skips, API failures, missing replies and stale replies."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_long_espnow import summarize_events


class TimelineTests(unittest.TestCase):
    def trace(self):
        return np.array([[1, 0, 0, 0], [2, 0, 10000, 0], [2, 0, 15000, 0],
                         [1, 1, 50500, 0], [1, 2, 100000, 0],
                         [3, 3, 200000, 1], [1, 4, 200000, 0], [2, 4, 210000, 200000],
                         [1, 5, 250000, 1], [2, 1, 900000, 50500],
                         [3, 6, 1000000, 14], [4, 20, 3000000, 37]], dtype=np.uint32)

    def test_scheduling_and_delivery_are_distinct(self):
        arrays, metrics, timeline = summarize_events(self.trace(), 20, 1)
        self.assertEqual((metrics['planned'], metrics['send_calls'], metrics['unsent_planned']), (20, 5, 15))
        self.assertEqual((metrics['api_errors'], metrics['api_accepted_without_reply']), (1, 1))
        self.assertEqual((metrics['unique_replies'], metrics['duplicate_replies']), (3, 1))
        self.assertEqual(metrics['planned_deadline20_pct'], 90)
        self.assertEqual(metrics['called_deadline20_pct'], 60)
        self.assertEqual(metrics['longest_missing_reply_run'], 15)
        self.assertEqual(metrics['maximum_reply_gap_ms'], 690)
        self.assertEqual(metrics['maximum_increasing_sequence_gap_ms'], 790)
        self.assertEqual(metrics['out_of_order_first_replies'], 1)
        self.assertEqual(arrays['received_ns'][0], 10_000_000)
        self.assertEqual(arrays['received_ns'][3], -1)
        self.assertEqual(timeline[0]['planned'], 20)

    def test_missing_uart_skip_is_rejected(self):
        trace = self.trace(); trace = trace[~((trace[:, 0] == 3) & (trace[:, 1] == 3))]
        with self.assertRaisesRegex(AssertionError, 'Missing UART events'):
            summarize_events(trace, 20, 1)

    def test_foreign_sender_timestamp_is_rejected(self):
        trace = self.trace(); trace[1, 3] = 1
        with self.assertRaises(AssertionError):
            summarize_events(trace, 20, 1)

    def test_short_placement_window_keeps_grace_and_skipped_slots_distinct(self):
        # One scheduling skip, one absent response, and a response in the
        # post-window grace period must remain different observations.
        events = []
        for sequence in range(1000):
            when = sequence*10000
            if sequence == 998:
                events.append([3, sequence, when, 1]); continue
            events.append([1, sequence, when, 0])
            if sequence != 999:
                reply = 10040000 if sequence == 997 else when+1000
                events.append([2, sequence, reply, when])
        events.append([4, 1000, 12000000, 37])
        trace = np.array(sorted(events, key=lambda event: (event[2], event[0])), dtype=np.uint32)
        _, metrics, timeline = summarize_events(trace, 100, 10)
        self.assertEqual((metrics['planned'], metrics['send_calls'], metrics['unique_replies']), (1000, 999, 998))
        self.assertEqual(metrics['unsent_planned'], 1)
        self.assertEqual(metrics['api_accepted_without_reply'], 1)
        self.assertAlmostEqual(metrics['planned_deadline20_pct'], .3)
        self.assertEqual(metrics['longest_missing_reply_run'], 2)
        self.assertEqual(metrics['maximum_increasing_sequence_gap_ms'], 39)
        self.assertEqual(len(timeline), 1)
        self.assertEqual((timeline[0]['start_s'], timeline[0]['end_s'], timeline[0]['planned']), (0, 10, 1000))


if __name__ == '__main__':
    unittest.main()
