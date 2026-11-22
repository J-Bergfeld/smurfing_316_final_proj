# Builders-4 follow-up screens

These are local squad-proxy screens, not official results. The comparison
configuration uses the `955e6bf` gameplay settings (notably supply drops off),
while both builds use the then-current frozen source. The official 5.47
score is not paired with these matches. The later combined threat-aware cube
and upgrade-value implementation is enabled by default and requires a new
comparison; these historical screens did not test that combined behavior.

| Candidate | Seeds | Control / candidate | Paired delta | 95% bootstrap interval | Decision |
| --- | --- | --- | --- | --- | --- |
| Safe combat cubes, initial snapshot | 422500–422515 | 4.6875 / 5.125 | +0.4375 | −0.6875 to +2.125 | Inconclusive; one +11 match accounts for much of the gain. A later work-limit change means the current bytes have not been screened. |
| Quiet opening scan | 422600–422615 | 4.9375 / 4.625 | −0.3125 | −1.25 to +0.5625 | Do not promote; investigate discovery and survival before revisiting. |
| Abandon stalled loot | 422700–422715 | 5.8125 / 5.875 | +0.0625 | −0.5625 to +0.8125 | Inconclusive; ten pairs tied. |
| Route-based zone urgency | 422800–422815 | 4.5 / 4.5 | 0 | −0.3125 to +0.25 | Do not promote; 13 pairs tied and the candidate had two late/invalid responses. |
| Combined threat-aware cubes and upgrade value | 422900–422915 | 5.1875 / 5.25 | +0.0625 | −1 to +1.375 | Inconclusive; candidate had four late/invalid responses versus one for control. Enabled by request, but requires timing and official evaluation. |

Reports: [cube screen](builders4-safe-cubes-screen.json),
[scan screen](builders4-opening-scan-screen.json),
[stalled-loot screen](builders4-stalled-loot-screen.json),
[zone screen](builders4-route-zone-screen.json),
[combined cube screen](builders4-threat-cube-upgrades-screen.json). The cube screen had one late and invalid response in each variant; the scan
screen had none. The stalled-loot control had two late and invalid responses,
and its candidate had none. Tests were run concurrently during part of the cube screen,
which can affect the wall-clock-limited controller. Frozen inputs and raw
results are in `/tmp/safe-combat-cubes-screen` and `/tmp/opening-scan-screen`;
these temporary directories are not durable. Specs in `experiments/` preserve
the settings. Neither screen establishes the direction of an official effect.

The branch already has five full-suite failures concerning finish approach,
practice routing and reload cover; the same five occur on untouched `b047a28`.
The focused controller tests and protocol replay should be rerun after changes.

After the combined cube screen, the safety check was changed to share a 5 ms
per-action budget. It stops between geometry calls and retains only fully
checked candidates. Individual geometry calls are not preemptible, so this is
a cooperative budget rather than a hard wall-clock limit. The combined screen
above predates this change; no paired screen was rerun.
