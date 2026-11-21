# Experiments

Practice scores are mean placement points. A simulated delta is a hypothesis, not an official prediction.
Use the same seeds and simulator revision for each factor combination. Keep the first combination as control.
Record the commit and environment values; if the tree is dirty, preserve the diff and bot hash with the results.

| Version / commit | Change and reason | Simulated Δ | Official score / Δ | Status |
| --- | --- | --- | --- | --- |
| `a528856` | Previous bot | — | 2.56 / — | Baseline reported by user; commit association unverified |
| `9a73729` | Adaptive combat and farming | — | 2.71 / +0.15 | Baseline reported by user |
| pending | Urgent roof descent: escape instead of stalling at an edge | +1 on one squad-proxy seed; 3 other seeds tied | Not submitted | Keep testing |
| pending | `BOT_STRAFE=steady` and `BOT_HUNTERS=on`: test movement and active-threat selection separately and together | 2 seeds: steady −1.0, hunters 0.0, interaction 0.0 | Not submitted | Smoke test only; opt-in |

## Run

```sh
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--eagle-eye-mech-royale \
  --factor BOT_STRAFE=legacy,steady --factor BOT_HUNTERS=off,on \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The JSON contains per-seed outcomes, factor values, paired differences, a two-factor interaction, bot and diff hashes,
and simulator revision. The first value of each factor is the control. Use a clean committed checkout for official
comparisons. `--opponent` enables FFA; without opponents the runner uses the squad proxy. These tests run external
controller processes and are not a substitute for the official engine.

## Calibration

| Bot / version | Simulator and seeds | Sim mean | Official mean | Difference |
| --- | --- | --- | --- | --- |
| 2.71 baseline | squad proxy, 420000–420003 | 2.0 | 2.71 | −0.71; only four matches, diagnostic only |

Do not infer a correction factor from this row. Add matched versions and larger samples before interpreting simulator accuracy.
