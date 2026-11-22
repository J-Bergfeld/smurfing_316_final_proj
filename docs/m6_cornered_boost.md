# Ground boost during a cornered dodge

The baseline recorded gun eliminations in 13/20 matches. On the 50-frame recorded pressure fixture the controller entered cornered mode on every frame. Movement already steers away from projectiles, but only the charging-laser path requests boost. The simulator increases horizontal boost speed on the ground and spends energy while moving. The opt-in challenger requests boost when the existing dodge vector is nonzero, the subject is cornered and grounded, and energy exceeds the existing 25-unit threshold. The counter-hypothesis is wasted energy or faster movement into another attack. The existing default remains the reference.

Primary outcome is placement points. Before examining match outcomes, select 15 fresh development pairs on 422200–422214. Advance if all matches finish, mean paired delta is positive and gains outnumber losses. If qualified, run 50 held-out pairs on 423200–423249. Require a positive lower 95% paired bootstrap endpoint to recommend an official challenger. The 7+ target requires an official result.

```sh
python3 -m unittest discover -s tests -q
python3 tools/scenario.py run tests/fixtures/terminal_pressure.json.gz
BOT_CORNERED_BOOST=1 python3 tools/scenario.py run tests/fixtures/terminal_pressure.json.gz
BOT_CORNERED_BOOST=1 python3 check/check.py -- python3 -u main.py
SIM="competitors/updated/$(python3 -c 'import json; print(json.load(open("competitors/lineup.json"))["simulator"])')"
python3 tools/paired_panel.py --sim "$SIM" --spec experiments/cornered-boost.json --offset 200 --seeds 15 --out mech-testing/m6-screen-422200
```

The challenger passed the protocol checker with 300/300 on-time valid replies. The fixture produced 39 boost requests for the challenger versus zero for the default. Both selected cornered on 50 frames and requested fire on 24. This measures changed actions on fixed observations.

## Development screen

A averaged 4.13 points and B averaged 4.67. The paired gain was +0.53 (95% bootstrap interval −0.13 to +1.27). B improved six seeds, tied seven, and worsened two. Its largest gain was four points on 422208 and its largest regression was two on 422204. It averaged 0.47 more credited kills and 7.02 more simulated seconds alive, with one late and one invalid reply versus zero for A. The predeclared rule advanced B to held-out testing. [Per-seed screen results](m6_screen_422200.json)

```sh
python3 tools/paired_panel.py --sim "$SIM" --spec experiments/cornered-boost.json \
  --confirm mech-testing/m6-screen-422200/report.json --offset 200 --seeds 50 --out mech-testing/m6-confirm-423200
```

## Held-out confirmation

All 50 pairs completed on seeds 423200–423249. Each pair had identical starting layout fingerprints. Default averaged 4.62 placement points and cornered boost averaged 4.52. The paired difference was -0.10 points (95% seed-bootstrap interval -0.50 to +0.34), with 9 better, 27 tied and 14 worse. The local confirmation did not meet the predeclared positive lower-bound criterion. [Per-seed held-out results](m6_confirm_423200.json)

## Official result

The user reported **4.90** for submitted commit `26db76cd87fc2383957d5d9a09d02f89be325db6` with cornered boost enabled in its Dockerfile. This is 0.27 below the recorded champion (5.17) and 0.38 above this candidate’s local held-out mean (4.52). Retain the champion. The submission timestamp, run ID and scorer version were not supplied.
