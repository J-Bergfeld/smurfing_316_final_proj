"""Freeze the squad proxy inputs and run a serial, evidence-producing panel."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

if __package__:
    from .match_telemetry import fingerprint
else:
    from match_telemetry import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def revision(path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()
    return dict(commit=git('rev-parse', 'HEAD'), dirty=bool(git('status', '--porcelain')))


def freeze(out, sim, bot_root=ROOT):
    groups = {
        'bot': (bot_root, ['main.py', 'mechfight.py', 'bot/*.py', 'bot/*.gz', 'bot/*.json']),
        'sim': (sim, ['arena.py', 'local_sim/*.py', 'local_sim/*.c']),
        'kit': (ROOT, ['arena/v2/world.json', 'arena/v2/terrain.i16', 'check/stream.jsonl.gz']),
        'tools': (ROOT/'tools', ['run_local_match.py', 'match_telemetry.py', 'baseline.py']),
    }
    hashes = {}
    with zipfile.ZipFile(out/'inputs.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for group, (root, patterns) in groups.items():
            files = {}
            for pattern in patterns:
                for path in sorted(root.glob(pattern)):
                    name = path.relative_to(root).as_posix()
                    data = path.read_bytes()
                    archive.writestr(group+'/'+name, data)
                    files[name] = hashlib.sha256(data).hexdigest()
            hashes[group] = fingerprint(files)
        archive.extractall(out/'inputs')
    return hashes


def prepare(out, sim, bot, env, seed_start, seeds):
    out.mkdir(parents=True, exist_ok=False)
    hashes = freeze(out, sim, bot)
    manifest = dict(v=1, level='L3', field='scripted-squad', map='arena/v2', env=env,
                    seed_start=seed_start, seeds=seeds, snapshot=hashes,
                    bot=revision(bot), sim=revision(sim), runner=revision(ROOT),
                    config_sha256=fingerprint([hashes['kit'], env, 'scripted-squad']),
                    archive_sha256=hashlib.sha256((out/'inputs.zip').read_bytes()).hexdigest(),
                    python=sys.version, platform=platform.platform(), created=datetime.now(timezone.utc).isoformat())
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def run_seed(out, manifest, seed, lib=None):
    inputs = out/'inputs'
    command = [sys.executable, str(inputs/'tools/run_local_match.py'), '--sim', str(inputs/'sim'),
               '--kit', str(inputs/'kit'), '--bot', str(inputs/'bot/main.py'), '--seed', str(seed),
               '--events', str(out/f'{seed}.jsonl')]
    if lib:
        command.extend(['--geometry-library', str(lib)])
    runtime_env = {k:v for k,v in os.environ.items() if not k.startswith('BOT_')}
    runtime_env.update(manifest['env'])
    stamp = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    row = json.loads(subprocess.check_output(command, cwd=inputs/'bot', text=True, env=runtime_env))
    row.update(wall_seconds=time.perf_counter()-start, timestamp=stamp,
               match_id=fingerprint([manifest['snapshot'], manifest['config_sha256'], seed, row['initial_layout_sha256']]),
               evidence=f'{seed}.jsonl')
    (out/f'{seed}.json').write_text(json.dumps(row, indent=2)+'\n')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seed-start', type=int, default=421100)
    parser.add_argument('--seeds', type=int, default=20)
    parser.add_argument('--bot-root', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error('positive seed count required')
    out = args.out.resolve()
    sim = args.sim.resolve(strict=True)
    bot = args.bot_root.resolve(strict=True)
    env = {k:v for k,v in os.environ.items() if k.startswith('BOT_')}
    manifest = prepare(out, sim, bot, env, args.seed_start, args.seeds)
    for seed in range(args.seed_start, args.seed_start+args.seeds):
        row = run_seed(out, manifest, seed)
        print(seed, row['points'], row['terminal']['fatal_weapon'], flush=True)


if __name__ == '__main__':
    main()
