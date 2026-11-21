# Run a local competitor match

From a checkout of the team's dev branch, run the commands below on macOS, Linux, or the Ubuntu terminal in VS Code. On Windows, type `wsl -d Ubuntu` in PowerShell first. A checkout at `C:\Users\jackb\mech-royal` is visible at `/mnt/c/Users/jackb/mech-royal`. Use your own checkout path. Both shells edit the same files.

## First run

On Ubuntu, install the dependencies once:

```bash
sudo apt update
sudo apt install -y git python3 build-essential
```

From the repository root:

```bash
python3 tools/competitor_match.py --seed 420000
```

To download without running a match, use `python3 tools/competitor_match.py --fetch-only`. The runner launches their Python code locally under your account. It uses a simulator, the team's root `main.py`, and the map and configuration under `arena/` and `check/`. Docker is optional for this workflow.

If you already have all four opponent folders, reuse them without downloading anything:

```bash
python3 tools/competitor_match.py --opponents-dir ~/mech-testing/opponents --seed 420000
```

## Compare two bot versions

Save the bot files in VS Code. From the repo root, run a five-seed batch. Pick a fresh label for each version:

```bash
set -o pipefail
label=baseline
mkdir -p "$HOME/mech-testing/results/$label"
for seed in 420000 420001 420002 420003 420004; do
  python3 tools/competitor_match.py --seed "$seed" |
    tee "$HOME/mech-testing/results/$label/$seed.json" || break
done
```

The match runs your bot and scripted opponents in a simulated free-for-all. Output includes your placement, points (16 minus place), credited kills, elapsed game time, and late and invalid responses. Opponent stats are recorded when your placement is settled. For a fair comparison, use the same seeds, lineup, and simulator revision. These scores describe local free-for-alls. The official practice field is a cooperating house squad.

The previous five-seed reference used a different, three-competitor lineup, so its scores are not directly comparable. To run a custom lineup, see `python3 tools/run_local_match.py --help`.
