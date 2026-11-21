# Experiments

Practice scores are mean placement points. A simulated delta is a hypothesis, not an official prediction.
Use the same seeds and simulator revision for each factor combination. Record the commit and environment
values; if the tree is dirty, preserve the diff and bot hash with the results.

## Operating loop

The team reports the limit is now six official submissions per hour (the published guide may lag).
Aim for one every ten minutes when a candidate is ready; verify the platform's actual limit and cutoff.
Keep the best official practice entry, current working champion, and best FFA candidate separately.
An official result is the authority for practice; neither local suite establishes final performance.

1. Start with a concrete failure or opportunity from traces, official feedback, or protocol mechanics.
   Describe a broad tactical alternative, why it should change placement, and where it could fail.
2. Have a second reasoning pass challenge the assumptions, identify simulator-dependent claims and
   propose a discriminating scenario. Check claims against protocol and traces; plausible reasoning is
   not evidence. Prioritize by expected placement impact, frequency, transferability, cost and uncertainty.
3. Test the mechanism in a small reproducible scenario, then screen the candidate against its parent
   using paired squad-proxy and FFA seeds. Start with 16–32 pairs where feasible; expand close or
   consequential comparisons. Review late/invalid actions and traces as well as mean placement.
4. Run protocol, relevant scenario/unit, and restricted-container checks before official submission.
   Record the exact submitted commit, factors, timestamp, score and comparison. Local tests are a
   gate for obvious failures, not proof of official improvement; investigate contradictions.
5. Update both scoreboards and select the next hypothesis while the official run scores. Retain raw
   outcomes and rejected ideas. Revisit movement, combat and economy as interactions become apparent.

Use 2×2 factorials for two plausible interacting philosophies: baseline, A only, B only and A+B,
on matching seeds. Define the expected interaction and decision before looking at results. Local
interaction is exploratory, particularly with small samples; use official slots on informative cells
when their value justifies the cost, and avoid assuming a local interaction transfers. Repeat a control
against itself to understand timing noise. Rotate validation seeds and lineups to limit local overfit.
The runner currently executes one variant's seeds before the next; account for order and machine-load
effects when interpreting comparisons. Do not assume identical seeds make divergent matches identical.

### Hypothesis card

Copy for each candidate or factorial and link to its results:

```text
ID / parent / exact commit and factors:
Observation and evidence (trace, protocol, or official result):
Hypothesis and mechanism; expected affected situations and placement outcome:
Counter-hypothesis / failure mode / simulator assumptions:
Minimal discriminating scenario and expected observable behavior:
Local squad and FFA comparisons: simulator, lineup, seeds, paired delta, uncertainty, failures, raw file:
2×2 interaction and decision rule, if applicable:
Official submission time / score / comparator / result:
Decision: promote, reject, investigate, or retest; next question:
```

## Official practice and candidate history

### Candidate: shared torso gun aim

- Parent: `184bb55`, reported official score 4.88. The integrated policy checks
  gun alignment against the gun lead, but a charging laser can subsequently
  replace the commanded aim. Protocol §6 and §9 say both weapons share the
  slewing torso. The focused controller test reproduces a shot authorized
  while the commanded laser direction misses the gun lead.
- Hypothesis: `BOT_GUN_AIM_CHECK=actual` suppresses that shot using the final
  commanded aim and the next physics tick's slew, preserving ammunition and
  potentially improving combat placement. The parent is `legacy` (default).
- Challenge: a later tick within the action could align, the geometry model and
  simulator may differ from the official engine, and withholding fire can
  reduce damage. This only affects simultaneous gun/laser or mortar aim
  conflicts, so the match-level effect may be small. Compare both squad and
  FFA, inspect late/invalid actions, and do not promote on the unit test alone.
- Reproduction: `test_gun_respects_final_laser_aim`; dirty candidate patch saved
  as `mech-testing/gun-aim-candidate.diff`. Squad screen: simulator `e322ffe`,
  seeds 420100–420115: parent 3.8125, candidate 3.875, paired +0.0625 ±
  0.335 SE; parent 14 late/invalid, candidate 1 late/invalid. The discrepancy
  and sequential execution confound the comparison. Raw result:
  `mech-testing/gun-aim-squad-420100.json`. FFA: parent 11.0, candidate
  11.5625, paired +0.5625 ± 0.547 SE, zero late/invalid for each, raw
  `mech-testing/gun-aim-ffa-420100.json`. Official result pending. Decision:
  investigate on rotated seeds and lineups; keep the parent as default.

The historic table combines official outcomes and local screening. Preserve uncertain commit associations;
new records should identify the comparison and link the separate suite results below.

| Version / commit | Change and reason | Simulated Δ | Official score / Δ | Status |
| --- | --- | --- | --- | --- |
| `184bb55` | Current bot; user reported latest commit score | — | 4.88 / — | Best reported official baseline; submission time and run ID not supplied |
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
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--eagle-eye-mech-royale \
  --factor BOT_POLICY=legacy,integrated --factor BOT_STRAFE=legacy,steady \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The JSON records per-seed outcomes, factors, paired differences, a two-factor interaction, bot and diff
hashes, and simulator revision. The first value of each factor is the control. `BOT_STRAFE` affects only
the legacy policy in this example. Use a clean committed checkout
for official comparisons. `--opponent` enables FFA; without opponents the runner uses the squad proxy.
These tests are not a substitute for the official engine.

## Squad-proxy calibration against official practice

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

For future calibration, add the local and official **candidate-minus-parent** deltas, their identities,
simulator revision, seeds, match counts and raw results. Compare the sign across several distinct
changes as well as absolute scores. Official fixed seeds and local proxy seeds differ, and aggregate
official scores alone do not provide paired per-match uncertainty. Do not derive a correction factor
from the current rows.

| Candidate / parent | Local squad delta (pairs, SE, seeds, simulator) | Official delta (scores, run IDs) | Direction agrees? / caveats |
| --- | --- | --- | --- |
| None recorded yet | — | — | Historical results above are not a validated calibration series |

## Local FFA performance

Track every tested candidate here independently of its practice score. Use the same pinned opponent
lineup, simulator revision and paired seeds within each comparison; record the lineup composition,
spawn variation if available, runtime and raw results. Compare candidates across several lineups and
held-out seeds before identifying a preferred final candidate. An FFA proxy is not the official final.
Leave results unknown until measured; do not compare means across different suites as a ranking.

| Candidate / parent | Lineup and simulator revision | Seeds / matches | Mean placement points; paired delta ± SE | Survival / kills; late / invalid | Raw result / decision |
| --- | --- | --- | --- | --- | --- |
| Gun aim check / `184bb55` | Five pinned opponents from `competitors/lineup.json`; `e322ffe` | 420100–420115 / 16 pairs | 11.5625 vs 11.0; +0.5625 ± 0.547 SE | 230.95 vs 214.43 s; 1.625 vs 1.4375 kills; 0/0 late/invalid each | `mech-testing/gun-aim-ffa-420100.json`; investigate |
