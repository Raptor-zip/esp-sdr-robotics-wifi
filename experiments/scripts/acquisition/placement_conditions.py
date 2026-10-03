"""Validate reported physical configurations before opening any device."""
import json
import math
from pathlib import Path

PLACEMENT_IDS = ('baseline-before', 'rotated', 'obstructed', 'farther', 'baseline-after')


def validate_fields(value):
    assert value['id'] in PLACEMENT_IDS
    assert value['source'] == 'user report'
    assert value['distance_reference'] == 'board-or-case-centres'
    assert value['fixed_devices_unchanged'] is True
    for key in ('sender_orientation', 'echo_baseline_orientation'):
        assert isinstance(value[key], str) and value[key].strip()
    if 'distance_note' in value:
        assert isinstance(value['distance_note'], str) and value['distance_note'].strip()
    distances = value['distances_cm']
    assert set(distances) == {'sender_echo', 'c5_sender', 'c5_echo'}
    for distance in distances.values():
        assert isinstance(distance, (int, float)) and not isinstance(distance, bool)
        assert math.isfinite(distance) and distance > 0
    assert type(value['echo_rotation_degrees']) is int
    assert value['echo_rotation_degrees'] == (90 if value['id'] == 'rotated' else 0)
    obstruction = value['body_obstruction']
    assert obstruction['kind'] in ('none', 'hand', 'body')
    assert obstruction['between_sender_and_echo'] is (value['id'] == 'obstructed')
    assert (obstruction['kind'] != 'none') is (value['id'] == 'obstructed')
    return value


def load_placement(path):
    value = json.loads(Path(path).read_text())
    assert value['configuration_applied'] is True, 'Physical configuration is not confirmed'
    assert isinstance(value['confirmation'], str) and value['confirmation'].strip(), 'Keep the user confirmation in the private input'
    public = {key: value[key] for key in ('id', 'source', 'distance_reference', 'fixed_devices_unchanged',
                                        'distances_cm', 'sender_orientation', 'echo_baseline_orientation',
                                        'echo_rotation_degrees', 'body_obstruction')}
    if 'distance_note' in value:
        public['distance_note'] = value['distance_note']
    return validate_fields(public)
