# Reproducing a local evaluation

Run from the repository root with Python 3.9+ and cc. The checked-out simulator used here is supplied by the existing local lineup. See docs/local-simulator.md for setup. The squad panel snapshots this repository's Python submission layout, the simulator source including arena.py, map binaries, greeting/configuration, and runner. For another Python layout use the existing FFA runner and document its dependencies separately.

```sh
SIM=competitors/updated/
P=mech-testing/eval-baseline
python3 tools/baseline.py --sim "$SIM" --seed-start 421100 --seeds 20 --out "$P"
python3 tools/diagnose.py "$P" --out /tmp/baseline.json
python3 tools/bench_observer.py mech-testing/eval-profile/full.jsonl
python3 -m unittest discover -s tests -v
```

Choose a fresh output directory for each panel. The actual run is under mech-testing/eval-baseline. inputs.zip preserves dirty source and independent runnable inputs. manifest.json records code, simulator and kit digests, revisions, effective BOT_ overrides, platform and UTC time. The hashes cover the bundled runtime files. System Python, compiler, OS, hardware, scheduling and wall-clock search limits affect reproducibility. The layout hash covers the starting actors with roles, assignment order, zone schedule, loot, NPCs and planned drops. The match ID identifies the seeded configuration; separate directories and timestamps distinguish repeat executions. The evidence filename identifies the match for every JSONL record. Official game version is unknown. The pinned squad roles come from run_local_match.py with identical pool.py bytes for all 15 opponents. FFA lineup is a separate evaluation.

To replay one frozen match from this baseline (default bot environment, using the same Python and compiler), run:

```sh
python3 "$P/inputs/tools/run_local_match.py" --sim "$P/inputs/sim" --kit "$P/inputs/kit" \
  --bot "$P/inputs/bot/main.py" --seed 421100 --events /tmp/repeated-events.jsonl \
  --trace /tmp/repeated-full.jsonl > /tmp/repeated-summary.json
```

For archived inputs extract inputs.zip into a fresh inputs/ directory first. Restore any recorded BOT_ settings and remove other BOT_ overrides. Compare initial_layout_sha256 first. A repeat may diverge after the first action. The recorded events are the evidence for the original outcome.

## Version 1 evidence

Each JSONL record has v, tick, t in game seconds, origin, and kind. Degrees of access matter when interpreting these records.

| Kind | Origin | Payload and interpretation |
|---|---|---|
| sample | wire | Once per simulated second and at phase changes. Position, HP, inventory, energy, observed mech IDs (including memory), visible cube count and effective movement/trigger commands. Coast actions can be applied after late replies. |
| event | wire | Original subject event, stamped at observation delivery. Includes damage amounts, weapon and attacker when supplied, hit target, pickups, takes and upgrades. Pickup cubes is the resulting cumulative count. |
| phase | simulator | Zero-based index in this seed's zone schedule. |
| event, end | simulator | Undelivered events at termination, life flag, fatal weapon/source when exposed by the engine, inventory, HP, phase. A surviving timeout can have place greater than one. |

Per-seed JSON includes timing, local placement points, kills, events by type, incoming damage sums and integrated horizontal distance between successive observations including the endpoint. xy_path_m approximates ground-track length. There are no item-path, exposure, LOS, shot-attempt, hit-rate, field-term or causal score-loss measurements. Armor is an upgrade/stat rather than a second health pool. The action stream contains no reliable reason, selected target, shot ID or complete private policy state. Cubes increase stats and trigger offers; a death inventory cannot establish hoarding.

## Diagnosis and uncertainty

The report includes all terminal records and sampled evidence from each final five game seconds, configurable via --window. Multi-attacker pressure counts distinct mech damage sources in that window (default two). Low-HP trigger counts a sampled fire command at or below 35% HP (--low-hp). Possible stall requires two one-second-apart samples with movement magnitude at least 0.8 at both ends and less than 0.5 m net horizontal progress. Reversals, combat maneuvers or command changes between samples can satisfy this rule. Zone elimination reads the simulator cause. Unknown means a death matched none of these rules. A surviving finish has no failure tags. Tags overlap. Low HP and incoming damage can be consequences of losing. Evidence for avoidability, readiness at fight entry, missed shots, inefficient farming, and attributable placement points requires a controlled comparison.

