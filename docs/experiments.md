# Experiments

Practice scores are mean placement points; local simulator results are hypotheses, not official predictions. The current priority is improving practice placement to qualify. [Practice implementation plan](practice-improvement-plan.md) · [Historical experiments and calibration](experiments-history.md) · [Simulator limitations](simulator.md).

## Scoreboards

### Official practice

| Commit / settings | Score | Squad-proxy mean / official minus proxy | Status / provenance |
| --- | ---: | --- | --- |
| `c5aeebba81a5`, default, second run | **5.23** | — | Best reported official practice score. User-reported rerun of the 5.17 shared-torso entry. |
| `4d02e84`, supply drops and late-circle play with shared-torso gun aim | 5.13 | — | User-reported official practice score for the combined version. |
| `c68975862d2b`, supply drops and late-circle play with legacy gun aim | 5.17 | 5.56 on the 16-seed validation panel | User-reported official practice score. |
| `47291ba`, packaged cornered boost, cover recovery and spacing | 4.88 | Unknown | User-reported official trial. Scored 0.02 below the `26db76c` cornered-dodge trial and 0.29 below the then-best 5.17. |
| `4991fa6`, default | **5.17** | 3.81 / +1.36; approximate control, see note | First reported entry to reach 5.17. User confirmed commit and defaults; submission time and run ID unknown. |
| `c5aeebb`, default | **5.17** | 3.875 / +1.295; approximate candidate, see note | First reported shared-torso run. Submission time and run ID unknown. |
| `fb85097`, default | 5.10 | 3.33 / +1.77; approximate candidate, see note | Threat spacing with shared aim; user-reported score. Submission time and run ID unknown. |
| `37d1a1d`, default | 5.06 | 8.50 / −3.44; approximate candidate, see note | Combat cube restraint; user-reported score. Submission time and run ID unknown. |
| `ded4a9c`, default | 4.81 | Unknown | Squad cover and weapon readiness; user-reported score. No local placement screen, submission time or run ID recorded. |
| `ee4f342`, default | 5.04 | 5.125 / −0.085; approximate candidate, see note | Recovery enabled by default; user reported score. Submission time and run ID unknown. |
| `9ceca70`, presumed default | 5.06 | 5.75 / −0.69; approximate first control, see note | User reported current repository result; recovery defaults to legacy. Submission time, run ID, and environment overrides unknown. |
| `26db76c`, packaged cornered dodge | **4.90** | 4.52 / +0.38 on the 50-pair holdout | User-reported official trial, 0.27 below champion. [Trial record](m6_cornered_boost.md#official-result) |
| `184bb55`, default | 4.88 | 3.81 / +1.07; approximate control, see note | Previously reported official baseline; submission time and run ID unknown. |
| `2646e82` | 2.92 | 3.19 / −0.27 | Commit inferred from timestamp. |
| `9a73729` | 2.71 | 3.06 / −0.35 | Reported baseline. |
| `a528856` | 2.56 | Unknown | Commit association unverified. |

The comparison is **official score minus local squad-proxy mean**, not a prediction error against identical matches. The 3.81 control used `184bb55` with a dirty experimental patch and `BOT_GUN_AIM_CHECK=legacy`, simulator `e322ffe`, seeds 420100–420115 (16 matches); it approximates both default policies but is not a verified exact-commit run for either, and had 14 late/invalid responses. The 3.19 and 3.06 means used simulator `e322ffe` and seeds 420000–420015 (16 matches). Official and proxy seeds and opponents differ, and local timing varies; these differences do not establish predictive accuracy. See [calibration and raw-result details](experiments-history.md#squad-proxy-calibration-against-official-practice).

The 5.75 proxy control used the P01 dirty candidate tree based on `e224892`, with recovery disabled and seeds 420200–420215; it was not an exact-commit run of `9ceca70`. A repeat of that control averaged 5.00, illustrating timing variation. The 5.06 result is attributed to `9ceca70` as the current repository implementation, assuming default settings; confirm the submitted commit and environment if available.

The 5.125 proxy candidate used that same dirty tree and seeds with `BOT_SQUAD_RECOVERY=cover`; it predates `ee4f342` and is not an exact-commit run. Its difference from the official score is not a calibrated prediction error.

The 8.50 cube-restraint estimate is the eight-match P02 split screen on seeds 420320–420327, with recovery off; the 3.875 shared-aim estimate is the 16-match historical screen on seeds 420100–420115. Both used simulator `e322ffe` and dirty experimental trees, not verified exact-commit runs of the official candidates. Their timing and small-sample caveats are recorded below and in the [historical shared-aim record](experiments-history.md#candidate-shared-torso-gun-aim).

The 3.33 spacing estimate is the six-match P05 screen on seeds 420500–420505 with simulator `e322ffe`, before spacing became the default. It used a dirty experimental tree rather than a verified exact-commit run; see the [P05 record](#p05-navigation-probes-and-comparison).

`4991fa6` defaults to the integrated policy with `BOT_GUN_AIM_CHECK=legacy`. Its opt-in gun-aim change was **not active** in the reported 5.17 result; do not attribute the change in score to it. Fixed practice seeds do not eliminate runtime timing noise. The 5.17 versus 4.88 score difference has no paired match-level uncertainty.

### FFA

The best FFA candidate is **undetermined**. The gun-aim candidate's local FFA screen is recorded in the [historical FFA table](experiments-history.md#local-ffa-performance); a single lineup and 16 pairs do not establish a champion. FFA remains separate from the practice scoreboard and is deferred while qualification practice is the priority.

## Supply drops and late-circle practice play

The scored commit `c68975862d2b` used the gun aim and movement settings from the earlier 5.17 entry (`4991fa6`). When squad play is active and there is no immediate danger, the bot values reachable supply drops more highly as its health falls. It estimates travel, landing and capture time against the zone deadline and holds inside the ring. When the next radius reaches 140 m with more than three mechs alive, it switches to selective engagement. At three remaining it resumes squad combat. That commit shipped with `BOT_LATE_HIDE=1`, `BOT_NAV_METHOD=legacy` and `BOT_GUN_AIM_CHECK=legacy`.

| Squad-proxy panel | Official 5.17 build | Drops only | Drops and late-circle play | Also rush laser |
| --- | ---: | ---: | ---: | ---: |
| 12 native pairs, 422715–422726 | 3.42 | 4.08 | 4.17 | — |
| 10 restricted-container matches per build, 423815–423824 | 5.50 | — | 6.20 | 7.50 |
| 16 native matches per build, 422890–422905 | 5.19 | — | 5.56 | 4.63 |

The final 16 seeds were fresh for the champion and laser variant. The simpler candidate ran afterward in a separate block on those same starts. Its mean paired gain was +0.38 with a 95% seed-bootstrap interval of [-0.69, 1.62]. On that panel the simpler candidate recorded zero captures and zero late or invalid replies. It captured two drops in the 12-seed screen. The three panels support an official trial of the combined policy. Individual gains cannot be attributed to captures alone.

The optional `BOT_LASER_RUSH=1` variant scans for lasers when calm, prioritizes reachable lasers and boosts toward them above 60 energy. It acquired a laser within 30 seconds in 9 of 16 validation matches versus 4 of 16 for the champion, but lost 0.56 placement points per match on that panel. It stays off in the packaged candidate. The official score for `c68975862d2b` was **5.17**.

Commit `4d02e84` combined these supply-drop and late-circle tactics with the shared-torso gun check from `c5aeebba81a5` by setting `BOT_GUN_AIM_CHECK=actual`. It scored **5.13** in official practice, 0.04 below its parent’s 5.17 and 0.10 below the shared-torso entry’s best run.

All panels used simulator `e322ffe`. Local raw evidence is in `mech-testing/tactics-screen-422715/`, `mech-testing/tactics-image-panel/` and `mech-testing/tactics-validation-422890/` (the later comparison is under `drops/`).

## Active practice candidates

The initial order is recovery, farming, positioning, aiming, and navigation; trace evidence can change it. One narrow candidate from each of P01–P05 has been tested officially. Each is described and challenged in the [implementation plan](practice-improvement-plan.md).

| ID | Priority / candidate | Expected mechanism | Main risk | Status |
| --- | --- | --- | --- | --- |
| P01 | 1. [Recovery and disengagement](practice-improvement-plan.md#p01-recovery-and-disengagement) | Survive repeat encounters by reaching cover and allowing health regeneration. | Shared vision and pursuit prevent a safe break; retreat can expose rear armor. | Official 5.04; inconclusive versus timing noise; [record](#p01-first-recovery-screen) |
| P02 | 2. [Efficient farming](practice-improvement-plan.md#p02-efficient-farming) | Acquire damage, health, upgrades, and useful weapons early at favorable cost. | Farming delays kills and costs health or zone time. | Cube-restraint test 5.06; [record](#p02-split-screen) |
| P03 | 3. [Anti-squad positioning](practice-improvement-plan.md#p03-anti-squad-positioning) | Limit simultaneous enemy firing angles while retaining our own opportunities to deal damage. | Cover can block our shots, permit encirclement, or delay kills. | Cover/readiness test 4.81; [record](#official-positioning-candidate) |
| P04 | 4. [Aiming and kill conversion](practice-improvement-plan.md#p04-aiming-and-kill-conversion) | Land more shots and finish reachable threats to shorten fights. | Prediction errors or target fixation can reduce damage and increase exposure. | Shared-aim runs 5.17 and 5.23; [record](#official-shared-aim-candidate) |
| P05 | 5. [Navigation and zone pressure](practice-improvement-plan.md#p05-navigation-and-zone-pressure) | Reduce exposure and zone damage with better movement decisions. | Spacing can reduce damage dealt; cover or early rotation can delay kills. | Spacing scored 5.10 officially; [record](#p05-navigation-probes-and-comparison) |

The previous [shared-torso gun-aim experiment](experiments-history.md#candidate-shared-torso-gun-aim) was locally inconclusive. Its squad comparison had asymmetric late/invalid responses; its FFA comparison is not evidence of practice improvement. Its official test tied the best reported score, which does not establish a performance difference.

### P01 first recovery screen

- Parent `e224892` (documentation-only successor to `4991fa6`); dirty bot hash `b4bf4835573443275996ba3ed90be92863d81f4eb77806f110e8833b6c3906d7`, diff SHA-256 `d8e9ccb6d4a796ab8d9887644a8bcbee7c0c4caf5e1faf7a626ca4bb35b650c8`; saved local patch `mech-testing/p01-recovery-candidate.diff`. The local experiment used `BOT_SQUAD_RECOVERY=legacy` as control and `cover` as candidate. Commit `ee4f342` enabled `cover` by default for its official test; later commits returned to `legacy`.
- Baseline traces for seeds 420100, 420101 and 420108 show periods below 55% HP and firing during those periods; HP also increased during all three matches, so the traces do not establish an absence of healing. Raw traces: `mech-testing/p01-baseline-{420100,420101,420108}.jsonl`.
- Candidate sustains a cover retreat for up to 10 seconds, holds fire while recovering, and yields to an urgent zone, a threat within 35 m, a finishing opportunity, or unavailable cover. Hypothesis: a longer damage-free interval enables regeneration and improves placement. Counter-hypothesis: lost damage, shared enemy vision and exposure while retreating outweigh healing. Focused controller scenarios pass; they do not establish actual healing in a match. An already charged laser can release when its trigger is dropped.
- Squad proxy `e322ffe`, seeds 420200–420215, 16 matches per pass, run in order baseline → candidate → repeated baseline: means **5.75 → 5.125 → 5.00**, candidate minus first **−0.625 ± 0.584 SE**, repeated control minus first **−0.75 ± 0.423 SE**, candidate minus repeated control **+0.125 ± 0.407 SE**. Kills: 3.69 / 2.88 / 2.94; mean survival: 211.08 / 204.00 / 202.92 s; late/invalid: 2/2, 1/1, 2/2. Raw result: `mech-testing/p01-recovery-squad-420200.json`. Sequential ordering and timing-sensitive searches confound comparisons; matched seeds can diverge.
- Official `ee4f342`, default recovery enabled: **5.04**, reported by user; submission time and run ID unknown. Difference from best reported 5.17 is −0.13, but the 5.06 run with recovery off and repeated local controls demonstrate variability; no causal conclusion follows from aggregate scores.
- Decision: **investigate; retain 5.17 official champion**. Capture candidate and control traces with recovery-state and healing-window measurements for further investigation. FFA deferred.

### P02 first farming screen

- Parent `ee4f342`; recovery forced off in all variants to approximate the 5.17 policy while its official recovery test is pending. Dirty bot SHA-256 `a72861c975e2253fd2af7d39897e325e4a8b8c100d0812e3000975183b434978`, diff SHA-256 `66a6c6f6c0d73ae2cffa7d068ef91bef63c936cf009091896767da63f330a0fb`; saved local patch `mech-testing/p02-farming-candidate.diff`. Farming defaults to `legacy`; `BOT_SQUAD_FARMING=selective` enables the candidate.
- Hypothesis: prioritize pickups with unobstructed nearby paths and near-term upgrades, penalize stale NPC targets while valuing weakened ones, and avoid cube detours during active combat. Counter-hypothesis: an approximate blocked-line penalty rejects worthwhile routes; avoiding combat cubes forfeits upgrades and healing; these bundled changes cannot individually explain any outcome. The focused blocked-versus-clear cube scenario passed.
- Squad proxy `e322ffe`, seeds 420300–420307, 8 matches per pass in baseline → candidate → repeated-baseline order: means **4.50 → 3.875 → 4.875**; candidate minus first **−0.625 ± 0.625 SE**, repeated control minus first **+0.375 ± 0.420 SE**, candidate minus repeated control **−1.00 ± 0.732 SE**. Kills 2.375 / 1.875 / 2.75; survival 151.85 / 144.73 / 165.03 s; late/invalid 0/0 each. Raw result `mech-testing/p02-farming-squad-420300.json`. Small sample and sequential timing variation prevent a firm conclusion.
- Decision after this screen: **investigate**. The subsequent split and official cube-restraint result are recorded below; FFA deferred.

### P02 split screen

- Parent `ee4f342` with `BOT_SQUAD_RECOVERY=legacy` in every variant; dirty bot SHA-256 `f9629b50a8bdffe39a230c103ebdd208e3c2d848ac3d29ab5918f06ed26eb608`, diff SHA-256 `8db1d46d39aa981ad3fdd6d6329691ae696961e73c03306f183b2100818537e1`, saved patch `mech-testing/p02-split-candidate.diff`. `BOT_SQUAD_FARMING=route` changes objective scoring; `cubes` disables combat cube detours; `legacy` is the control. Both factors remain opt-in. They separate the previous bundled hypothesis, but the route variant still combines several scoring changes.
- Squad proxy `e322ffe`, seeds 420320–420327, eight matches each, sequential baseline → route → cubes → baseline: means **8.625 / 8.625 / 8.50 / 7.25**. Versus first control, route **0.00 ± 1.363 SE**, cubes **−0.125 ± 0.789 SE**, repeat control **−1.375 ± 1.267 SE**. Versus repeated control, route **+1.375 ± 1.164 SE**, cubes **+1.25 ± 1.221 SE**. Late/invalid counts 2/2, 4/4, 1/1, 0/0 respectively. Raw result `mech-testing/p02-split-squad-420320.json`. Small samples, differing late counts, order effects and substantial control variation preclude a conclusion.
- Official `37d1a1d`, default `cubes`, recovery disabled: **5.06**, user-reported, compared with 5.17 baseline; submission time and run ID unknown. Difference −0.11 is comparable in size to observed repeat variability and does not establish causation. Route remains a separate opt-in policy. Best official practice score remains 5.17.

### P05 navigation probes and comparison

- Base `c5aeebb`, default shared-torso gun aim retained. Five squad-proxy traces on seeds 420400–420404 produced 9, 3, 3, 10 and 7 placement points; all ended before a win. Each showed substantial gun damage; observed multi-enemy proximity varied from about 5 to 75 seconds. One trace had 2.7 seconds outside the zone and 270 observed zone damage. Commanded movement with low measured speed varied from 0.2 to 12.3 seconds, but includes ordinary acceleration and fighting, not necessarily stalls. Last observations and end events do not always unambiguously identify the lethal source. These proxy observations motivate combat spacing and cover as well as earlier rotation; they do not establish official-engine death causes. Raw traces `mech-testing/p05-probe-{420400,420401,420402,420403,420404}.jsonl`.
- Screened independent `BOT_NAV_METHOD` variants: `spacing` penalizes close proximity to observed enemies, especially lightning; `cover` increases the penalty for visibility to secondary enemies; `early_zone` starts rotation earlier. `legacy` is the prior behavior. Risk: spacing sacrifices firing angles, cover reduces damage or costs computation, and early rotation abandons fights. Squad proxy `e322ffe`, six pairs on 420500–420505, sequential legacy → spacing → cover → early_zone → repeated legacy. Local results select among approaches, not certify an official improvement.
- Mean points: **3.33 / 3.33 / 2.33 / 3.00 / 2.67**; candidate-minus-first-control ± SE: spacing **0.00 ± 0.68**, cover **−1.00 ± 0.68**, early zone **−0.33 ± 0.56**; repeated control **−0.67 ± 0.42**. Versus repeated control: spacing **+0.67 ± 0.71**, cover **−0.33 ± 0.33**, early zone **+0.33 ± 0.56**. Mean kills: 1.83 / 2.17 / 1.00 / 1.50 / 1.33; late/invalid: 0/0, 0/0, 4/4, 0/0, 1/1. Sequential order, timing variation, and six seeds make all estimates uncertain. Raw result `mech-testing/p05-navigation-420500.json`; dirty bot SHA-256 `2f4c9b37abd6c890200a1250a40766a527d3ecdc2628d3e8ab03e904a3bf6bc1`, diff SHA-256 `b20201dcf013708c6533a8f7cfa6724509e57162ccaa82d70f128d50d5a618d5`; saved patch `mech-testing/p05-navigation-candidates.diff`. Those hashes identify the screened opt-in versions, before selecting the default.
- Official `fb85097`, default spacing and shared aim: **5.10**, user-reported; submission time and run ID unknown. This is −0.07 versus the 5.17 `c5aeebb` parent, within the range of previously observed variation; the aggregate score does not establish whether spacing helped or hurt.
- Decision: **investigate**; retain the earlier 5.17 official champion. `spacing` is the committed default; `BOT_NAV_METHOD=legacy` restores the prior behavior, while the alternatives remain available. Recovery, farming and squad-cover experiments remain disabled by default; `c5aeebb` shared aim remains enabled.

## Operating loop

### Official positioning candidate

`ded4a9c` returns farming and recovery to `legacy` and enables `BOT_SQUAD_POSITION=cover` by default. In squad combat it seeks cover from an aimed charging laser when our beam is not hot and considers secondary-weapon readiness instead of treating any laser or lightning as ready. Hypothesis: reduce incoming fire while unable to deal effective damage. Risk: hiding can reduce our own damage or delay kills; local score unknown. The protocol replay passed with one late reply on this host. Official score **4.81**, user-reported, −0.36 versus 5.17; time and run ID unknown. Timing noise and no match-level breakdown prevent attributing this difference to the policy; investigate before reusing it.

### Official shared-aim candidate

`c5aeebb` returns positioning, farming and recovery to `legacy` and enables `BOT_GUN_AIM_CHECK=actual` by default. It suppresses a gun trigger when the final shared torso command is aiming elsewhere for the laser or mortar. Hypothesis: avoid wasting ammunition; risk: a later physics tick could align, so withheld fire can reduce damage. The prior local screen is inconclusive and timing-confounded. Protocol replay passed on this host with no late replies. The user reported **5.17 on the first run** and **5.23 on the second run** of the same commit. Submission times and run IDs are unknown.

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
