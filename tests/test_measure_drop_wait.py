import json
import tempfile
import unittest
from pathlib import Path

from tools.measure_drop_wait import measure


class DropWaitTests(unittest.TestCase):
    def test_wait_stops_at_landing_and_missing_observations_are_skipped(self):
        def step(t, lands, x):
            return {'type': 'step', 'obs': {'t': t, 'self': {'pos': [x, 0, 0]},
                'drops': [{'id': 20, 'pos': [0, 0, 0], 'radius': 8, 'lands_in': lands}],
                'events': []}}
        records = [step(1., .15, 0), step(1.1, .05, 0), step(1.2, 0., 0),
                   step(2., 1., 0), step(2.1, .9, 20),
                   {'type': 'end', 'events': [{'type': 'drop', 'id': 20}]}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            path.write_text(''.join(json.dumps(record) + '\n' for record in records))
            result = measure(path)
        self.assertEqual(result['prelanding_seconds_in_ring'], .25)
        self.assertEqual(result['observed_captures'], [20])


if __name__ == '__main__':
    unittest.main()
