# Experiments

Practice scores are mean placement points; local simulator results are hypotheses, not official predictions. The current priority is improving practice placement to qualify. [Practice implementation plan](practice-improvement-plan.md) · [Historical experiments and calibration](experiments-history.md) · [Simulator limitations](simulator.md).

## Scoreboards

### Official practice

| Commit / settings | Score | Squad-proxy mean / official minus proxy | Status / provenance |
| --- | ---: | --- | --- |
| `4991fa6`, default | **5.17** | 3.81 / +1.36; approximate control, see note | Best reported official entry and current working champion. User confirmed commit and defaults; submission time and run ID unknown. |
| `184bb55`, default | 4.88 | 3.81 / +1.07; approximate control, see note | Previously reported official baseline; submission time and run ID unknown. |
| `2646e82` | 2.92 | 3.19 / −0.27 | Commit inferred from timestamp. |
| `9a73729` | 2.71 | 3.06 / −0.35 | Reported baseline. |
| `a528856` | 2.56 | Unknown | Commit association unverified. |

The comparison is **official score minus local squad-proxy mean**, not a prediction error against identical matches. The 3.81 control used `184bb55` with a dirty experimental patch and `BOT_GUN_AIM_CHECK=legacy`, simulator `e322ffe`, seeds 420100–420115 (16 matches); it approximates both default policies but is not a verified exact-commit run for either, and had 14 late/invalid responses. The 3.19 and 3.06 means used simulator `e322ffe` and seeds 420000–420015 (16 matches). Official and proxy seeds and opponents differ, and local timing varies; these differences do not establish predictive accuracy. See [calibration and raw-result details](experiments-history.md#squad-proxy-calibration-against-official-practice).

`4991fa6` defaults to the integrated policy with `BOT_GUN_AIM_CHECK=legacy`. Its opt-in gun-aim change was **not active** in the reported 5.17 result; do not attribute the change in score to it. Fixed practice seeds do not eliminate runtime timing noise. The 5.17 versus 4.88 score difference has no paired match-level uncertainty.

### FFA

The best FFA candidate is **undetermined**. The gun-aim candidate's local FFA screen is recorded in the [historical FFA table](experiments-history.md#local-ffa-performance); a single lineup and 16 pairs do not establish a champion. FFA remains separate from the practice scoreboard and is deferred while qualification practice is the priority.

## Active practice candidates

The initial order is recovery, farming, positioning, aiming, and navigation; trace evidence can change it. None has been promoted or officially tested as a distinct candidate. Each is described and challenged in the [implementation plan](practice-improvement-plan.md).

| ID | Priority / candidate | Expected mechanism | Main risk | Status |
| --- | --- | --- | --- | --- |
| P01 | 1. [Recovery and disengagement](practice-improvement-plan.md#p01-recovery-and-disengagement) | Survive repeat encounters by reaching cover and allowing health regeneration. | Shared vision and pursuit prevent a safe break; retreat can expose rear armor. | Proposed |
| P02 | 2. [Efficient farming](practice-improvement-plan.md#p02-efficient-farming) | Acquire damage, health, upgrades, and useful weapons early at favorable cost. | Farming delays kills and costs health or zone time. | Proposed |
| P03 | 3. [Anti-squad positioning](practice-improvement-plan.md#p03-anti-squad-positioning) | Limit simultaneous enemy firing angles while retaining our own opportunities to deal damage. | Cover can block our shots, permit encirclement, or delay kills. | Proposed |
| P04 | 4. [Aiming and kill conversion](practice-improvement-plan.md#p04-aiming-and-kill-conversion) | Land more shots and finish reachable threats to shorten fights. | Prediction errors or target fixation can reduce damage and increase exposure. | Proposed |
| P05 | 5. [Navigation and zone pressure](practice-improvement-plan.md#p05-navigation-and-zone-pressure) | Avoid stalls, unreachable objectives, and late zone entries using route-aware estimates. | Search overhead and conservative detours may outweigh rare failures. | Proposed |

The previous [shared-torso gun-aim experiment](experiments-history.md#candidate-shared-torso-gun-aim) remains opt-in and inconclusive. Its squad comparison had asymmetric late/invalid responses; its FFA comparison is not evidence of practice improvement. Revisit it under P04 with the original factor identity intact.

## Operating loop

1. Start from a specific trace, official result, or protocol mechanic. State the tactical alternative, affected situations, expected placement mechanism, counter-hypothesis, and where simulator behavior may not transfer.
2. Challenge the premise in a second reasoning pass. Select a small discriminating scenario and define the decision before looking at results. Prioritize expected placement impact, frequency, transferability, cost, and uncertainty.
3. Run the scenario and screen candidate versus parent on paired **squad-proxy** seeds, starting with 16–32 pairs where feasible. Expand close or consequential comparisons, rotate validation seeds, inspect traces and late/invalid actions, and repeat control against itself to estimate timing noise. The runner executes all seeds of one variant before the next; account for order and machine load. Equal seeds do not make divergent matches identical.
4. For two interacting policies, define a 2×2 comparison (baseline, A, B, A+B), expected interaction, and decision rule in advance. Treat local interactions as exploratory. Use official slots on informative cells only when justified.
5. Before official submission, run protocol, relevant scenario/unit, and restricted-container checks. Submit an exact clean commit; record settings, timestamp, run ID, score, and comparator. Local checks are gates, not proof of official improvement. Official practice is the authority for practice selection.
6. Update the official scoreboard and candidate record; keep raw outcomes and rejected ideas. Revisit interactions and calibrate local versus official candidate-minus-parent deltas over multiple distinct changes. Track FFA separately when that objective resumes.

The published track and status pages have stated **four submissions per hour**, while the team reported six. Verify the live platform limit and cutoff before submitting; until confirmed, plan around four per hour. Keep the best official practice entry, current working champion, and best FFA candidate separate.

## Experiment record template

Give each candidate a stable ID; place detailed records in a linked document as the index grows. Keep official and local results separate and do not infer missing provenance.

```text
ID / status / parent commit and factors / candidate commit and factors:
Observation and evidence (trace, protocol, or official result):
Hypothesis, mechanism, affected situations, expected placement impact:
Counter-hypothesis, failure mode, simulator assumptions:
Discriminating scenario, expected behavior, and decision rule:
Local suite, simulator revision and dirtiness, lineup, seeds, match count:
Paired placement delta ± SE; survival, kills, late/invalid; timing-control results:
Raw result, trace, bot hash, and dirty diff location:
2×2 interaction and predeclared decision, if applicable:
Official submission commit, settings, timestamp, run ID, score, comparator:
Decision (promote / reject / investigate / retest) and next question:
```

## Running and retaining results

```sh
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--eagle-eye-mech-royale \
  --factor BOT_POLICY=legacy,integrated --factor BOT_STRAFE=legacy,steady \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The runner records per-seed outcomes, factors, paired differences, a two-factor interaction, bot and diff hashes, and simulator revision. The first factor value is control; `BOT_STRAFE` in this example affects only the legacy policy. Without `--opponent` the runner uses the squad proxy; with opponents it runs FFA. Use the same simulator revision and seeds for each comparison and record lineup and runtime conditions. The proxy is not the official engine.

`mech-testing/` is Git-ignored: its raw files and saved diffs are local, not shared by committing documentation. Preserve the exact diff and bot hash for dirty runs, record where artifacts are stored, and arrange durable sharing separately when needed. Missing local files must be marked unavailable, not silently treated as version-controlled evidence.
