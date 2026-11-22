"""Extract and replay a fixed observation window against the current submission policy."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check.check import Schema
from main import Bot


def capture(args):
    with args.trace.open() as stream:
        observations = [r['obs'] for r in map(json.loads,stream)
                        if r['type']=='step' and args.tick <= r['obs']['tick'] < args.tick+2*args.steps]
    if len(observations) != args.steps or [o['tick'] for o in observations] != list(range(args.tick,args.tick+2*args.steps,2)):
        raise ValueError('trace must contain the entire contiguous observation window')
    fixture = dict(version=1, match_seed=args.seed, start_tick=args.tick, field='local squad proxy',
                   trace_sha256=hashlib.sha256(args.trace.read_bytes()).hexdigest(), observations=observations)
    with args.out.open('xb') as f:
        f.write(gzip.compress(json.dumps(fixture,separators=(',', ':')).encode(),mtime=0))


def replay(path):
    with gzip.open(path,'rt') as stream:
        fixture = json.load(stream)
    obs = fixture['observations']
    with gzip.open(ROOT/'check/stream.jsonl.gz','rt') as stream:
        hello = json.loads(next(stream))
    slot = obs[0]['self']['id']
    hello.update(slot=slot, seed=(slot+1)*1779033703 % 2**32)
    hello['map']['dir'] = str(ROOT/'arena')
    bot = Bot(hello)
    schema = Schema(ROOT/'mechfight.schema.json')
    modes = Counter()
    triggers = low_hp_triggers = boost_steps = 0
    start = time.perf_counter()
    for o in obs:
        action = bot.act(o)
        if action.get('tick') != o['tick'] or schema.errors(action,'Action'):
            raise ValueError(f"invalid action at tick {o['tick']}")
        json.dumps(action,allow_nan=False)
        modes[getattr(bot.strategy,'mode','unreported')] += 1
        boost_steps += bool(action.get('boost'))
        fired = any(action.get('fire',[]))
        triggers += fired
        low_hp_triggers += fired and o['self']['hp'] <= .35*o['self']['max_hp']
    print(json.dumps(dict(fixture=path.name, seed=fixture['match_seed'], steps=len(obs), modes=modes,
                          trigger_steps=triggers, low_hp_trigger_steps=low_hp_triggers, boost_steps=boost_steps,
                          decision_loop_seconds=time.perf_counter()-start)))


def run_fixtures(fixtures, timeout, jobs):
    def run_worker(fixture):
        result = subprocess.run([sys.executable, __file__, 'worker', str(fixture)],
                                timeout=timeout, check=True, stdout=subprocess.PIPE, text=True)
        return result.stdout

    with ThreadPoolExecutor(max_workers=min(jobs, len(fixtures))) as workers:
        for output in workers.map(run_worker, fixtures):
            print(output, end='', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    extract = commands.add_parser('capture')
    extract.add_argument('trace',type=Path)
    for name in ('seed','tick','steps'):
        extract.add_argument('--'+name,type=int,required=True)
    extract.add_argument('--out',type=Path,required=True)
    run = commands.add_parser('run')
    run.add_argument('fixtures',nargs='+',type=Path)
    run.add_argument('--timeout',type=float,default=10)
    run.add_argument('--jobs', type=int, default=1, help='Concurrent isolated replay workers')
    worker = commands.add_parser('worker')
    worker.add_argument('fixture',type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        if args.steps < 1:
            parser.error('positive window length required')
        capture(args)
    elif args.command == 'run':
        if args.jobs < 1 or args.timeout <= 0:
            parser.error('jobs and timeout must be positive')
        run_fixtures(args.fixtures, args.timeout, args.jobs)
    else:
        replay(args.fixture)
