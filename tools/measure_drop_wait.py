"""Measure pre-landing time inside drop rings from local match traces."""
import argparse
import json
import math
from pathlib import Path


def measure(path):
    rows = []
    captures = set()
    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            if record.get('type') == 'step':
                rows.append(record['obs'])
                for event in record['obs'].get('events', []):
                    if event.get('type') == 'drop':
                        captures.add(event['id'])
            elif record.get('type') == 'end':
                for event in record.get('events', []):
                    if event.get('type') == 'drop':
                        captures.add(event['id'])
    waits = {}
    for obs, following in zip(rows, rows[1:]):
        dt = following['t'] - obs['t']
        # Do not infer waiting across missing observations.
        if dt <= 0 or dt > .2:
            continue
        pos = obs['self']['pos']
        for drop in obs.get('drops', []):
            landing = drop['lands_in']
            if landing > 0 and math.dist(pos[:2], drop['pos'][:2]) <= drop['radius']:
                waits[drop['id']] = waits.get(drop['id'], 0.) + min(dt, landing)
    return {'trace': str(path), 'prelanding_seconds_in_ring': round(sum(waits.values()), 3),
            'wait_seconds_by_drop': {str(k): round(v, 3) for k, v in sorted(waits.items())},
            'observed_captures': sorted(captures), 'observations': len(rows)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps([measure(path) for path in args.traces], indent=2))
