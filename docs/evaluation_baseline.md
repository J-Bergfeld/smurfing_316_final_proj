# Current policy on 20 fresh squad-proxy seeds

On arena/v2, the default bot averaged **3.90 placement points** (median 4, sample SD 2.79, bootstrap 95% interval for the mean 2.65–5.15). All 20 matches ended in elimination. Thirteen lethal hits were gun, five laser, one lightning and one zone. The strongest hypothesis to test is survival under fire from multiple mechs. These data do not establish whether changing engagement or retreat would improve placement in practice.

Panel 421100–421119 used the same scripted squad, default settings, bot source from d87f599 and simulator e322ffe. Full digests, per-match scores, timings, terminal state and event windows accompany the report. [Machine-readable evidence](evaluation_baseline.json)

| Local placement points | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Matches | 2 | 3 | 3 | 2 | 0 | 4 | 2 | 3 | 0 | 0 | 1 |

Mean finish was 12.1 of 16, with 1.65 credited kills and 189.27 simulated seconds alive. Subjects acquired a mean 3.95 cubes by death, held 1.70 upgrades and traveled 753 m of sampled XY path. The subject transport recorded three late and three invalid replies in total. Higher score by later terminal phase partly reflects survival itself. Phases 0/1/2/3/4 contained 3/5/9/2/1 deaths, averaging 0.33/3.00/5.22/5.00/5.00 points. All games used one map and one joint opponent mix.

| Final five-second evidence | Matches | Interpretation |
|---|---:|---|
| At least two distinct opposing mechs dealt damage | 16 (80%) | Direct evidence of pressure from multiple sources during the window. Simultaneous LOS and avoidability are unknown. |
| Fire command sampled at or below 35% HP | 16 (80%) | Continuing to request fire at low HP is common. It can be appropriate during retreat or a finishing opportunity. |
| Strong movement commands at both ends of a low-displacement second | 3 (15%) | Possible stall or reversal. Exact collision and intermediate command intent are unavailable. |
| Zone caused elimination | 1 (5%) | Direct terminal attribution with concurrent combat. |
| No rule matched | 1 (5%) | A known weapon can kill the subject without establishing a policy diagnosis. |

These are overlapping tags. Points attributable to each behavior are unidentified. Frequency gives combat scenarios priority. An impact ranking needs counterfactual paired matches. Seed 421101 took damage from slots 5, 8 and 11 after 199.05 s, ending at one point. The frozen replay reproduced its initial layout fingerprint, points and gun elimination. Seed 421110 had damage from three opposing mechs in the final window and died to zone at five points. Seed 421107 died to laser at zero points with insufficient evidence for any heuristic. Every diagnosis includes its underlying window in the JSON report.

## Minimal discriminating experiments

| Question | Decision point | Smallest comparison and endpoint |
|---|---|---|
| Does recovery break incoming pressure? | Controller.act, Movement.seek_cover | Replay the terminal pressure fixture to compare modes under the existing recovery toggle. Then pair full matches and compare repeated attacker damage and placement. |
| Does secondary-threat cover help? | Movement.combat_move | Use the existing spacing/cover scenario, then compare the existing position option on common seeds. Measure terminal attacker count, kills and points together. |
| Are gun commands at low HP useful? | combat.apply_weapon_control | Inspect readied gun state, trigger commands and credited mech hit events in a focused replay. A causal aim test needs gun discharge instrumentation or an isolated paired change. |
| Is zone timing costly outside its single lethal case? | Controller.act, geometry.zone_deadline | Pair the existing early_zone option with default; compare actual zone damage, kills and placement. |
| Do the three movement flags represent stalls? | Movement.navigate, apply_evasion_and_recovery | Inspect full observation/action windows on 421109, 421113 and 421118. Reproduce the obstacle geometry before changing path search. |
| Does early loot improve readiness before contact? | loadout.choose_objective | Test cube choice in the opening fixture, then compare existing farming options on pickups before first mech damage, survival and placement. |

## Cost

The 20 original matches took 144.77 s summed wall time. Mean was 7.24 s, median 5.67 s and nearest-rank p95 12.78 s. Mean startup through handshake took 1.02 s, including 0.115 s compiling geometry per match. Match simulation and decision-making dominate. Reuse compilation within a study and run focused decision windows for screening. Full seed pairing remains necessary for placement. The 20-game result and the historical official best of 5.17 concern different builds and fields. This panel provides no calibration pair for that official entry.
