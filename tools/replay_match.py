"""Run the current bot against a saved local lineup and record a fresh trace."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("baseline", type=Path, help="Result JSON from a previous match")
args = parser.parse_args()

root = Path(__file__).resolve().parents[1]
baseline = args.baseline.expanduser().resolve(strict=True)
result = json.loads(baseline.read_text())
opponents = [entry["bot"] for entry in result["opponents"]]

opponent_args = []
sim = None
for bot in opponents:
    path = Path(bot)
    if path.is_absolute():
        if not path.is_file():
            parser.error(f"Missing opponent on this machine: {path}")
        if (path.parent / "local_sim" / "game.py").is_file():
            sim = path.parent
        opponent_args.extend(["--opponent", bot])
    else:
        opponent_args.extend(["--opponent-image", bot])

if sim is None:
    parser.error("This lineup needs the Eagle Eye simulator folder on this machine.")

seed = result["seed"]
run_dir = Path(tempfile.mkdtemp(prefix=f"replay-{seed}-", dir=baseline.parent))
trace = run_dir / "trace.jsonl"
command = [
    sys.executable, "tools/run_local_match.py",
    "--sim", str(sim), "--kit", ".", "--bot", "./main.py",
    "--seed", str(seed), "--trace", str(trace), *opponent_args,
]

print(f"Running seed {seed}. Output directory: {run_dir}", flush=True)
match = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, check=True)
summary = json.loads(match.stdout)
if not trace.is_file() or trace.stat().st_size == 0:
    raise SystemExit("The match finished without a trace.")

(run_dir / "result.json").write_text(match.stdout)
print(f"Place: {summary['place']} | Points: {summary['points']} | Kills: {summary['kills']}")
print(f"Trace: {trace} ({trace.stat().st_size:,} bytes)")