The interval uses a fixed RNG seed and 4,000 percentile bootstrap resamples of entire seed outcomes. Single-field results describe sampling variation on this proxy and exclude timing variance within seed and official engine uncertainty. Attribution by individual opponent would require a different design because all roles participate in the same match.

The original baseline used a working tree with evaluation files added to d87f599. Submission runtime bytes were frozen before playing, and no gameplay files were edited. Later runner revisions also record subject and slot_roles explicitly. For the original rows the subject slot is recovered from the pinned Match constructor's first seeded random draw, to exclude self-damage from attacker counts.

## Fast checks and scenarios

L0 uses existing decision, navigation and physics tests. L1 uses replayed observations with a fresh real Bot for each fixture. Two windows together took 2.22 s wall versus 144.77 s for the full baseline. The terminal fixture is the **repeat** of 421101. The controller starts with empty memory at tick 3982. It chose cornered on 50/50 frames and requested fire at low HP on eight. The opening fixture starts at spawn with visible loot; the default chose loot on 25 of 60 frames. Input and greeting seeds are fixed. Timing-budgeted path searches can still vary. The harness checks action schema, finite numbers and tick alignment. It applies a ten-second process timeout per fixture. Counterfactual combat, movement and pickup outcomes require closed-loop matches.

```sh
python3 -m unittest discover -s tests -p test_controller.py -v
python3 -m unittest discover -s tests -p test_navigation.py -v
python3 -m unittest discover -s tests -p test_scenarios.py -v
/usr/bin/time -p python3 tools/scenario.py run tests/fixtures/*.json.gz
python3 check/check.py -- python3 -u main.py
```

The committed fixture files can be regenerated from these local traces. Capture requires a fresh output filename. The kit greeting provides the map/config and the runner's slot formula provides the bot seed.

```sh
P=mech-testing/eval-baseline
python3 "$P/inputs/tools/run_local_match.py" --sim "$P/inputs/sim" --kit "$P/inputs/kit" \
  --bot "$P/inputs/bot/main.py" --seed 421101 --events /tmp/repeat-events.jsonl \
  --trace /tmp/repeat-full.jsonl > /tmp/repeat-summary.json
python3 tools/scenario.py capture mech-testing/eval-profile/full.jsonl --seed 421000 --tick 0 --steps 60 --out /tmp/opening_loot.json.gz
python3 tools/scenario.py capture mech-testing/eval-profile/repeat-full.jsonl --seed 421101 --tick 3982 --steps 50 --out /tmp/terminal_pressure.json.gz
```

## Screening and confirmation

Each spec names A and B, optionally C. Paths are relative to the spec. Use clean worktrees or the supported Python submission layout for different source builds. Each candidate executes from its own frozen snapshot. The spec supplies all BOT_ overrides. History in inputs.zip and registry.jsonl identifies each build. A failed child aborts the study and completed rows remain available for inspection. The runner refuses to reuse an output directory.

```sh
SIM=competitors/updated/
python3 tools/paired_panel.py --sim "$SIM" --spec experiments/squad-screen.json --seeds 3 --out mech-testing/eval-screen
python3 tools/paired_panel.py --sim "$SIM" --spec experiments/squad-confirm.json --seeds 5 \
  --confirm mech-testing/eval-screen/report.json --out mech-testing/eval-confirm
```

The smoke screen compared existing options. A/default averaged 7.67, B/recovery 8.00 and C/position 7.67. B−A was +0.33, C−A 0, B−C +0.33. On five fresh confirmation pairs both A and B averaged 3.20, with B−A differences +1, 0, −1, 0, 0 and bootstrap interval [−0.6, +0.6]. There were zero late or invalid replies in either study. This is a pipeline check and provides no basis for promoting a challenger. Score intervals on three or five observations are descriptive. The historical official champion stays recorded in docs/experiments.md.

