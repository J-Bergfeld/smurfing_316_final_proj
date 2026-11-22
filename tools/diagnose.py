"""Evaluate transparent terminal-window hypotheses on a complete frozen squad panel."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import statistics


def bootstrap_mean(values):
    rng = random.Random(711)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(4000))
    return [means[99], means[3899]]


def diagnose(window, terminal, low_hp, attackers, subject=None):
    if terminal['alive']:
        return {}
    damage = [r['event'] for r in window if r['kind'] == 'event' and r['event']['type'] == 'damaged']
    sources = {e['by'] for e in damage if e.get('by') is not None and 0 <= e['by'] < 16 and e['by'] != subject}
    samples = [r for r in window if r['kind'] == 'sample']
    tags = {}
    if len(sources) >= attackers:
        tags['multi_attacker_pressure'] = dict(source_ids=sorted(sources))
    if terminal['fatal_weapon'] == 'zone':
        tags['zone_elimination'] = dict(weapon='zone')
    trigger_ticks = [r['tick'] for r in samples if r['hp'] <= low_hp*r['max_hp'] and any(r['fire'] or [])]
    if trigger_ticks:
        tags['low_hp_trigger'] = dict(sample_ticks=trigger_ticks)
    # One-second samples. Count only consecutive pairs with sustained endpoint commands.
    stationary = [b['tick'] for a,b in zip(samples, samples[1:])
                  if b['tick']-a['tick'] == 20 and math.hypot(*(a['move'] or [0,0])) >= .8
                  and math.hypot(*(b['move'] or [0,0])) >= .8 and math.dist(a['pos'][:2], b['pos'][:2]) < .5]
    if stationary:
        tags['possible_stall'] = dict(sample_ticks=stationary)
    return tags or {'unknown': {}}


def panel(directory, seconds=5., low_hp=.35, attackers=2):
    manifest = json.loads((directory/'manifest.json').read_text())
    rows = []
    for seed in range(manifest['seed_start'], manifest['seed_start']+manifest['seeds']):
        row = json.loads((directory/f'{seed}.json').read_text())
        if row['seed'] != seed or not 1 <= row['place'] <= 16 or row['points'] != 16-row['place']:
            raise ValueError(f'invalid score or seed: {seed}')
        end = row['game_seconds']
        with (directory/row['evidence']).open() as stream:
            window = [event for event in map(json.loads, stream) if event['t'] >= end-seconds]
        if window[-1]['kind'] != 'end':
            raise ValueError(f'incomplete evidence for {seed}')
        # The pinned v1 simulator draws the subject slot first. Later summaries store it.
        subject = row.get('subject', random.Random(seed).randrange(16))
        rows.append(dict(**row, window_start=max(0,end-seconds), window=window,
                         tags=diagnose(window, row['terminal'], low_hp, attackers, subject)))
    scores = [r['points'] for r in rows]
    phases = defaultdict(list)
    for r in rows:
        phases[r['terminal']['phase']].append(r['points'])
    return dict(manifest=manifest, thresholds=dict(window_seconds=seconds, low_hp_fraction=low_hp,
                distinct_mech_sources=attackers), n=len(rows), mean=statistics.mean(scores),
                median=statistics.median(scores), sd=statistics.stdev(scores) if len(scores)>1 else None,
                bootstrap95=bootstrap_mean(scores), score_distribution=Counter(scores),
                terminal_causes=Counter((r['terminal']['fatal_weapon'] or 'unattributed') if not r['terminal']['alive']
                                        else 'survived' for r in rows),
                tags=Counter(tag for r in rows for tag in r['tags']),
                phase_points={p:dict(n=len(v),mean=statistics.mean(v)) for p,v in phases.items()},
                matches=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--window', type=float, default=5)
    parser.add_argument('--low-hp', type=float, default=.35)
    parser.add_argument('--attackers', type=int, default=2)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.window <= 0 or not 0 <= args.low_hp <= 1 or args.attackers < 1:
        parser.error('invalid diagnosis thresholds')
    report = panel(args.directory, args.window, args.low_hp, args.attackers)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('matches','manifest')}, indent=2))


if __name__ == '__main__':
    main()
