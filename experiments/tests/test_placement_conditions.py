"""Reject unconfirmed/invalid geometry before a radio is opened."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/acquisition'))
from placement_conditions import load_placement, validate_fields


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.value = dict(id='baseline-before', source='user report',
            distance_reference='board-or-case-centres', fixed_devices_unchanged=True,
            distances_cm=dict(sender_echo=30, c5_sender=30, c5_echo=30),
            sender_orientation='Synthetic test pose', echo_baseline_orientation='Synthetic test pose',
            echo_rotation_degrees=0, body_obstruction=dict(kind='none', between_sender_and_echo=False),
            configuration_applied=True, confirmation='Synthetic test confirmation, not a physical measurement')

    def load(self, value):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'input.json'; path.write_text(json.dumps(value))
            return load_placement(path)

    def test_private_confirmation_is_required_but_not_published(self):
        result = self.load(self.value)
        self.assertNotIn('confirmation', result)
        self.assertNotIn('configuration_applied', result)
        value = deepcopy(self.value); value['configuration_applied'] = False
        with self.assertRaisesRegex(AssertionError, 'not confirmed'):
            self.load(value)
        value['configuration_applied'] = True; value['confirmation'] = ''
        with self.assertRaisesRegex(AssertionError, 'confirmation'):
            self.load(value)

    def test_bad_or_missing_distance_is_rejected(self):
        for distance in (True, 0, -30, float('nan'), float('inf'), None):
            with self.subTest(distance=distance):
                value = deepcopy(self.value); value['distances_cm']['sender_echo'] = distance
                with self.assertRaises(AssertionError):
                    self.load(value)
        value = deepcopy(self.value); value['distances_cm'].pop('c5_echo')
        with self.assertRaises(AssertionError):
            self.load(value)

    def test_only_recorded_orientation_and_obstruction_are_accepted(self):
        value = deepcopy(self.value); value['id'] = 'rotated'
        with self.assertRaises(AssertionError):
            validate_fields(value)
        value['echo_rotation_degrees'] = 90
        self.assertEqual(validate_fields(value)['echo_rotation_degrees'], 90)
        value = deepcopy(self.value); value['id'] = 'obstructed'
        with self.assertRaises(AssertionError):
            validate_fields(value)
        value['body_obstruction'] = dict(kind='hand', between_sender_and_echo=True)
        self.assertEqual(validate_fields(value)['body_obstruction']['kind'], 'hand')


if __name__ == '__main__':
    unittest.main()
