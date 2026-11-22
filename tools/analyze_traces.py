"""Summarize local runner traces without inferring unseen shots or line of sight."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics


def summarize(directory):
    rows = []
    for result_path in sorted(directory.glob('*.result.json')):
        if not result_path.stat().st_size:
            continue
        result = json.loads(result_path.read_text())
        prefix = result_path.name.removesuffix('.result.json')
        steps = []
        with (directory / (prefix + '.trace.jsonl')).open() as stream:
            for line in stream:
                record = json.loads(line)
                if record.get('type') == 'step':
                    steps.append(record)
        events = [json.loads(line) for line in (directory / (prefix + '.events.jsonl')).open()]
        damage = [r for r in events if r['kind'] == 'event' and r['event']['type'] == 'damaged']
        terminal_damage = [r['event'] for r in damage if r['t'] >= result['game_seconds'] - 5]
        attackers = {e['by'] for e in terminal_damage if e.get('by') is not None
                     and 0 <= e['by'] < 16 and e['by'] != result['subject']}
        samples = [r for r in events if r['kind'] == 'sample']
        stalls = sum(1 for a, b in zip(samples, samples[1:])
                     if b['tick'] - a['tick'] == 20
                     and math.hypot(*(a['move'] or [0, 0])) >= .8
                     and math.hypot(*(b['move'] or [0, 0])) >= .8
                     and math.dist(a['pos'][:2], b['pos'][:2]) < .5)
        listed = [s for s in steps if any(m['kind'] == 'mech' for m in s['obs']['mechs'])]
        ready = [s for s in listed if any(w and w['kind'] == 'gun' and w['ammo'] > 0
                                         and w['reload'] <= 0 and w['cooldown'] <= 0
                                         for w in s['obs']['self']['weapons'])]
        untriggered = sum(not any(s['action'].get('fire', [])) for s in ready)
        rows.append(dict(seed=result['seed'], points=result['points'], kills=result['kills'],
                         seconds=result['game_seconds'], late=result['late'], invalid=result['invalid'],
                         fatal_weapon=result['terminal']['fatal_weapon'],
                         terminal_attackers=len(attackers), possible_stall_seconds=stalls,
                         steps=len(steps), listed_mech_steps=len(listed), ready_gun_listed_steps=len(ready),
                         ready_gun_listed_no_trigger=untriggered,
                         incoming_damage=result['incoming_damage']))
    if not rows:
        raise ValueError('No completed matches')
    mean = lambda k: statistics.mean(r[k] for r in rows)
    return dict(matches=len(rows), mean_points=mean('points'), mean_kills=mean('kills'),
                mean_seconds=mean('seconds'), late=sum(r['late'] for r in rows),
                invalid=sum(r['invalid'] for r in rows),
                fatal_weapons=dict(Counter(r['fatal_weapon'] for r in rows)),
                terminal_multiple_attackers=sum(r['terminal_attackers'] >= 2 for r in rows),
                matches_possible_stall=sum(r['possible_stall_seconds'] > 0 for r in rows),
                listed_mech_steps=sum(r['listed_mech_steps'] for r in rows),
                ready_gun_listed_steps=sum(r['ready_gun_listed_steps'] for r in rows),
                ready_gun_listed_no_trigger=sum(r['ready_gun_listed_no_trigger'] for r in rows),
                rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    output = json.dumps(summarize(args.directory), indent=2) + '\n'
    if args.out:
        args.out.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
