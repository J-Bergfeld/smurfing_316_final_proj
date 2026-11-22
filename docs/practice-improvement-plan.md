# Practice improvement: implementation and validation plan

## Objective and evidence

Improve mean official practice placement enough to qualify, starting from reported **5.17 at `4991fa6` with default settings**. The practice field is 15 cooperating house bots: they share vision, do not fight one another, and send more hunters as their number falls. A kill generally improves placement but can intensify the following encounter. The final qualifying round is FFA; this plan prioritizes practice and does not claim the same tactics will transfer. Check the current [official track rules](https://www.joinbuilders.org/buildathon/tracks/builders) and submission limit before an official run.

Work in the order below unless baseline traces show another failure has greater placement impact. These are independent hypotheses, not a bundle to ship together. Record implementation, outcomes, and decisions in the [experiment index](experiments.md); preserve prior work in the [history](experiments-history.md). The local squad proxy is an approximation of house behavior, not an official predictor.

## Shared measurement and decisions

- **Establish baseline first.** Use `4991fa6` and default environment; capture traces for a representative selection of existing squad seeds including early deaths, prolonged fights, and late/invalid replies. Run at least one control-versus-itself comparison on matched seeds to estimate timing noise. Record simulator revision, dirtiness, bot hash, host conditions, seed, slot if available, and raw per-match outcomes. Do not assume a proxy behavior occurs officially.
- **Trace the mechanism.** Derive metrics from existing observations, events, actions, and end records where possible: HP and time, damage taken/dealt and weapon, kills, cubes/upgrades, position and zone state, movement commands, visible threats, shots/hits, late/invalid actions, and elapsed response time. Record unobservable quantities as unknown; damage events and sampled actions do not always reveal every shot, cause of death, hidden enemy, or collision. If necessary add diagnostic tooling that does not change submitted actions or protocol output.
- **Keep variants attributable.** Implement each candidate behind an explicit factor, defaulting to the unchanged parent during screening; record exact settings. Keep any diagnostics and candidate logic within the existing action deadline and preserve protocol behavior. A later combined candidate requires its own identity and test.
- **Screen before submission.** First run targeted scenarios with observable expectations and a plausible counterexample. Compare candidate and parent on the same 16–32 fresh squad seeds where feasible, reporting mean placement, paired delta and SE, per-seed outcomes, survival, kills, late/invalid counts, and mechanism metrics. Rotate held-out seeds and expand close or consequential results. The runner evaluates variants sequentially; repeat a reversed-order or control comparison if load or lateness differs. Investigate timing discrepancies before interpreting a score difference.
- **Decision rule.** Reject a candidate that fails its mechanism scenario or causes a clear repeatable placement regression. Investigate and retest mixed or uncertain results; a favorable point estimate alone is not promotion. Consider an official test when the mechanism is demonstrated, local results are not materially adverse after timing checks, and the candidate is informative enough to justify a submission. Promote the practice champion only on a better official practice result; retain the previous best entry. A tie ranks the earlier submission first. If interaction is plausible, predeclare a matched 2×2 test before selecting a combined policy.
- **Submission gate.** Run all relevant unit and scenario checks, protocol conformance, and the documented restricted Docker check using an exact clean commit. If Docker or the platform is unavailable, record the blocker and do not represent the gate or submission as completed. Record official commit, factors, submission time, run ID, score and comparator; use official results as authority, not the local proxy. Verify the current platform limit and cutoff.

## P01: Recovery and disengagement

**Current behavior and opportunity.** Squad retreat is based on recent losing conditions and can expire roughly 1.5 seconds after the condition stops. Regeneration begins after five seconds without dealing or taking damage, only inside the zone. Shooting while withdrawing can prevent healing. Supply drops grant full health and energy plus three cubes after four uncontested seconds, but are publicly visible.

**Candidate.** Add a squad recovery state that chooses reachable cover, avoids unnecessary damage-dealing while seeking a healing window, and re-engages when sufficiently recovered or when healing is no longer feasible. Preserve immediate zone escape, lethal threats, and an urgent finish as competing priorities. Treat supply-drop pursuit as a separate factor, only when its travel, zone, health, and contest risks support it; do not bundle it with basic recovery.

**Counter-hypothesis.** House shared vision and pursuit may deny five safe seconds. Retreat may expose the rear armor multiplier, lose a finishable kill, or surrender zone position. A drop can attract enemies rather than heal us. Proxy pursuit may differ from the house squad.

**Scenarios and measurements.** Verify that a damaged bot with cover can stop dealing damage for the regeneration delay and resume once recovered; verify that an exposed bot under pursuit or a closing zone does not wait indefinitely. Test a safe landed drop separately from a contested or unreachable one. Measure successful healing windows, HP recovered, rear hits, time exposed, kills after recovery, zone damage, survival, and placement. A recovery state that rarely heals or sacrifices placement is not supported merely because it lasts longer.

## P02: Efficient farming

**Current behavior and opportunity.** The integrated objective scorer uses fixed values and approximate straight-line distance for drones, crates, cubes, and weapons; in squad combat nearby cubes can override combat movement. Each drone drops two cubes, crates drop one and can yield a weapon, and cube thresholds provide upgrades. The existing legacy economy trial was small and does not establish the outcome for the integrated policy.

**Candidate.** Compare the existing policy with selective farming that estimates acquisition time, expected health cost, route/zone feasibility, upgrade thresholds, and likely weapon benefit. Gate cube detours during combat by exposure and immediate threat. Compare conservative and more aggressive farming as distinct levels; do not assume distant laser pursuit or all cubes are always valuable.

**Counter-hypothesis.** NPC damage, travel time, larger cube-scaled hitboxes, and delayed engagements can exceed the value of upgrades. Local drone and loot behavior may differ from official practice; a higher cube count alone is not success.

**Scenarios and measurements.** Contrast a nearby low-risk drone with a distant obstructed one; test a cube across enemy fire and a crate near a valuable upgrade threshold. Measure time and HP at first sustained fight, time to upgrades and useful weapons, cubes, farming damage, detour time, kills, survival, and placement. Keep the variant only if evidence supports better combat readiness without offsetting placement losses.

## P03: Anti-squad positioning

**Current behavior and opportunity.** Combat movement uses fixed preferred ranges that depend on loadout and squad mode, and squad logic can treat laser or lightning as ready without modeling the complete timing of the next useful shot. Buildings block shots even when enemies share vision. The current non-squad laser-charge evasion is not applied in the same way in squad mode.

**Candidate.** Score reachable combat positions by incoming firing angles, cover, path exposure, weapon range and actual readiness, while preserving a viable line of fire and zone escape. Compare this with the existing desired-distance policy; test laser evasion separately so its contribution is identifiable. Use only observed or explicitly tracked information, not hidden simulator state.

**Counter-hypothesis.** Cover may obstruct our shots, trap the bot, let enemies surround it, or postpone kills until the zone closes. Approximate line-of-sight and enemy behavior may distort proxy results.

**Scenarios and measurements.** Compare open space, a corner with two converging enemies, a gun reload under pressure, and an aimed charging laser. Measure visible enemy firing angles as a proxy rather than true simultaneous damage potential, damage received/dealt per engagement, time with a viable shot, rear hits, kills, and placement. Require a demonstrated reduction in exposure without a damaging loss of offensive output.

## P04: Aiming and kill conversion

**Current behavior and opportunity.** Gun lead and muzzle position use timing and geometry approximations; weapons share the torso and target selection favors recent and low-health targets. `BOT_GUN_AIM_CHECK=actual` is opt-in and was not used in the 5.17 official result. Its earlier squad screen was inconclusive and had uneven timing failures.

**Candidate.** Audit motion prediction, actual torso slew, muzzle origin and shot clearance against the protocol and controlled traces. Change one identifiable mechanism at a time: first validate the existing shared-aim factor, then test prediction or target-switching adjustments if traces show a recurring failure. Preserve the existing factor name and parent identity for comparisons. Use actual weapon cooldown and readiness in any target-value estimate.

**Counter-hypothesis.** Acceleration, collision, imperfect enemy visibility, simulator physics, and two physics ticks per action can make a more elaborate prediction worse. Aiming at a different target or waiting for perfect alignment can reduce damage or expose the bot. Hit events and actions may not reveal the exact number of rounds fired.

**Scenarios and measurements.** Test crossing, approaching, accelerating, partially covered, and near-lethal targets; include a laser overriding gun aim and a target becoming obstructed. Measure confirmed hit events, damage by weapon, ammo changes or other defensible shot estimates, time to kill, target switches, incoming damage, and placement. State any metric denominator limitations. Do not infer official benefit from a unit scenario or the previous FFA result.

## P05: Navigation and zone pressure

**Current behavior and opportunity.** Zone urgency and loot selection use straight-line distance and multipliers while movement uses approximate baked geometry and time-limited search. Roof edges, bridges, and collision are approximations. A prior roof-descent test was too small to establish a match benefit.

**Candidate.** First measure navigation stalls, unreachable-objective time, zone damage, and detours in baseline traces. If frequent enough to matter, test route-aware travel-time and reachable-goal estimates, plus targeted roof descent or recovery improvements as separate factors. Bound navigation work within the action deadline and retain a safe fallback if a search cannot finish.

**Counter-hypothesis.** Stalls or zone deaths may be uncommon, more search can cause late actions, and conservative detours may lose fights or pickups. The local map model may not match the official engine's collision behavior.

**Scenarios and measurements.** Test roof-edge descent, narrow gaps, a bridge or overhead obstruction, an objective behind a building, and a closing zone requiring a detour. Measure commanded-but-unproductive movement, time stalled, route completion, zone damage, response-time percentiles, late/invalid actions, survival, and placement. If baseline traces show little exposure, defer the implementation instead of optimizing a rare theoretical failure.

## Sequence and interactions

Start with baseline trace and timing characterization, then P01, P02, P03, P04, and P05. Revise that order if evidence identifies a more frequent or damaging failure. Consider a predeclared 2×2 for recovery × positioning or farming × navigation only after the individual factors show plausible benefits. Use new seeds for confirmation, document uncertainty and rejected ideas, and make official submissions only after the required gates. Preserve the best official practice entry throughout; FFA testing can resume when the qualification objective allows.