Development uses seeds 422000–422999 and confirmation 423000–423999, indexed by --offset and --seeds. Choose fresh, logged offsets on later studies and predeclare the size before examining results. Confirmation verifies the screened reference and challenger identities and environment context. The runner checks every paired layout. Turn order rotates within each seed. Each study compiles geometry once; each match starts a fresh process and Map. Running several timed bots on shared cores can change policy decisions and timeout rates, so these measurements use serial full matches. Independent unit tests can run concurrently.

For the compilation comparison below, the same frozen screen runner and seed 421101 scored one point both ways. Startup fell from 1.43 s (0.45 s in cc) to 0.64 s, and wall time from 5.61 s to 4.82 s. This single pair includes cache warming and timing variation. The verified saving is one compilation per subsequent match. The screen compiled once for nine games and confirmation once for ten.

```sh
S=mech-testing/eval-screen
/usr/bin/time -p python3 "$S/A/inputs/tools/run_local_match.py" --sim "$S/A/inputs/sim" --kit "$S/A/inputs/kit" --bot "$S/A/inputs/bot/main.py" --seed 421101 --events /tmp/uncached.jsonl
/usr/bin/time -p python3 "$S/A/inputs/tools/run_local_match.py" --sim "$S/A/inputs/sim" --kit "$S/A/inputs/kit" --bot "$S/A/inputs/bot/main.py" --seed 421101 --events /tmp/cached.jsonl --geometry-library "$S/geometry.so"
```

## Manual official records

The SQLite log imports a completed frozen reference panel, supports a reasoned queue, and records actual submissions and results manually. The slot view needs a complete submission history for the last hour and a caller-supplied verified platform limit. It cannot see the platform. No submission timestamps or official results were supplied for the frozen baseline. Its matched calibration sample is **n=0**. Earlier approximate local builds and user-reported aggregate scores are retained in docs/experiments.md.

```sh
DB=mech-testing/eval-registry.sqlite
python3 tools/official_log.py --db "$DB" import-panel mech-testing/eval-baseline
python3 tools/official_log.py --db "$DB" list
python3 tools/official_log.py --db "$DB" slots --limit "$VERIFIED_LIMIT"
python3 tools/official_log.py --db "$DB" queue "$BUILD_ID" "$REASON"
python3 tools/official_log.py --db "$DB" submitted "$BUILD_ID" "$OFFICIAL_RUN_ID" "$ACTUAL_ISO_TIMESTAMP" "$BENCHMARK_VERSION"
python3 tools/official_log.py --db "$DB" result "$OFFICIAL_RUN_ID" "$REPORTED_POINTS"
python3 tools/official_log.py --db "$DB" calibration "$PANEL_ID" "$BENCHMARK_VERSION" --chart /tmp/calibration.vl.json
```

The last five commands are templates for verified operator inputs. Queue only an artifact whose submitted Dockerfile/config will activate the tested settings. Register the exact built and configured source; a local BOT_ toggle alone does not configure an official image. The official ranking uses the highest recorded score within benchmark version and earliest submission for ties. A reference panel fixes seeds, simulator, map/config and runner. Import one preselected reference run per build and panel. Calibration averages official repeats for each exact build/version, reports official minus local, MAE and rank inversions, and emits an optional Vega-Lite scatterplot specification. Pearson and tie-aware Spearman appear only for five or more distinct builds with nonconstant values (null for zero variance). Small panels remain exploratory.

The [machine-readable event schema](schemas/match-event-v1.json) describes version 1 JSONL records. For the post-implementation verification run, use:

```sh
python3 -m unittest discover -s tests -v
python3 tools/diagnose.py mech-testing/eval-baseline --out docs/evaluation_baseline.json
python3 tools/paired_panel.py --sim competitors/updated/ \
  --spec experiments/squad-confirm.json --out mech-testing/eval-pipeline-check --offset 20 --seeds 1
```

The last command runs a one-pair development smoke test of subsystem-delta output. For the real A/B/C screen and held-out smoke results, see the original study directories in mech-testing. Preserve these directories, including inputs.zip, when moving results to another machine. They are Git-ignored.
