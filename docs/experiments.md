# Experiments

Practice scores are mean placement points. A simulated delta is a hypothesis, not an official prediction.
Use the same seeds and simulator revision for each factor combination. Keep the first combination as control.
Record the commit and environment values; if the tree is dirty, preserve the diff and bot hash with the results.

| Version / commit | Change and reason | Simulated Δ | Official score / Δ | Status |
| --- | --- | --- | --- | --- |
| `2646e82` | 11:21 p.m. Nov 20 bot: tactics, repositioning and roofs | — | 2.92 / — | Best reported; commit inferred from timestamp |
| `a528856` | Previous bot | — | 2.56 / — | Baseline reported by user; commit association unverified |
| `9a73729` | Adaptive combat and farming | — | 2.71 / +0.15 | Baseline reported by user |
| pending | Urgent roof descent: escape instead of stalling at an edge | +1 on one squad-proxy seed; 3 other seeds tied | Not submitted | Keep testing |
| pending | `BOT_STRAFE=steady` and `BOT_HUNTERS=on`: test movement and active-threat selection separately and together | 2 seeds: steady −1.0, hunters 0.0, interaction 0.0 | Not submitted | Smoke test only; opt-in |
| pending | Delay partial gun reloads during recent combat; reload empty guns immediately | Expanded FFA, seeds 420000–420004: 9.2 vs 9.4 control. Squad proxy, seeds 420000–420003: 2.5 vs 2.25 control | Not submitted | Mixed, small samples; needs more testing |
| pending | Reload policies, squad proxy seeds 420000–420007 | Legacy 2.00; recent contact 2.125 (paired +0.125, SE 0.48); cover 1.625 (paired −0.375, SE 0.71) | Not submitted | Recent-contact candidate is default locally; cover is opt-in |
| pending | Short combat boost bursts, same seeds, recent-contact reload | Off 2.125; on 1.75 (paired −0.375, SE 0.26) | Not submitted | Opt-in only |
| pending | Nearby laser peek after cooldown, same seeds, recent-contact reload | Off 2.125; on 2.00 (paired −0.125, SE 0.125) | Not submitted | Opt-in only; six peek decisions in seed 420003 trace |
| `2646e82` | Previously reported 2.92 version, same squad proxy and seeds | 3.625 vs current recent-contact candidate 2.125 | 2.92 reported, commit inferred | Eight seeds; investigate changes before drawing conclusions |
| pending | Hybrid current committed bot with `2646e82` combat module, squad proxy 420000–420015 | 3.1875 vs 2.625 current committed bot; first eight 2.625 vs 2.0; holdout eight 3.75 vs 3.25 | Not submitted | Module swap includes multiple changes; small sample |
| pending | Hybrid current committed bot with `2646e82` strategy module, squad proxy 420000–420007 | 2.0 vs 2.0 current committed bot | Not submitted | Eight seeds; does not establish equivalence |
| pending | Gun and laser trigger factorial, legacy reload, 420000–420007 | Current 2.0; old gun 2.875; old laser 2.0; both old 3.0 | Not submitted | Gun paired delta +0.875, SE 0.93; concentrated in one seed |
| pending | Gun trigger holdout, legacy reload, 420008–420015 | Current 3.25; no predicted-path check 2.75; old gun 3.375 | Not submitted | No clear gain; keep current trigger |
| pending | Weapon-range positioning and extended engagement, squad proxy 420000–420007 | Control 2.125; engagement only 1.75; positioning only 2.125; both 1.875 | Not submitted | Small sample; keep both off by default |
| pending | Weapon matchup: estimated enemy weapons in range, preferred distance, and exposed approach, squad proxy 420000–420023 | 24 seeds: 2.542 vs 2.292 control. Initial 16: 2.125 vs 2.0625 (paired +0.0625, SE 0.43); holdout 8: 3.375 vs 2.75 (paired +0.625, SE 0.50) | Not submitted | Enabled in local candidate; needs official validation |

The experimental switches are `BOT_RELOAD_POLICY=legacy,recent,cover`,
`BOT_COMBAT_BOOST=off,on`, and `BOT_LASER_PEEK=off,on`. Set
`BOT_FIRE_DIAGNOSTICS=on` to include gun decision labels in local traces, then
run `python3 tools/summarize_combat_trace.py /path/to/trace.jsonl`. These
summaries count observations, not individual shots; `cooldown` can accompany
an active fire command. The optional diagnostics consume debug-label budget.
For gun and laser ablations, use `BOT_GUN_POLICY=current,no_lead_check,legacy`
and `BOT_LASER_POLICY=current,legacy`. These legacy switches reproduce only
the noted trigger and laser-aim selection portions, not the entire old combat module.
Range experiments use `BOT_RANGE_POSITION=on` and `BOT_RANGE_ENGAGEMENT=on`;
the bot can see opponent weapon kinds but not their upgraded weapon stats.
`BOT_RANGE_MATCHUP=off` disables the local matchup candidate, including its
range-based incoming damage estimate, exposed-approach check, and positioning.

## Run

```sh
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--eagle-eye-mech-royale \
  --factor BOT_STRAFE=legacy,steady --factor BOT_HUNTERS=off,on \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The JSON contains per-seed outcomes, factor values, paired differences, a two-factor interaction, bot and diff hashes,
and simulator revision. The first value of each factor is the control. Use a clean committed checkout for official
comparisons. `--opponent` enables FFA; without opponents the runner uses the squad proxy. These tests run external
controller processes and are not a substitute for the official engine.

## Calibration

| Bot / version | Simulator and seeds | Sim mean | Official mean | Difference |
| --- | --- | --- | --- | --- |
| `2646e82` | squad proxy `e322ffe`, 420000–420015 (16 matches) | 3.19 (SE 0.60) | 2.92 | +0.27; different seeds and opponents |
| `2646e82` | second proxy `c1cc0d2`, 0–3 (4 matches) | 2.75 | 2.92 | −0.17; different seeds and opponents |
| 2.71 baseline | squad proxy, 420000–420003 | 2.0 | 2.71 | −0.71; only four matches, diagnostic only |

The first proxy's 16-match scores range from 0 to 6; its approximate 95% interval for the mean is 1.91–4.47.
The official 2.92 covers 48 matches on private seeds. These estimates cannot establish predictive accuracy or a
correction factor; compare more versions and repeat official results. Raw local results are in
`mech-testing/calibration-2646e82-420000.json`, `mech-testing/calibration-2646e82-420008.json`, and
`mech-testing/calibration-2646e82-second.jsonl` (ignored local files).
