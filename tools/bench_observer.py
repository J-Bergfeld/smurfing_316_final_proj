"""Compare recording cost on identical, predecoded observations (excludes simulation)."""
import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time
from types import SimpleNamespace
from match_telemetry import Observer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    args = parser.parse_args()
    with args.trace.open() as stream:
        steps = [r for r in map(json.loads, stream) if r['type']=='step']
    phases = {end:i for i,end in enumerate(dict.fromkeys(s['obs']['zone']['shrink_end'] for s in steps))}
    dummy = SimpleNamespace(subject=0, order=[], zone_phases=[], players=[], crates={}, pickups={},
                            npcs={}, npc_cd={}, drop_plan=[])
    times = {k:[] for k in ('off','compact','full')}
    sizes = {}
    for order in (list(times), list(reversed(times)))*3:
        for mode in order:
            with tempfile.TemporaryFile('w+') as f:
                observer = Observer(f,dummy)
                start = time.perf_counter()
                for row in steps:
                    obs = row['obs']
                    if mode == 'compact':
                        observer.step(obs,row['action'],phases[obs['zone']['shrink_end']])
                    elif mode == 'full':
                        f.write(json.dumps(row,separators=(',', ':'))+'\n')
                f.flush()
                times[mode].append(time.perf_counter()-start)
                sizes[mode]=f.tell()
    print(json.dumps({'steps':len(steps),'median_seconds':{k:statistics.median(v) for k,v in times.items()},
                      'bytes':sizes}))


if __name__ == '__main__':
    main()
