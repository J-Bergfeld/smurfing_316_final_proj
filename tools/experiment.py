"""Paired squad/FFA experiments against a local simulator checkout."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools/run_local_match.py'


def factors(values):
    names, levels = [], []
    for value in values:
        name, sep, options = value.partition('=')
        choices = options.split(',')
        if not sep or not name.isidentifier() or not choices or any(not x for x in choices):
            raise ValueError('factor must be NAME=value1,value2')
        if name in names:
            raise ValueError('duplicate factor: ' + name)
        names.append(name)
        levels.append(choices)
    return [dict(zip(names, combination)) for combination in itertools.product(*levels)] or [{}]


def provenance(bot):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    diff = subprocess.check_output(['git', 'diff', 'HEAD', '--binary'], cwd=ROOT)
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    digest = hashlib.sha256()
    files = [bot] + sorted((bot.parent/'bot').glob('*.py')) if (bot.parent/'bot').is_dir() else [bot]
    if (bot.parent/'mechfight.py').is_file(): files.append(bot.parent/'mechfight.py')
    for path in files:
        digest.update(str(path.relative_to(bot.parent)).encode()+b'\0'+path.read_bytes())
    return {'commit': commit, 'dirty': dirty, 'diff_sha256': hashlib.sha256(diff).hexdigest() if diff else None,
            'bot_sha256': digest.hexdigest()}


def verify_revision(bot, revision):
    """Confirm the external checkout's Python runtime matches a local commit."""
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', revision+'^{commit}'], cwd=ROOT, text=True).strip()
    tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, '--', 'main.py', 'mechfight.py', 'bot/'], cwd=ROOT, text=True).splitlines()
    files = [name for name in tracked if name.endswith('.py')]
    if bot.name != 'main.py' or 'main.py' not in files:
        raise ValueError('revision verification requires the root main.py')
    actual = {'main.py', *(str(p.relative_to(bot.parent)) for p in (bot.parent/'bot').glob('*.py'))}
    if (bot.parent/'mechfight.py').is_file(): actual.add('mechfight.py')
    if actual != set(files): raise ValueError('bot runtime files do not match the revision')
    for name in files:
        expected = subprocess.check_output(['git', 'show', commit+':'+name], cwd=ROOT)
        if (bot.parent/name).read_bytes() != expected:
            raise ValueError('bot file differs from revision: '+name)
    return commit


def summarize(rows):
    points = [row['points'] for row in rows]
    return {'mean': statistics.mean(points), 'matches': len(points),
            'kills': statistics.mean(row['kills'] for row in rows),
            'survival_s': statistics.mean(row['game_seconds'] for row in rows),
            'late': sum(row['late'] for row in rows), 'invalid': sum(row['invalid'] for row in rows)}


def compare(base, candidate):
    b = {r['seed']: r['points'] for r in base}
    c = {r['seed']: r['points'] for r in candidate}
    if b.keys() != c.keys():
        raise ValueError('paired variants must have identical seeds')
    diffs = [c[seed]-b[seed] for seed in sorted(b)]
    sem = statistics.stdev(diffs)/math.sqrt(len(diffs)) if len(diffs) > 1 else None
    return {'delta': statistics.mean(diffs), 'se': sem, 'pairs': len(diffs)}


def interactions(variants):
    if not variants: return []
    names = list(variants[0]['factors'])
    levels = {name: list(dict.fromkeys(v['factors'][name] for v in variants)) for name in names}
    if len(names) != 2 or any(len(levels[n]) != 2 for n in names): return []
    a, b = names
    lookup = {(v['factors'][a], v['factors'][b]): {r['seed']:r['points'] for r in v['matches']} for v in variants}
    a0,a1=levels[a]; b0,b1=levels[b]
    cells = [lookup[(a0,b0)],lookup[(a1,b0)],lookup[(a0,b1)],lookup[(a1,b1)]]
    seeds = set(cells[0])
    if any(set(cell) != seeds for cell in cells): raise ValueError('factorial seeds differ')
    diffs = [cells[3][s]-cells[2][s]-cells[1][s]+cells[0][s] for s in sorted(seeds)]
    return [{'factors':[a,b], 'contrast':'difference of differences', 'delta':statistics.mean(diffs),
             'se':statistics.stdev(diffs)/math.sqrt(len(diffs)) if len(diffs)>1 else None, 'pairs':len(diffs)}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim', type=Path, required=True, help='Checkout containing local_sim')
    parser.add_argument('--bot', type=Path, default=ROOT/'main.py')
    parser.add_argument('--bot-revision', help='Verify the bot runtime matches this local Git revision')
    parser.add_argument('--factor', action='append', default=[], metavar='NAME=A,B')
    parser.add_argument('--seed-start', type=int, default=420000)
    parser.add_argument('--seeds', type=int, default=8, help='Number of paired seeds')
    parser.add_argument('--opponent', type=Path, action='append', default=[], help='Add external bots for FFA')
    parser.add_argument('--opponent-python', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.seeds < 1: parser.error('--seeds must be positive')
    try: variants = factors(args.factor)
    except ValueError as exc: parser.error(str(exc))
    sim = args.sim.resolve(strict=True)
    bot = args.bot.resolve(strict=True)
    if not (sim/'local_sim/game.py').is_file(): parser.error('--sim must contain local_sim/game.py')
    source = provenance(bot)
    if args.bot_revision:
        try: source['bot_revision'] = verify_revision(bot, args.bot_revision)
        except (ValueError, subprocess.CalledProcessError) as exc: parser.error(str(exc))
    try:
        sim_commit = subprocess.check_output(['git', '-C', str(sim), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        sim_dirty = bool(subprocess.check_output(['git', '-C', str(sim), 'status', '--porcelain'], text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        sim_commit, sim_dirty = None, None
    result = {'source': source, 'simulator': {'path': str(sim), 'commit': sim_commit, 'dirty': sim_dirty},
              'mode': 'ffa' if args.opponent else 'squad', 'bot': str(bot), 'variants': []}
    for env in variants:
        rows = []
        for seed in range(args.seed_start, args.seed_start + args.seeds):
            command = [sys.executable, str(RUNNER), '--sim', str(sim), '--kit', str(ROOT), '--bot', str(bot), '--seed', str(seed)]
            for name, value in env.items(): command.extend(['--bot-env', name+'='+value])
            for opponent in args.opponent: command.extend(['--opponent', str(opponent.resolve(strict=True))])
            if args.opponent_python: command.extend(['--opponent-python', str(args.opponent_python.resolve(strict=True))])
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if completed.returncode:
                raise RuntimeError('seed %s failed: %s' % (seed, completed.stderr.strip()))
            rows.append(json.loads(completed.stdout.strip().splitlines()[-1]))
            print(json.dumps({'factors': env, 'seed': seed, 'points': rows[-1]['points']}), flush=True)
        result['variants'].append({'factors': env, 'summary': summarize(rows), 'matches': rows})
    baseline = result['variants'][0]['matches']
    for variant in result['variants']:
        variant['paired_vs_first'] = compare(baseline, variant['matches'])
    result['interactions'] = interactions(result['variants'])
    if provenance(bot)['bot_sha256'] != source['bot_sha256']:
        raise RuntimeError('bot files changed during the experiment; discard results')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([{'factors': v['factors'], **v['summary'], 'paired': v['paired_vs_first']} for v in result['variants']], indent=2))


if __name__ == '__main__':
    main()
