# Practice strategy: prepare the next fight

## Objective and evidence

Improve official practice placement from the known 5.23 build `835d4a7`. Practice opponents cooperate and send increasing numbers of hunters as the field thins, but the published rules do not specify an exact trigger or the position of hidden hunters. Five placement points are not necessarily five kills: opponents can die to the zone. Do not infer an enemy roster, active-hunter count, or deterministic wave from the local proxy.

The hypothesis is that the bot needs a good position **before** several enemies can shoot, not just a reaction after low health. Proxy traces motivate testing that hypothesis but cannot establish its frequency in official matches. Controlled scenarios establish behavior; only official practice measures placement. Preserve `835d4a7` and its FFA behavior as the reference.

## Candidate A: prepare an escape corridor

Keep the existing weapon control, target selection, upgrade order, normal strafe and current emergency dodge. Replace the first practice positioning trial only: the policy plans a short route near cover while fighting one hunter, and uses it if the position is still safe and offensive. It does not wait for health to drop or hold fire to heal.

### Information and pressure

Use the current observation, recent visible tracks, recent damage source IDs and bearings, weapon readiness, actual body dimensions, zone geometry and map. Treat sounds as uncertain bearings, never as actor IDs or certain line of sight. Track observed or recently damaging opponents, with time decay; unknown opponents may exist. `obs.alive` is a rough urgency signal, not an exact count of current hunters. A reasonable starting activation condition is practice mode with a visible target and either `alive <= 12` or a second recent/visible threat; tune it only as an identifiable experiment. Immediate multi-source danger can activate earlier. In this baseline, practice mode is inferred after 20 seconds and switches away after unexplained deaths; preserve that behavior for the first trial.

### Corridor selection

Use the existing indexed corner and passage candidates in `PositionalField`, including the current position and existing path. For each candidate within roughly 25–40 m, require:

1. A verified size-aware route with a clear next step and enough zone margin for travel plus a short escape buffer. Check route samples, not merely the endpoint. Reject stale, unreachable, rooftop-only or body-size-invalid paths.
2. A viable shot on the current target at or along the route, or a short measured interval to regain one. Never accept indefinite hiding as a good position.
3. At least one verified exit from the candidate toward another walkable cell or the next zone. Reject dead ends and routes whose only exit crosses known incoming lines.

Score remaining routes for expected number of exposed firing angles along the approach, time with a usable shot, time to reach the position, usable exit, zone margin and exposure to uncertain sound bearings. A known second attacker has a stronger penalty than an anonymous sound; overlapping sounds do not become separate confirmed hunters. Give current position a real score and require a meaningful improvement before moving. The values are tunable engineering parameters, not claims about damage probabilities.

Pre-plan with one target, but take a proactive route only when it preserves offense and is not materially more exposed than staying. On a newly observed second threat, rescore and use an already verified route if it shields the extra firing angle. Replan on new attacker, body-size or zone changes, an invalid step, or loss of target; otherwise retain a route briefly to avoid oscillation. Check movement on every tick. Do not chase a cube across a danger line merely because it is nearby; defer or permit it only if it lies on the selected safe route. This gate is part of candidate A and must be measured, not presented as an independently proven benefit.

### Priority and failure handling

The decision order is stuck recovery, imminent projectile/shell dodge, urgent zone escape, corridor, existing combat movement and existing objective selection. Weapon firing stays active when there is a valid shot; preserve the target chosen by the existing controller. Current urgent-finish logic can override a corridor only when the target is visible and the action does not create an immediate zone or collision failure. Do not enter a cover/recovery state solely because the corridor has no shot.

Bound planning to a shared 3 ms budget inside the existing controller deadline, run at most every 0.5 seconds unless materially invalidated, and examine at most 24 endpoints and three route candidates initially. Timeouts return the last still-verified step or the existing combat action; never return an unverified route. These are starting limits, not performance guarantees. A wall-clock timeout must not leave half-updated route state.

## Candidate B: early power acquisition

Test separately on `835d4a7`; do not combine with A until both have official results. Before sustained combat, value a nearby, reachable drone that yields two cubes and is safe to attack. Estimate travel and kill time, visible threat, remaining health, zone deadline, cube proximity and whether those cubes cross an upgrade threshold. Prefer an immediately reachable weapon or cube where appropriate. Stop farming when an actual threat requires combat or the zone requires rotation. Avoid distant, blocked targets and recognize that more cubes increase body size as well as health and damage. Keep the baseline's weapon ranking and target selection initially.

This is a new selective farming policy, not the earlier blanket prohibition on combat cube collection or the rejected laser-rush policy. Its risk is losing time and health before the first fight. It is successful only if it improves official placement, not merely cube count.

## Verification and official sequence

For A, create focused scenarios covering: one visible hunter and a safe corridor; a second shooter arriving before low health; the shortest route crossing both firing lines; a tempting cube across that crossing; an exit blocked by growth; no valid corridor; and an urgent zone or incoming shell. Include a near-lethal target and a case where the only cover destroys our firing line. Verify selected route, next-step safety, target/fire preservation, fallback and deadline. Use a separate low-cost recorded replay to verify action latency; a static replay does not prove match performance.

For B, test a nearby clear drone, an obstructed or distant drone, an immediate threat, an upgrade threshold, and a zone deadline. Verify pursuit, fire and cancellation behavior.

Build each trial independently with explicit settings on `835d4a7`, run the baseline's relevant tests and the restricted Docker protocol check, and submit exact clean commits. Record run IDs, scorer version, score and any available per-match replays. The official best stays the champion; a single noisy score does not quantify the true effect. Four or more practice slots per hour allow a baseline repeat and distinct A and B tests; use the live quota. If an official result is promising, repeat it before drawing strong conclusions. A+B requires a separate candidate and result.

Do not wait for proxy placement to select the candidate. Proxy runs may cheaply detect crashes or obvious mechanics errors, but previous proxy rankings and official results disagree. If official replays are available, analyze the 10–20 seconds before deaths for health, simultaneous attackers, firing angles, damage, movement and zone; absence of official telemetry must be marked unknown.
