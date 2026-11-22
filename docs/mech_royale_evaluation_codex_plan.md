# Mech Royale — Evaluation Infrastructure and Optimization Plan

> Implementation brief for Codex. **Read and inspect the repository before changing anything.** The immediate objective is to understand why the current bot scores approximately 5–5.5 and build a trustworthy, fast evaluation system. The longer-term target is an official score of 7+.

## 0. Operating principles

1. **Diagnose first.** Do not rewrite strategy before establishing baseline measurements and failure categories.
2. **Use the existing simulator.** Reuse match execution, state representation, scoring, replay, and opponent interfaces. Identify limitations before adding new abstractions.
3. **Optimize for useful evidence per minute**, not raw match count. The existing local suite takes approximately 10 minutes; profile whether this is startup, simulation, serial execution, logging, or too many games.
4. **Keep comparisons paired.** Baseline and candidate(s) use identical seeds, initial conditions, opponent builds, and settings wherever possible. Gameplay divergence means trajectories will differ, but paired initial conditions still reduce noise.
5. **Explore with paired A/B/C; confirm with paired A/B.** Use small common-seed A/B/C screening when comparing genuinely different tactics. Confirm the best challenger against the incumbent on held-out seeds. Do not make three-way testing mandatory for every small fix.
6. **Preserve every tested build by Git commit SHA and configuration hash.** No need to duplicate the repository. Never rely on a mutable branch name as the identity of a historical result. Use worktrees or isolated build directories if tests run concurrently.
7. **Use official submission capacity intentionally.** Aim to use all six rolling submissions per hour when possible. If no proven improvement is ready, submit a deliberately selected diagnostic candidate (or baseline repeat if allowed/useful), not arbitrary untested code. Keep the champion intact. Track actual rolling slot availability rather than assuming exact ten-minute intervals.
8. **Local score is a proxy.** Measure its correlation and calibration against official results; do not assume that local winners transfer.
9. **No fabricated measurements.** All metrics and charts must be computed from actual game events and clearly distinguish measured values from heuristic diagnoses.

## 1. First action: repository reconnaissance (no gameplay changes)

Inspect the codebase and produce `docs/evaluation_audit.md` covering:

- How the bot is built, configured, and submitted; exact official artifact format and restrictions.
- Simulator entry points, match APIs, available seed control, opponent selection, and deterministic replay/state injection support.
- Score calculation and known differences between local and official scoring.
- Existing logs, traces, replay tools, metrics, and test scripts.
- Runtime profiling of the current ~10-minute local suite: total matches, mean/p50/p95 match duration, CPU utilization, startup overhead, compilation, parallelization opportunities, and logging overhead.
- Current movement, shooting, engagement, farming, resource, and zone-policy decision points.
- Which proposed scenario tests can be implemented directly, which need replay/state injection, and which require simulator changes.
- Concrete implementation plan aligned to existing language/framework/conventions.

**Stop and report blockers rather than guessing APIs or game rules.** Do not assume access to official benchmark internals.

## 2. Phase 1 — Baseline telemetry and failure diagnosis

### 2.1 Stable build identity

Capture for every run:

- Git commit SHA, dirty-tree status, code/config hash, simulator version, game version if available.
- Seed, map/scenario ID, initial state fingerprint, opponent names and exact build hashes, run timestamp.
- Test level, wall-clock runtime, game duration, outcome, official-compatible score if locally computable.
- Whether results are reproducible. If working-tree changes must be tested, snapshot the exact source or build artifact and record its content hash; do not label it as a clean commit.

### 2.2 Structured event logging

Instrument existing decisions with minimal performance impact. Prefer JSONL events and a compact per-match JSON summary. Example event schema:

```json
{"schema_version":1,"match_id":"example","tick":120,"actor":"self","event":"engagement_decision","target_id":"enemy_2","action":"engage","features":{"self_hp":42,"enemy_hp_estimate":90,"distance":18,"line_of_sight":true},"policy_reason":"expected_advantage"}
```

Capture when observable:

- **Movement:** target position, chosen direction, field terms/weights, actual displacement, collision/stuck/oscillation events, exposure and cover indicators, zone status.
- **Combat:** detected enemies, line of sight, engagement decision and reason, target choice, shots, hit/miss, damage dealt/taken, weapon/ammo/energy, distance, kill conversion, retreat outcomes.
- **Farming:** resource/chest opportunities, chosen targets, path/time to pickup, acquired value, contested pickups, skipped opportunities.
- **Survival:** health/armor over time, elimination cause, recent incoming damage, time alive, zone damage, phase at elimination.
- **Economy:** resources gained/spent, upgrades, unused inventory at death, inventory at phase transitions.
- **Strategic:** placement, kills, survival time, score breakdown, phase transitions.

Log only state actually available to the bot or simulator, and label simulator-only privileged observations separately. Avoid expensive per-tick full-state dumps unless sampled or enabled for a diagnostic replay.

