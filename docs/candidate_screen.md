# Recovery and positioning on fresh squad-proxy seeds

## Study design

A is the current default. B enables the existing recovery behavior at low HP. C enables the existing readiness and cover behavior in squad fights. Both address the multiple-attacker pressure observed in 16 of 20 baseline eliminations. Candidate settings are in experiments/squad-screen.json. This study uses seeds 422100–422114, absent from prior local panel manifests. Each seed supplies one matched initial layout for all three configurations. The runner rotates A/B/C order and executes full games serially.

The primary endpoint is the paired difference in placement points relative to A. Before running, we selected a fixed 15-seed development screen. Advance at most one challenger if its mean difference is positive, it improves more seeds than it worsens, and it completes all games. Break a tie on mean difference by fewer late replies, then fewer invalid replies. Record kills, survival, terminal cubes, incoming damage, timing faults and the bootstrap interval alongside placement. A selected challenger receives a fresh 50-pair confirmation on 423100–423149. Treat a confirmation interval crossing zero as inconclusive. Preserve the default throughout this study.

Run from the repository root with a fresh output directory.

```sh
SIM="competitors/updated/$(python3 -c 'import json; print(json.load(open("competitors/lineup.json"))["simulator"])')"
python3 tools/paired_panel.py --sim "$SIM" --spec experiments/squad-screen.json --offset 100 --seeds 15 --out mech-testing/m4-screen-422100
```

## Result

Keep A as the local reference. Recovery tied the default on mean points and lost more seeds than it won. Positioning averaged 0.40 fewer points. Neither qualified for held-out confirmation under the predeclared rule.

| Configuration | Mean points | Paired change vs A (95% bootstrap interval) | Better / tied / worse vs A | Mean kills | Mean survival, s | Late / invalid replies |
|---|---:|---:|---:|---:|---:|---:|
| A · Default | 5.53 | — | — | 3.20 | 200.01 | 0 / 0 |
| B · Recovery | 5.53 | 0.00 [−1.00, +1.00] | 3 / 8 / 4 | 3.13 | 208.35 | 5 / 5 |
| C · Positioning | 5.13 | −0.40 [−1.27, +0.53] | 3 / 6 / 6 | 2.67 | 204.66 | 3 / 3 |

B−C was +0.40 points with a 95% interval of [−0.67, +1.40]. Recovery recorded multi-attacker damage in the final five seconds of 6 of its 14 eliminations, compared with 8 of 14 for default and 9 of 15 for positioning. B survived 8.34 seconds longer per game on average but recorded 290 more incoming damage per game. Damage totals accumulate across different survival durations. The timing counters also differed, so the screen cannot isolate the effect of a change in tactics from timing variability.

All 45 games completed on simulator e322ffe, with identical initial layout fingerprints across all three candidates on each seed. The bot code came from working tree 4ccf499, with evaluation files dirty. All three frozen bot-content hashes matched, and the study changed only candidate environment settings. The comparison covers one local squad and map. The historical official results and this panel use different fields.

The [machine-readable report](candidate_screen_422100.json) preserves all paired seed differences, candidate identifiers, frozen context hashes and dispersion estimates. Per-seed summaries, full telemetry, source archives and the candidate registry are under mech-testing/m4-screen-422100. Recompute terminal tags with:

```sh
for label in A B C; do
  python3 tools/diagnose.py "mech-testing/m4-screen-422100/$label" --out "/tmp/m4-422100-$label.json"
done
```
