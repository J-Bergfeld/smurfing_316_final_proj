# Experiments

Practice scores are mean placement points. A simulated delta is a hypothesis, not an official prediction.
Use the same seeds and simulator revision for each factor combination. Record the commit and environment
values; if the tree is dirty, preserve the diff and bot hash with the results.

| Version / commit | Change and reason | Simulated Δ | Official score / Δ | Status |
| --- | --- | --- | --- | --- |
| `2646e82` | 11:21 p.m. Nov 20 bot: tactics, repositioning and roofs | — | 2.92 / — | Best reported; commit inferred from timestamp |
| `a528856` | Previous bot | — | 2.56 / — | Baseline reported by user; commit association unverified |
| `9a73729` | Adaptive combat and farming | — | 2.71 / +0.15 | Baseline reported by user |
| pending | Urgent roof descent: escape instead of stalling at an edge | +1 on one squad-proxy seed; 3 other seeds tied | Not submitted | Keep testing |
| pending | `BOT_STRAFE=steady` and `BOT_HUNTERS=on`: test movement and active-threat selection separately and together | 2 seeds: steady −1.0, hunters 0.0, interaction 0.0 | Not submitted | Smoke test only; opt-in |
| pending (`dc22ddf`, bot `5fa80b81b4f8`) | Predictive gun trigger: account for next tick's turn | 16 seeds: −0.38 ± 0.77 SE; 3 late | Not submitted | Opt-in; keep testing |
| pending (`dc22ddf`, bot `14c3fd7c4164`) | Selective threats: prioritize attackers and closing enemies | 16 seeds: −0.31 ± 0.60 SE | Not submitted | Opt-in; keep testing |
| pending (`dc22ddf`, bot `fcabe0f643db`) | Squad economy: seek laser, farm at moderate health | 4 seeds: −0.25 ± 0.25 SE | Not submitted | Opt-in; keep testing |
| pending (`dc22ddf`, bot `521cbac18c08`) | Gun-preserving loadout: reserve secondary for laser or lightning | 8 seeds: 0.00 ± 0.19 SE | Not submitted | Opt-in; keep testing |
| pending (`dc22ddf`, bot `0539c4c5d674`) | Integrated policy and shared per-turn search budget | 8 seeds: 3.13; earlier repeat: 4.75 | Not submitted | Historical |
| pending (`dc22ddf`, bot `d5904f95136b`) | Consolidate active policy into one controller | 16 seeds: 4.31; 5 late replies | Not submitted | Historical |
| pending (`dc22ddf`, bot `1018d68aa3ae`) | Python seeded RNG and Python-built world grid | 16 seeds: 4.81 vs previous 4.31; +0.50 ± 0.89 SE; 2 late | Not submitted | Default; test officially |
| pending (`dc22ddf`, bot `ccbae42b74e4`) | Split threat, objective, evasion, and weapon decisions into testable methods; expected Δ 0 | 4 seeds: 6.25; −1.25 ± 2.75 SE vs prior run; 1 late | Not submitted | Behavior-preserving refactor; sample too small to establish a score change |
| pending (`dc22ddf`, bot `5aeac9bfaaac`) | Move active perception, geometry, movement, combat, and loadout into their modules; expected Δ 0 | 4 seeds: 6.25; 0.00 ± 4.64 SE vs prior run; 2 late | Not submitted | Behavior-preserving refactor; sample too small to establish a score change |

## Run

```sh
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--mech-royale \
  --factor BOT_POLICY=legacy,integrated --factor BOT_STRAFE=legacy,steady \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The JSON records per-seed outcomes, factors, paired differences, a two-factor interaction, bot and diff
hashes, and simulator revision. The first value of each factor is the control. `BOT_STRAFE` affects only
the legacy policy in this example. Use a clean committed checkout
for official comparisons. `--opponent` enables FFA; without opponents the runner uses the squad proxy.
These tests are not a substitute for the official engine.

## Calibration

| Bot / version | Simulator and seeds | Sim mean | Official mean | Difference |
| --- | --- | --- | --- | --- |
| `2646e82` | squad proxy `e322ffe`, 420000–420015 (16 matches) | 3.19 (SE 0.60) | 2.92 | +0.27; different seeds and opponents |
| `2646e82` | second proxy `c1cc0d2`, 0–3 (4 matches) | 2.75 | 2.92 | −0.17; different seeds and opponents |
| 2.71 baseline | squad proxy, 420000–420003 | 2.0 | 2.71 | −0.71; only four matches, diagnostic only |

The first proxy's 16-match scores range from 0 to 6; its approximate 95% interval for the mean is
1.91–4.47. The official 2.92 covers 48 matches on private seeds. These estimates cannot establish
predictive accuracy or a correction factor. Repeated local runs also vary with time-limited searches.

Paired squad-proxy comparison, seeds 420000–420015: `2646e82` **3.19**, `9a73729` **3.06**;
new minus old **−0.13 ± 0.30 SE** (4 wins, 3 losses, 9 ties). Neither the direction nor a cause is established.
The most recent 16-seed run scored **10, 2, 8, 10, 2, 5, 4, 2, 3, 1, 1, 6, 3, 4, 6, 10**;
its +0.50 ± 0.89 SE change does not establish an improvement. Raw local results remain under `mech-testing/`.