### 2.3 Failure taxonomy

Implement transparent, configurable heuristic tags, each with supporting evidence and confidence/limitations:

- Bad engagement / avoidable unfavorable fight.
- Poor aim or missed firing opportunity.
- Excessive exposure / positioning failure.
- Stuck or oscillating navigation.
- Inefficient farming or resource travel.
- Late-zone/rotation failure.
- Resource hoarding / under-utilization.
- Low readiness entering a fight.
- Unknown / insufficient evidence.

**Important:** A death may have multiple tags; tag frequency is not causation. Do not force one exclusive label or sum overlapping tags to 100%. Include severity and estimated score impact only where defensible. Provide a replay link or event window for every diagnosis.

### 2.4 Baseline report

Run a representative baseline set, ideally 50 games to start if runtime permits, with seed/opponent coverage. Produce:

- Mean, median, dispersion, distribution, and bootstrap uncertainty for total score; breakdown by opponent/map/game phase.
- Score components, survival/placement, combat, farming, movement, and resource utilization.
- Failure categories ranked by frequency **and** plausible score impact, with illustrative replays.
- 5–10 highest-value testable hypotheses and their minimal experiments.
- Observed simulation runtime and recommended speed improvements.

**Phase 1 gate:** The team can explain the top suspected score losses with real evidence, reproduce representative failures, and locate each relevant policy decision in code. Do not start broad optimization before this gate.

## 3. Phase 2 — Fast layered evaluation suite

Targets below are aspirations; benchmark actual feasibility and adjust.

| Level | Goal runtime | Purpose | Typical gate |
|---|---:|---|---|
| L0: microtest | 1–5 seconds | Pure decision functions, invariants, edge cases | Correctness and no regressions |
| L1: scenario | 5–30 seconds | Isolated combat/movement/farming situations | Relevant behavior metric improves |
| L2: short-match | 30–90 seconds | Multi-policy interaction under controlled conditions | No obvious strategic regression |
| L3: full local | Current ~10 minutes, optimize | Generalization and score comparison | Held-out paired improvement |
| L4: official | Up to six rolling submissions/hour | Real benchmark score and calibration | Update official evidence and champion |

These durations are not hard requirements. Optimize the simulator or test count before compromising fidelity.

### Scenario library

Build deterministic scenarios using state injection if available, otherwise replay checkpoints or a curated set of seeds:

1. **Combat:** equal-health duel, low-health fight, moving target, cover duel, multiple enemies, retreat vs engage, weapon/resource constraints.
2. **Movement:** wall avoidance, escape from enclosure, stuck recovery, pursuit, retreat, cover selection, zone crossing, field oscillation.
3. **Farming:** nearest vs highest-value loot, contested chest, farming under threat, transition from farming to combat, late-game resource scarcity.
4. **Strategic:** early/mid/late phase, shrinking zone, resource deficit, high-health/low-health late-game choices.

For each scenario define setup, seed, opponent policy/build, measurable outcome, timeout, and expected invariants. Avoid defining pass/fail thresholds from arbitrary guessed game mechanics.

### Microtests and oracle ablations

Add focused tests for decision functions and field calculations. Where simulator control allows, temporarily substitute an idealized subsystem (e.g. perfect target selection, idealized navigation, or ideal aim) to estimate upper-bound score opportunity. Label these as **diagnostic oracles**, never deployable strategies. Beware unrealistic oracle interactions.

## 4. Phase 3 — Experiment protocol

### Paired A/B/C exploration

Use when comparing two distinct challenger policies against the current champion:

- A = current champion, B = challenger 1, C = challenger 2.
- Run all on the same small development-seed panel and opponent builds.
- Compute per-seed score differences `B-A`, `C-A`, and `B-C` plus subsystem-specific metrics.
- Reject crashes, clear regressions, and poor behavior. Do not automatically pick the highest noisy mean.
- A/B/C costs ~50% more simulations than A/B on the same seed count; use it only when the added comparison is valuable.

### Paired A/B confirmation

- Compare selected challenger to champion on fresh, held-out seeds/opponents.
- Use an initial smoke batch (e.g. 5 pairs), screening (e.g. 15–25), and confirmation (e.g. 50+), adapted to runtime and variance.
- Record paired mean difference, median, per-seed win fraction, variability, uncertainty interval, and worst regressions.
- Repeated peeking/early stopping invalidates naive fixed-sample significance claims; use predeclared thresholds or sequentially valid inference for formal claims.
- Keep development, validation, and final holdout seeds distinct. Rotate or refresh the final holdout deliberately to avoid overfitting.
- Consider opponent mixes, not just a single top bot; include representative baseline, aggressive, defensive, and strong opponents if available.

### Parameter tuning (later)

Only after policy logic is validated, use small factorial/screening designs or Optuna/TPE if installed and suitable. Tune movement field weights, engagement thresholds, and farming utility parameters under paired seeds. Keep parameter experiments separate from code-logic experiments. Beware selection bias from testing many candidates on the same holdout.

