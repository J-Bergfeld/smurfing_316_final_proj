# Mech Royale practice brainstorming

Goal: improve placement against the house bots during builders-4 practice. The
reported 5.47 score for `955e6bf` is the reference, not a prediction for the
current branch. Practice uses fresh private seeds, so official scores are not
paired. Local squad-proxy comparisons are useful screens, not proof of an
official improvement. Jack is handling reloading and engagement policies;
coordinate any changes that touch his work.

These are hypotheses, not established gains. Priorities reflect potential
impact and confidence, not estimated score increases. The [experiment
record](builders4-followup-screens.md) contains local results and limitations.

## Current priorities

1. **Threat-aware cube collection and upgrade value.** Implemented and enabled
   on `sam` in `bc36dac`. Screen the final 5 ms-budget version when authorized;
   the earlier combined screen was inconclusive and had more late responses.
   The current positional field can take precedence over combat-cube detours.
2. **Opening information and economy.** Investigate discovery, first weapon,
   first upgrades, and health costs. A simple scan was screened and not promoted;
   test improved farming value separately.
3. **Route-aware zone movement.** Measure actual late rotations, detours and
   zone damage. The initial route-time probe was flat locally and is off.
4. **Movement against crossfire.** Measure the existing field's use, incoming
   firing lines, route exposure, and own firing uptime before revising it.
5. **Stalled or unreachable objectives.** Measure zero-output and physical
   stalls separately. The initial stalled-loot candidate was inconclusive and
   is off.

## Economy and looting

1. **Post-kill cubes.** Prefer short, safe routes to cubes when their health,
   damage and upgrade value outweighs exposure. Do not assume every pile is a
   kill drop. Implemented in a conservative form; the local screen is
   inconclusive. Measure collection time, incoming damage and subsequent survival.
2. **Imminent thresholds.** Increase cube value when it immediately grants an
   upgrade, using `hello.config.cubes.upgrade_thresholds`. Implemented; the
   multiplier is a hypothesis to tune, not a measured optimum.
3. **After the stat cap.** Reduce long detours once direct stat gains cap at 10,
   but preserve safe pickups that immediately unlock an upgrade. Cubes continue
   increasing body size. The combat-detour gate implements this narrow case.
4. **Cluster collection.** Plan a short route through several visible cubes
   instead of repeatedly selecting the closest; stop if risk or zone urgency
   rises. Test compact piles against scattered and contested cubes.
5. **Acquisition time.** Rank opening objectives by route time, time to destroy
   a crate or drone, expected loot and progress toward an upgrade. Avoid treating
   straight-line distance as the whole cost.
6. **Route-compatible farming.** Prefer multiple useful items along the same
   route, while limiting commitment to stale or dangerous objectives.
7. **Opportunistic crates.** Investigate whether a crate can be damaged while
   already traveling past it. Firing and ammo use overlap Jack's work; coordinate
   before changing weapon behavior.
8. **Fresh item information.** Validate remembered items when approaching and
   avoid chasing stale loot. Absence outside the vision wedge is not proof that
   an item disappeared.
9. **Rooftop loot.** Consider high-value roof items only with a feasible ascent,
   energy reserve, zone margin and verified exit. The active ground objective
   selector currently excludes elevated items.
10. **Contextual weapon pickup.** Compare fixed laser-first ranking with values
    based on range, current weapons, enemy equipment, phase and equip delay.
    Swapping may interrupt useful damage.
11. **Upgrade selection.** Test state-dependent defense, movement and weapon
    upgrades against the fixed order. Change one preference at a time; previous
    magazine tests under old scoring did not establish a gain.
12. **Sensor upgrades.** If traces show missing information is costly, test
    greater vision and sound accuracy against direct combat upgrades.

## Information and the opening

13. **Quiet-opening scan.** Survey unseen sectors without overriding an active
    threat. A simple sweeping candidate was −0.31 locally over 16 pairs with a
    wide interval; it is off. Investigate discoveries and survival before retesting.
14. **Selective drone farming.** Compare the value of two cubes against drone
    damage, travel, noise and delayed encounters. An earlier drone-preference
    candidate scored 4.91 versus 5.47 for its independent-seed comparator;
    this does not establish causality.
