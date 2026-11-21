# Experiments

Practice scores are mean placement points. A simulated delta is a hypothesis, not an official prediction.
Use the same seeds and simulator revision for each factor combination. Keep the first combination as control.
Record the commit and environment values; if the tree is dirty, preserve the diff and bot hash with the results.

| Version / commit | Change and reason | Simulated Δ | Official score / Δ | Status |
| --- | --- | --- | --- | --- |
| `2646e82` | 11:21 p.m. Nov 20 bot: tactics, repositioning and roofs | — | 2.92 / — | Best reported; commit inferred from timestamp |
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
| `2646e82` | squad proxy `e322ffe`, 420000–420015 (16 matches) | 3.19 (SE 0.60) | 2.92 | +0.27; different seeds and opponents |
| `2646e82` | second proxy `c1cc0d2`, 0–3 (4 matches) | 2.75 | 2.92 | −0.17; different seeds and opponents |
| 2.71 baseline | squad proxy, 420000–420003 | 2.0 | 2.71 | −0.71; only four matches, diagnostic only |

The first proxy's 16-match scores range from 0 to 6; its approximate 95% interval for the mean is 1.91–4.47.
The official 2.92 covers 48 matches on private seeds. These estimates cannot establish predictive accuracy or a
correction factor; compare more versions and repeat official results. Raw local results are in
`mech-testing/calibration-2646e82-420000.json`, `mech-testing/calibration-2646e82-420008.json`, and
`mech-testing/calibration-2646e82-second.jsonl` (ignored local files).
