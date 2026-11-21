"""Summarize movement and opt-in gun diagnostics in a local JSONL trace."""
import argparse
from collections import Counter
import json
import math

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('trace')
parser.add_argument('--from-t', type=float, default=float('-inf'))
parser.add_argument('--to-t', type=float, default=float('inf'))
args = parser.parse_args()
reasons = Counter()
movement = Counter()
with open(args.trace, encoding='utf-8') as trace:
    for line in trace:
        record = json.loads(line)
        if record.get('type') != 'step': continue
        obs, action = record['obs'], record['action']
        if not args.from_t <= obs['t'] <= args.to_t: continue
        label = action.get('debug', {}).get('label', '')
        if ' gun=' in label:
            fields = dict(field.split('=', 1) for field in label.split() if '=' in field)
            if fields.get('target') != 'none': reasons[fields['gun']] += 1
            if fields.get('peek') == '1': movement['laser_peek_decisions'] += 1
        p = obs['self']['pos']
        if any(e['kind']=='mech' and math.dist(p[:2],e['pos'][:2])<140 for e in obs.get('mechs',[])):
            movement['observations'] += 1
            if math.hypot(*action.get('move',[0,0])) > .1: movement['commanded_move'] += 1
            if math.hypot(*obs['self']['vel'][:2]) > 1: movement['moving'] += 1
            if action.get('boost'): movement['boosting'] += 1
print(json.dumps({'gun_reasons':reasons, 'nearby_enemy_movement':movement}, indent=2))
