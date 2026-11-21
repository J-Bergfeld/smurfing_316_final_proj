# Run a local competitor match

The local runner reads its lineup from the ignored file `competitors/lineup.json`.
The lineup and any opponent-specific dependencies stay
on your computer and are excluded from the submission image.

## Set up a lineup

Create `competitors/lineup.json` with a list of simulator opponents

```bash
python3 -m venv competitors/.venv
competitors/.venv/bin/python -m pip install numpy==1.26.4
python3 tools/competitor_match.py --fetch-only
python3 tools/competitor_match.py --seed 420000
```

The runner fetches missing pinned checkouts into `competitors/updated/` and
verifies existing checkout revisions. It executes the selected opponent code
locally under your account. The match uses our root `main.py`, the local
simulator, and the map and configuration under `arena/` and `check/`. On macOS,
the runner does not enforce the Linux 512 MB address-space limit.

Use `--config /path/to/lineup.json` to select a different configuration or
`--opponents-dir /path/to/checkouts` to reuse existing checkouts. Add
`--trace /tmp/mech-420000.jsonl` to save our bot's observations and actions.
The trace contains game state and can become large.

## Compare versions

Run each version on the same seeds and save the output outside the repository:

```bash
set -o pipefail
label=baseline
mkdir -p "$HOME/mech-testing/results/$label"
for seed in 420000 420001 420002 420003 420004; do
  python3 tools/competitor_match.py --seed "$seed" |
    tee "$HOME/mech-testing/results/$label/$seed.json" || break
done
```

The match fills unused slots with scripted opponents in a simulated
free-for-all. Output includes placement, points, credited kills, elapsed game
time, and late and invalid responses. For a fair comparison, use the same
seeds, lineup, and simulator revision. These scores are not directly comparable
to the official practice field, which uses a cooperating house squad.

## Trace a saved lineup

From the project root, run:

```bash
python3 tools/replay_match.py ~/mech-testing/results/baseline/420000.json
```

Use a result generated on your machine, with its opponent folders and Docker
images available. The helper prints a new directory containing `trace.jsonl`
and `result.json`.
