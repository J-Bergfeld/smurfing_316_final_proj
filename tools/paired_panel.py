"""Screen frozen Python builds on common seeds and confirm one on a disjoint panel."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import statistics
import time

from baseline import prepare, run_seed
from experiment import compare, summarize
from match_telemetry import fingerprint


def build_id(manifest):
    return fingerprint([manifest['bot']['commit'], manifest['snapshot']['bot'], manifest['config_sha256']])


def run(args):
    spec = json.loads(args.spec.read_text())
    names = list(spec)
    if names not in (['A','B'], ['A','B','C']):
        raise ValueError('spec needs ordered candidates A, B and optionally C')
    if args.confirm and len(names) != 2:
        raise ValueError('confirmation needs two candidates')
    if args.offset < 0 or args.seeds < 1 or args.offset+args.seeds > 1000:
        raise ValueError('seed range must fit the 1000-seed panel')
    start = (423000 if args.confirm else 422000)+args.offset
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifests = {}
    ids = {}
    for name, item in spec.items():
        env = item.get('env', {})
        if not all(k.startswith('BOT_') and k.isidentifier() and isinstance(v,str) for k,v in env.items()):
            raise ValueError('candidate overrides must be string-valued BOT_ settings')
        bot = (args.spec.parent/item['root']).resolve(strict=True)
        m = prepare(out/name, args.sim.resolve(strict=True), bot, env, start, args.seeds)
        manifests[name] = m
        ids[name] = build_id(m)
    def context(m):
        return {k:m['snapshot'][k] for k in ('sim','kit','tools')}
    field = context(manifests['A'])
    if any(context(m) != field for m in manifests.values()):
        raise ValueError('simulator, kit or runner changed during setup')
    if args.confirm:
        screen = json.loads(args.confirm.read_text())
        if (screen['stage'] != 'screen' or screen['context'] != field or ids['A'] != screen['builds']['A']
                or ids['B'] not in [v for k,v in screen['builds'].items() if k != 'A']):
            raise ValueError('confirm the same screened baseline, challenger and proxy')
    lib = out/'geometry.so'
    compile_start = time.perf_counter()
    subprocess.run(['cc','-O3','-shared','-fPIC',str(out/'A/inputs/sim/local_sim/geometry.c'),'-lm','-o',str(lib)],
                   check=True)
    rows = {n:[] for n in names}
    report = dict(stage='confirm' if args.confirm else 'screen', builds=ids, context=field, spec=spec,
                  seed_start=start, seeds=args.seeds, compile_seconds=time.perf_counter()-compile_start,
                  geometry_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),
                  parent_report_sha256=hashlib.sha256(args.confirm.read_bytes()).hexdigest() if args.confirm else None)
    for i,seed in enumerate(range(start, start+args.seeds)):
        # Counterbalance order while keeping one deadline-sensitive match active.
        shift = i % len(names)
        for name in names[shift:]+names[:shift]:
            row = run_seed(out/name, manifests[name], seed, lib)
            rows[name].append(row)
            print(name,seed,row['points'],flush=True)
    report['summaries'] = {n:summarize(v) for n,v in rows.items()}
    pairs = [('B','A')]
    if 'C' in rows:
        pairs += [('C','A'),('B','C')]
    report['comparisons'] = {x+'-'+y:compare(rows[y],rows[x]) for x,y in pairs}
    for x, y in pairs:
        # Rows are in ascending seed order for every candidate despite rotated execution.
        common = zip(rows[x], rows[y])
        differences = [(a['kills']-b['kills'], a['game_seconds']-b['game_seconds'],
                        a['terminal']['cubes']-b['terminal']['cubes'],
                        sum(a['incoming_damage'].values())-sum(b['incoming_damage'].values()))
                       for a,b in common]
        metrics = ('kills','game_seconds','terminal_cubes','incoming_damage')
        report['comparisons'][x+'-'+y]['mean_metric_deltas'] = dict(zip(metrics,map(statistics.mean,zip(*differences))))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'registry.jsonl').open('x') as stream:
        for n in names:
            record = dict(label=n, build_id=ids[n], commit=manifests[n]['bot']['commit'],
                          parent=ids['A'], manifest=n+'/manifest.json', hypothesis=spec[n].get('hypothesis'),
                          stage=report['stage'], results='report.json', panel_start=start, seeds=args.seeds)
            stream.write(json.dumps(record)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--sim', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--confirm', type=Path, help='screen report for the selected A/B builds')
    parser.add_argument('--offset', default=0, type=int)
    parser.add_argument('--seeds', type=int, help='Number of paired seeds (confirmation default: 12; required for screening)')
    args = parser.parse_args()
    if args.seeds is None:
        if not args.confirm:
            parser.error('--seeds is required for screening')
        args.seeds = 12
    try:
        run(args)
    except ValueError as exc:
        parser.error(str(exc))