## 5. Official submission pipeline

### Champion and challenger registry

Use Git SHA + config/build artifact hash as immutable identity. Maintain machine-readable `experiments/registry.jsonl` or SQLite if appropriate:

- Candidate ID, parent/champion SHA, hypothesis, changed subsystem, implementation notes.
- Local development and held-out results, opponent/seed panels, runtime, regression flags.
- Official submission timestamp, result, score components if returned, and benchmark version.
- Status: `experimental`, `screened`, `validated`, `queued`, `submitted`, `official_champion`, `rejected`.

Keep the champion identified by a Git tag or registry pointer; do not mutate a tested artifact. GitHub history alone is insufficient unless you record which SHA/config produced each score.

### Rolling six-per-hour scheduling

- Track the actual official submission timestamps and when each slot reopens (approximately one hour after its corresponding submission, per user-observed rules; verify if the platform exposes precise status).
- Target high utilization: submit a validated challenger when available.
- Otherwise use an intentional **information-gathering submission**: e.g. a meaningful strategy ablation, alternative policy, or reproducibility repeat that can calibrate local vs official behavior.
- Do not waste a slot on an artifact that is broken or incompatible. Never sacrifice the best-known champion merely to fill a slot.
- Queue at least one primary candidate and one backup where practical; do not block local development on an official result.
- If multiple tests run concurrently, use isolated Git worktrees/build directories and immutable config files. Ensure shared logs and artifacts cannot overwrite each other.
- Initially make official submissions a **manual, human-approved step** unless the repository and competition rules explicitly permit automation. Implement a ready-to-submit queue and schedule view first.

### Suggested operating loop

1. At slot availability, submit the best queued candidate or most informative diagnostic candidate.
2. In parallel, continue local baseline analysis and implementation on independent branches/worktrees.
3. When official results arrive, append them to the registry and compare against local expectations.
4. Promote to champion only according to a documented official-score rule; consider noise/repeatability.
5. Refresh experiment priorities based on new evidence.

## 6. Local-to-official calibration

For each official submission, retain:

- Exact submitted SHA/build/config.
- Local scores from a **consistent reference benchmark** and optionally additional specialized benchmark panels.
- Official score and metadata, timestamp, scoring/competition version.

Report:

- Scatterplot of local vs official scores, with build labels.
- Pearson and Spearman correlation (only when sample size is sufficient; display `n`).
- Bias, absolute error, rank inversions, and prediction residuals.
- Calibration stratified by opponent mix, strategy family, and phase if observable.
- A warning when the number of points is too small to interpret correlation meaningfully.

If local gains repeatedly fail to transfer, prioritize identifying simulator/scoring/opponent-distribution mismatch before tuning strategy further. Never use official outcomes to tune a hidden benchmark through assumptions about its internals.

## 7. CLI and deliverables

- `docs/evaluation_audit.md` and `docs/evaluation_methodology.md`.
- Versioned telemetry schemas, match summaries, failure diagnosis, and replay pointers.
- Baseline score/failure report with measured results and clear limitations.
- Reproducible microtests and scenario suite.
- Paired A/B/C screening and A/B confirmation commands with uncertainty reporting.
- Candidate registry, official-slot tracker, local-to-official calibration report.
- Minimal README explaining setup, commands, runtimes, and interpretation.
- Tests for score parsing, pairing, metric aggregation, reproducibility, and artifact identity.

## 8. Execution order and stop points

**Milestone 1 — Audit and profile (first):** Inspect repository, run existing tests, measure bottlenecks, write audit. No strategy changes.

**Milestone 2 — Instrument and diagnose:** Stable run IDs, telemetry, 20–50-game baseline (or feasible sample), top failure hypotheses, representative replays. Present findings to the team before optimizing.

**Milestone 3 — Make testing fast:** L0/L1 scenario harness, parallel execution where safe, caching/build reuse, structured reports. Prove runtime improvements with before/after measurements.

**Milestone 4 — Compare candidates:** Paired A/B/C exploration, A/B confirmation, held-out panels, automated candidate tracking.

**Milestone 5 — Close official feedback loop:** Rolling submission schedule, official-result recording, local-to-official plots, calibrated candidate ranking.

**Milestone 6 — Improve bot:** Pick the highest expected score-loss reduction per engineering minute, make minimal isolated policy changes, validate through the pyramid, and iterate toward 7+ official score.

### Acceptance criteria

- Can reproduce a test using exact SHA/config/seed/opponents.
- Can explain major baseline failures with evidence, not only score averages.
- Can test one subsystem substantially faster than the original full suite.
- Can compare A/B/C on common seeds and confirm A/B on unseen seeds.
- Can distinguish local improvements from official benchmark improvements.
- Can always recover the best-known champion while submitting experiments.
- Can identify when official submission capacity is available and select an informative candidate.