15. **Sound-informed movement.** Use sound bearing, age and distance band to
    bias scouting or route risk. Avoid double-counting visible opponents and
    never treat anonymous noisy sound as a known position.

## Combat positioning and movement

16. **Isolate firing lines.** Seek positions that block secondary attackers
    while preserving a shot at the selected target. Measure own firing uptime
    and incoming damage rather than rewarding cover alone.
17. **Exposure along the route.** Penalize time crossing multiple firing lines,
    not just exposure at the destination. The current positional field already
    approximates this; inspect its failures before replacing it.
18. **Unseen damage direction.** Use recent damage bearings to bias movement
    toward cover, with uncertainty about the shooter's location. Avoid getting
    trapped or abandoning a good firing position.
19. **Rear armor while moving.** When there is no active shot, consider facing
    the likely damaging threat; rear hits deal more damage. Torso aim also
    controls vision and shooting, so coordinate with Jack.
20. **Laser-charge evasion.** Test earlier movement across a visible charging
    laser's projected line. False positives and movement into obstacles can cost
    more than they save.
21. **Energy reserve.** Balance boost, lightning, roof escape and zone travel;
    avoid spending all energy just before an escape. Reserving too much can
    reduce speed or damage.
22. **Boost open crossings.** Spend energy to shorten exposed travel when the
    destination is reachable and useful. Compare damage saved to energy spent.
23. **Strafe inertia.** Check whether rapid reversals prevent acceleration and
    make the bot easier to hit. Use command and velocity traces before changing it.
24. **Channel pursuers.** Favor cover that funnels several bots into one
    approach while retaining an exit. Test against actual proxy behavior; a
    corner can become a trap.
25. **Combat roofs.** Investigate roof firing positions that improve sightlines
    and limit ground pursuers. Account for ascent exposure, energy, enemy fire,
    zone timing and descent.
26. **Plan the roof exit first.** Reject a roof when no safe descent is known,
    particularly before a shrinking circle or after growth changes clearance.
27. **Recovery windows.** Measure when reaching cover can actually create the
    five damage-free seconds needed for regeneration. Earlier broad recovery
    screens were inconclusive; lost damage and pursuit remain real risks.

## Zone and navigation

28. **Route-aware rotation.** Estimate time using a complete route, detour
    uncertainty, current speed and body size instead of only straight-line
    distance. The first bounded route-time probe was flat locally and is off.
29. **Safe circle entry.** Prefer a reachable point just inside the next circle
    with cover and firing lanes, rather than automatically traveling farther
    toward the center. Avoid sacrificing useful fights by rotating too early.
30. **Path failure detection.** Distinguish incomplete search, no path, blocked
    route and physical stall. The opt-in stalled-loot probe abandons repeated
    zero-output objectives; its screen was inconclusive.
31. **Route cost for loot.** Feed estimated path length into the top few loot
    candidates so a nearby item across a wall does not dominate a reachable one.
    Keep extra searches bounded.
32. **Growth-aware path invalidation.** Recheck clearance and invalidate stale
    routes as cubes enlarge the body. Existing code clears movement caches on
    size change; look for remaining failures before expanding it.
33. **Path cache and fallback.** Cache only while the goal and relevant
    geometry remain valid, and retain a safe low-cost fallback when searches
    run out of time. Measure repeated searches and zero-movement intervals.
34. **Deterministic field search.** Profile how often wall-clock limits leave
    the positional field without a verified candidate. Reduce timing-sensitive
    variance without consuming the action budget or increasing late replies.

## Supply drops

35. **Timed staging.** Arrive shortly before landing when the full heal,
    energy and three cubes justify travel, wait and risk. Compare drops off,
    existing pursuit and staging independently. The blocked-route candidate's
    5.10 official result bundled changes and used independent seeds.
36. **Contest and progress.** Use observed contest state and capture progress
    to decide whether to stay or leave. Avoid claiming knowledge of unseen
    enemies; account for the zone and the risk of waiting in the ring.

## Experiment discipline

Freeze the exact candidate and control configuration. Start with targeted
scenarios, then use paired local seeds and fresh holdouts. Track placement,
survival, kills, cubes, damage, route stalls and late/invalid actions. Avoid
running other CPU-heavy work during timing-sensitive matches. Retain the
best official entry separately, and record each submission's commit, settings,
scorer version and result. A small official score difference on independent
seeds is not a causal measurement.
