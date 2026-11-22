# Trace review: 955e6bf practice baseline

Eight serial local squad-proxy matches, seeds 424000–424007, used the exact
`955e6bf` bot files with the environment in its Dockerfile. The external
simulator was `e322ffe872a52ef83a89ab194b6500edc0da36df`, clean at the time
of the run. This is a small diagnostic panel, not official practice; the local
proxy and timing can produce different trajectories and rankings. The raw
traces, events, results, and analysis are in the ignored local directory
`mech-testing/baseline-955-424000/`. Recompute with
`python3 tools/analyze_traces.py mech-testing/baseline-955-424000`.

The mean was 5.875 points and 3.5 kills, with scores 2, 11, 5, 1, 10, 4, 9,
5. There were three late and three invalid replies across the panel. All eight
subjects died: six fatal weapons were guns, one lightning, and one zone.
Six of eight had damage from at least two distinct opposing mechs in their
final five seconds. This supports investigating pressure from multiple enemies;
it does not prove simultaneous exposure, a preventable death, or a causal value
for a positioning change. Four had at least one possible one-second stall
defined by strong movement commands and little net displacement; reversals or
other movement can also satisfy that rule.

Only one match had any damage marked as rear damage in the final five seconds
(135 damage in seed 424003). That weakens a terminal-window case for tuning
rear-facing protection on this panel, but does not describe the rest of each
match or establish what happened in official games.

Listed actors can be remembered rather than currently visible. Likewise, a
ready gun and no fire command do not establish a missed opportunity: range,
line of sight, aim and the other weapon matter. Seed 424001 accounts for 2,566
of the 3,704 decisions with both a listed mech and a ready gun, so a pooled
trigger percentage would be misleading. Neither the local score nor these
counts establish an official practice improvement.

## A concrete navigation case and rejected probe

In seed 424001, the bot stayed at approximately `(82.16, -31.07)` as the
zone closed and died to the zone at 369.25 s. At 360 s its model considered
its precise current position not standable after growth, while its grid cell
was free and a route to the zone goal existed. Every first path shortcut was
rejected by `line_walkable`; the trace showed a zero movement command. Normal
stuck detection requires a nonzero command. This is a plausible model mismatch,
not proof that the same failure occurs in the official simulator.

A temporary prototype steered toward a nearby model-standable point whenever
the current ground position failed the model's standability check. The replay
used the same initial layout fingerprint and seed, but diverged much earlier:
it died to gunfire at 115.45 s and scored 7 versus baseline 11, with seven
kills in both. Neither run had late or invalid replies. One paired seed cannot
measure the general effect or isolate why the prototype lost; it does show the
condition activates outside the intended terminal case. The prototype is not
in the bot. The ignored directory `mech-testing/recovery-probe-424001/`
contains its patch and trace. Its movement file SHA-256 was
`04cd6db524bb1f6e6a7056b7f8b43d9414e3d92bfe6561c60611b02a74112a89`;
the baseline's was
`fecdc8273e0e763a6841e86c64a7baab9ef45aad25d80b180bd961a05216d6c8`.

Next, inspect repeated multi-attacker windows and distinguish enemy locations,
target availability and movement choices before tuning exposure weights. For
navigation, first make an isolated state fixture that reproduces the invalid
starting position and checks that any escape only activates after sustained
zero-progress navigation. Test a counterexample where contact with cover is
intentional. Do not promote the prototype based on this one replay.

## Urgent-zone-only recovery screen

A second, separate prototype was tested only in a frozen copy of `955e6bf`.
It looked for an adjacent standable point only when urgent zone navigation had
returned zero movement for one second, the mech remained grounded and nearly
stationary, and the collision model rejected its current position. Its aim was
to avoid activating during ordinary combat or intentional cover contact. This
is still an approximate collision escape; a standable endpoint alone does not
guarantee an unobstructed route there.

On the same eight seeds and initial layout fingerprints, baseline scores were
`2, 11, 5, 1, 10, 4, 9, 5`; candidate scores were `3, 9, 6, 1, 10, 4, 9, 5`.
Mean paired difference was **0.00 ± 0.33 standard error**; this small screen
does not rule out a material benefit or harm. Baseline had three late and
invalid replies; candidate had none, so timing can affect the comparison.
On the diagnostic seed 424001, the first action difference was at 338.4 s at
the original position: baseline stayed still, candidate moved south, and the
candidate later died to gunfire for 9 points versus baseline's zone death for
11. The behavior achieved the immediate movement mechanism but did not prove
a placement benefit. On seed 424000 the first action difference coincided with
a late baseline reply; seed 424002 diverged at 209.6 s without an observed late
reply on that decision, so the cause of its trajectory change is unresolved.

Decision: do not enable or submit this prototype. It is unproven and needs an
isolated state scenario, swept-body clearance checks, a cover-contact
counterexample, and a larger timing-controlled comparison before promotion.
Traces, match results and the patch are retained in the ignored local directory
`mech-testing/zone-recovery-424000/`.
