# Experiments

Practice scores are mean placement points; local simulator results are hypotheses, not official predictions. The current priority is improving practice placement to qualify. [Practice implementation plan](practice-improvement-plan.md) · [Historical experiments and calibration](experiments-history.md) · [Simulator limitations](simulator.md).

**Scoring context:** Unless explicitly marked builders-4, the official practice scores and comparisons in this document use the old scoring setup. The user reports that `835d4a7` was rescored at **5.21** under builders-4; its old score was **5.23**. Do not compare old scores directly with builders-4 scores.

## Close-range gun timing — rejected local experiment

On `6f1b276`, a candidate changed gun-only aiming within 65 m to predict the shooter's movement, the target's movement before the firing substep, the forward muzzle offset, and the proxy simulator's discrete projectile steps. The existing policy instead aims from observed positions. The hypothesis was that compensating for movement before firing would improve close-range hits. The candidate was limited to grounded, non-jumping situations where the gun could fire within the next two physics ticks; it retained the original model when its assumptions could not be applied.

The change was **rejected and reverted**. In 384 open-ground cases with perfect initial alignment and no spread, both versions hit every time. In 5,000 synthetic cases with varied alignment, movement, boost, spread and cooldown, the original produced **3,144 hits** and the candidate **3,125**. Two further synthetic batches also favored the original overall (4,495 vs 4,421 and 4,512 vs 4,467 hits). Some apparent improvements in particular distance or velocity subgroups were identified after examining the data and did not consistently reproduce in held-out checks.

These are open-ground local proxy-physics simulations with artificial scenario distributions, not match results or official scores. The candidate changed some trigger decisions as well as the aim point, so the hit totals do not isolate aim-angle accuracy. The experiment does not prove every close-range correction is harmful; it means this implementation did not demonstrate a reliable improvement worth submitting. The experimental patch and analysis scripts were left under `/private/tmp` and may not persist.

## Official practice — builders-4

**Subtle gun-range candidate — score pending:** Starting from `fb99ebd` (4.93),
ordinary squad combat with a gun and no laser or lightning prefers 82 m rather
than 85 m when seeking line of sight. Target selection, retreat decisions and
cornered retreat movement retain the parent behavior. Other positioning
planners can still take priority. Hypothesis: slightly shorter range improves
gun pressure; risk: the extra proximity increases damage taken. Compare with
`fb99ebd` before attributing any score difference to this single change.

**Aggressive retreat and targeting candidate — official 4.93:** The user
reports that `fb99ebd` scored **4.93**, compared with **5.47** for `955e6bf`
(observed difference −0.54). The run ID and submission time were not supplied.
The runs use independent private seeds, so the difference does not establish a
causal effect. Retain `955e6bf` as the best reported practice result.

The candidate is based on the runtime and Docker
settings of `955e6bf` (5.47), with the later favorable-fight initiation and
timeout fallback removed. In practice, retreat starts at higher health when
outnumbered or losing a one-on-one exchange and persists for three seconds;
offensive positioning yields to retreat unless finishing or in the late game.
Vulnerable visible enemies can be engaged farther away and have a stronger
priority over the current target. This combines two changes, so an official
result cannot isolate their contributions. Longer retreats may sacrifice damage
or expose the rear, and switching may waste aim time.

**Next hypothesis:** Survival may benefit more from cover that preserves a
firing opportunity than from a longer retreat triggered by health and enemy
count alone. This candidate can retreat without creating the damage-free window
needed for regeneration, and its reduced target persistence may delay kills.
These are plausible mechanisms, not observed causes of the score. Compare each
change separately against `955e6bf`: first measure retreat duration, damage
dealt and received, healing windows, target switches, kills, and placement in
matched local scenarios; then test a narrowly scoped change where those traces
show a recurring problem. The proxy is not an official score predictor.

**Favorable-fight candidate — official 5.03:** The user reports that `3a9ff29`
scored **5.03** in builders-4. The run ID and timestamp were not supplied. This
is the direct parent and official baseline for the `afef1f3` rearchitecture
candidate, whose official result is pending. Independent random seeds limit
what a score difference can establish. On the
`955e6bf` strategy and Docker settings with the smart timeout fallback, practice
may initiate a fight against a currently listed mech within 130 m and clear line
of fire when health exceeds 60%, a gun or laser is ready, there is no other
recently tracked mech within 160 m, and the existing rough damage-exchange
estimate is at least 1.3. Existing urgent-zone and defensive decisions retain
priority. This is a heuristic, not the other bot's range planner; unseen enemies,
armor, hit rates and readiness can make the estimate wrong. Sound scanning and
predictive projectile dodge are excluded. Hypothesis: take more advantageous
fights and convert them to kills. Risk: underestimated incoming damage or extra
hunters cause earlier deaths. The 163-test suite passed (15 skipped), and the
native recorded protocol replay answered 300/300 on time (14.5 ms maximum on
this host). The linux/amd64 Docker image passed the restricted one-CPU, 512 MB,
read-only replay 300/300 (19.7 ms maximum on this host under emulation). These
checks do not establish official placement or live-match latency.

**Sound-directed scanning — official 5.01:** `f36ede6` uses the
`955e6bf` strategy and Docker configuration, adds the smart timeout fallback,
and changes idle scanning to look toward fresh nearby or midrange mech sounds.
It favors cues outside the current vision cone and gives movement and reload
sounds more weight than weapon fire. Active combat and recent damage directions
retain priority; sound alone does not trigger a shot. It excludes predictive
projectile dodge. Hypothesis: orient vision toward otherwise unseen mechs and
acquire threats sooner. Risks: sounds are anonymous and noisy, cover may block
vision, and repeated sounds may distract from other directions. The weights and
scan duration are uncalibrated. The 166-test suite passed (15 skipped); the
native recorded protocol replay answered 300/300 on time, max 15.1 ms on this
host. These checks verify behavior and protocol timing, not placement. User
reports **5.01** for `f36ede6`, versus 5.47 for `955e6bf` (observed −0.46).
The timeout safeguard also differs; independent seeds prevent causal attribution.
Run ID and timestamp were not supplied.

**Predictive projectile dodge:** User reports `9078ed6` scored **5.29**, versus
5.47 for `955e6bf` (observed −0.18). Its strategy adds only predictive projectile
steering to the 5.47 baseline; it also includes the smart timeout fallback.
Therefore the result does not independently measure dodge and timeout effects.
Run ID and timestamp were not supplied. The independent-seed comparison does not
establish causality. The timeout fallback sends the last continuous move, aim
and boost if a decision exceeds its internal budget; it omits one-shot actions.

**Combined movement trial:** User reports `37d0167` scored **5.11**, versus
5.47 for `955e6bf` (observed −0.36). It bundled predictive projectile steering,
clearance-based recovery, top-surface jump/jet routing, roof descent and
lower-resolution combat sampling. The runtime strategy otherwise matches the
5.47 baseline. The bundled changes and independent seeds prevent attribution
to any individual mechanism. Run ID and timestamp were not supplied.

**Fixed upgrade order:** User reports `7d09a1b` scored **5.35**. It keeps corner duel and the positional field enabled and removes the gun-only magazine priority. Run ID and timestamp were not supplied. Independent-seed score differences do not establish causality.

**Positional-field follow-up:** User reports `a8a9e91` scored **5.08** with positional field disabled, compared with 5.47 for `955e6bf` and 4.95 for `e331335` with corner duel disabled. These are independent-seed results, not proof of causality. Keep both tactics on for the next test. The next candidate removes the gun-only magazine priority, keeping the fixed upgrade order; it changes only `choose_loadout` on the 5.47 baseline. Earlier magazine comparisons were under the old scorer. Run IDs and timestamps were not supplied.

**Corner-duel follow-up:** User reports `e331335` scored **4.95** with corner duel off on the `955e6bf` baseline, versus 5.47 with it on. These runs use independent private seeds, so the observed −0.52 does not prove the causal effect. Next test keeps corner duel on and disables the positional field alone. Submission time and run ID were not supplied.

**Follow-up:** User reports `c6053f8` scored **5.06**. Its submission files match `5801ebd`, which enables supply drops on the 5.47 `955e6bf` baseline. The observed difference is −0.41 on independent private seeds; it does not prove a causal loss. Keep 5.47 as the best reported result. Next candidate disables corner duel on the exact 5.47 runtime, with supply drops off. User also reports `25c82cd` scored 5.26; it uses a different source tree and enables finish priority. Run IDs and timestamps were not supplied.

| Commit | Configuration | Score |
| --- | --- | ---: |
| `955e6bf` | Jack aim, corridor off, early drone off | **5.47** |
| `fb99ebd` | Earlier, longer retreat and stronger vulnerable-target priority | 4.93 |
| `7d09a1b` | Fixed upgrade order, positional field and corner duel on | 5.35 |
| `9078ed6` | 5.47 baseline, predictive projectile dodge and timeout fallback | 5.29 |
| `37d0167` | 5.47 baseline, combined movement changes | 5.11 |
| `3a9ff29` | Favorable-fight initiation and timeout fallback | 5.03 |
| `f36ede6` | 5.47 baseline, sound scanning and timeout fallback | 5.01 |
| `a8a9e91` | 5.47 baseline, positional field off | 5.08 |
| `e331335` | 5.47 baseline, corner duel off | 4.95 |
| `26c9ad6` | Jack aim-only package | 5.42 |
| `835d4a7` | Positional-field baseline, rescored | 5.21 |
| `6e0c84c` | Jack aim with partial-cover aiming | 5.20 |
| `4741606` | Supply drops with blocked-route penalty | 5.10 |
| `a022b4a` | Jack aim, corridor on, early drone off | 5.05 |
| `4d4d263` | Jack aim, corridor off, early drone on | 4.91* |

Scores are user-reported, except the Jack-branch results recorded in its experiment notes. Run IDs and timestamps were not supplied. Builders-4 runs use independently sampled seeds, so differences do not establish causality. *The supplied hash for the 4.91 result did not resolve locally; `4d4d263` is the matching queued commit and should be confirmed.

## Ranked queue when official testing reopens

### Current focus: drops, zone, roofs and post-kill loot

Jack is investigating reload and engagement policy; keep those unchanged in this series. Use `955e6bf` (5.47 builders-4) as the control and test each factor separately.

1. **Supply drops only:** `5801ebd` on branch `trial/supply-drops` is based directly on `955e6bf` and changes only `BOT_SUPPLY_DROPS=1`. When calm, the existing policy considers an uncontested drop, estimates landing, capture and zone timing, and values its full heal and three cubes. Risks include travel, lost combat time and incoming hunters. The 17 controller tests passed, including drop approach, hold and yield; the exact linux/amd64 image passed the restricted replay with 300/300 on time (29.4 ms maximum on this host). Record captures, HP before and after, detours and placement. Official score pending.
   **Blocked-route variant:** `4741606` on `sam` packages the same submission files as tested trial `ddc0cfb`. User-reported builders-4 score: **5.10**, versus 5.47 for `955e6bf` (observed difference −0.37; independent random seeds). This comparison changes both supply-drop pursuit and the blocked-route penalty, so it isolates neither effect. Run ID and timestamp were not supplied. It adds 45 m to the estimated distance for a blocked direct approach, affecting drop preference and zone deadline checks. This is a conservative heuristic, not an actual path-length estimate; open routes and capture behavior are unchanged. Three route scenarios, the wait-metric scenario and 17 controller tests passed. The `ddc0cfb` restricted linux/amd64 replay passed 300/300 on time (28.8 ms maximum under host emulation). `tools/measure_drop_wait.py` in this commit measures observed pre-landing time inside drop rings and captures from local JSONL traces. On one sequential proxy pair at seed 425001, `5801ebd` spent 8.2 s in the first ring before landing and captured it, while `ddc0cfb` died before the first drop and spent 0 s waiting; their scores were 5 and 6 respectively, with 1 late/invalid response for control and none for the variant. This single timing-confounded pair is not a comparison of wait reduction or official strength. Trace files: `/tmp/drop-control-425001.jsonl` and `/tmp/drop-route-425001.jsonl` (temporary local files). No staging change has been implemented.
2. **Post-kill loot:** instrument combat cube detours, including nearby enemies, time to collect, damage taken and upgrades. Then compare the existing unconditional nearby-cube diversion with a threat-aware gate. Avoid assuming every cube pile is from a kill; verify event and item associations.
3. **Zone movement:** measure zone damage, late rotations, route stalls and lost firing time first. If they are frequent, test an earlier or route-aware rotation independently; straight-line distance underestimates some routes, but overly early movement can sacrifice kills.
4. **Roof tactics:** first measure roof visits, line of fire, falls and exits. The controller already has roof ascent and descent navigation; a combat-roof policy would be a new experiment. Check zone timing, energy, safe descent and firing lanes before testing it.

Further candidate: investigate supply-drop contest prediction using observed or recently seen enemies only, after measuring how often the existing drop policy attempts, captures or abandons drops. Do not assume unobserved enemy positions.

**Recorded baselines:** `835d4a7`, 5.21 on builders-4 (5.23 on the old scorer); Jack's branch reports `26c9ad6`, 5.42 on builders-4. All five candidates below enable Jack's `BOT_AIM_MODEL=dev` and retain Sam's reload behavior. They run practice-only and are not suitable for qualifying FFA without a separate policy and test. Their commits are distinct packages on the `sam` branch.

The organizers announced **builders-4**, with 96 fresh private random seeds per practice submission, and automatic rescoring of each team's picked or best builders-3 entry. Identical code keeps its first builders-4 score; resubmitting it does not yield an independent score. Verify the live quota before starting. Record the exact commit, settings, run ID, timestamp, scorer version, score and any per-match results or replays. Old scores are not directly comparable to builders-4 results. Fresh seeds make candidate comparisons unpaired. [Organizer announcement](https://www.joinbuilders.org/buildathon/leaderboard)

1. **Aim with corridor:** `a022b4a` — corridor on, early drone off, optimized geometry. User-reported builders-4 score: **5.05**; run ID and timestamp were not supplied. Compare with item 2 to investigate the corridor; this is also the control for item 5.
2. **Aim without corridor:** `955e6bf` — corridor off, early drone off, optimized geometry. User-reported builders-4 score: **5.47**. Compare with item 3 to investigate early-drone preference and with item 1 to investigate the corridor. Run ID and timestamp were not supplied.
3. **Aim with early drone:** `4d4d263` — corridor off, early drone on, optimized geometry. User-reported builders-4 score: **4.91**. The supplied hash was `d4d263b93ae`, which does not resolve locally; `4d4d263b93ae` is the matching queued commit. Confirm the submitted revision. Compare with item 2 to investigate the early-drone preference.
4. **Aim with corridor and early drone:** `8a4db86` — corridor on, early drone on, optimized geometry. Together with items 1–3, this completes the corridor × drone comparison.
5. **Aim with earlier geometry:** `a10db1f` — corridor on, early drone off, using the geometry and corridor planner from `ebf0354` before the `d0b451b` optimizations. Compare with item 1 to investigate those optimizations. Both retain the later early-drone code with the factor off.

Each exact commit built for linux/amd64 and passed the restricted protocol replay with 300/300 on-time replies; maximum response times were 29.1, 28.8, 35.3, 28.5 and 35.8 ms respectively on this host under emulation. The fifth replay dropped one older queued observation. Each commit also passed the three focused aim tests. These checks do not establish placement or live-match latency.

The user reports that `835d4a7` was rescored at 5.21 under builders-4. Record the run ID, timestamp and per-match results if available. Do not spend a slot on an identical-code repeat to seek another draw.

Jack's branch (`609162f`) records **5.42** for `26c9ad6` under builders-4 and **5.20** for the later partial-cover aiming trial `6e0c84c`; these scores are reported without run IDs or timestamps. The 4.91 candidate also changes practice behavior and drone preference, so its result does not isolate aim. The aim portion of `4d4d263` matches `26c9ad6` when enabled; its default switch differs but the candidate Dockerfile explicitly selects `dev`. It intentionally retains Sam reload behavior, as does Jack's aim-only package.

The user-reported 5.47 for `955e6bf` versus 4.91 for `4d4d263` is an observed difference of +0.56 with the early-drone preference off. These packages differ only in that switch, but their builders-4 runs use independent random seeds; the aggregate difference does not establish a causal effect. The 5.47 and Jack's 5.42 also come from different packages and independent runs.

The user-reported 5.05 for `a022b4a` versus 5.47 for `955e6bf` is an observed difference of −0.42 with the corridor enabled. These packages differ only in that switch; their independently sampled builders-4 runs do not establish a causal effect. Retain `955e6bf` as the stronger reported result.

Do not prioritize rerunning the recent failed packages without a new reason: `e922fb0` (steady strafe, 4.65), `f2a61ab` (laser timing, 4.96), `4933656` (attacker priority, 4.90) and `8d52f44` (dedicated practice policy, 5.00) are user-reported results. In particular, do not bundle another strafe change into the corridor or farming trials. A later strafe study should first measure actual movement, overrides, hits, damage and firing time; the edited strafe timer does not by itself determine the movement command.

## Jack's aim-only model

Jack's `26c9ad6` packages the aim model introduced in `40bfccc`, with Sam reload behavior. The queue ports only the gun aim portion onto the practice controller: `BOT_AIM_MODEL=dev` uses a constant-velocity intercept from the observed muzzle and checks the predicted shot path; `sam` or an unset variable retains the original aim. The Dockerfile explicitly enables `dev`. It does not include Jack's reload policy or the later upper-body aiming change. The model can withhold a shot when the predicted center is obstructed, including when the target's upper body is visible; it may also change leading accuracy. These effects and placement remain unmeasured on this parent.

Jack's eight-seed local screen on a different parent found aim-only 5.0 versus Sam control 6.25 (paired −1.25, SE 1.49); it was sequential, one aim response was late, and simulator metadata was incomplete. It cannot rank the new package or predict builders-4 scores. The prior combined aim-and-reload score of 5.15 was also under the old scorer and cannot isolate either change.

The initial aim-port working-tree linux/amd64 image passed the restricted protocol replay: 300/300 on time, maximum 28.6 ms under emulation on this host. Three focused aim tests and 17 controller tests passed with the model enabled. The full suite had five failures in finish-approach, reload-cover and historical practice-routing tests; the unchanged `c93c3f0` control has the same five failures. Recheck the exact committed image before submission; these checks do not establish placement strength.

## Reference comparison and latency

The local reference documents a Python approximation of Giddy `e19e3c8`; the current integrated policy shares substantial tactical structure but has diverged, and is not an equivalent reproduction. For a read-only comparison, the locally vendored Go driver and the packaged Python image were run separately against the same 300-observation checker stream, with linux/amd64 Docker, one CPU, 512 MB and the same mounted map. Go returned 300/300 on time (p99 2.8 ms, max 10.0 ms). Python returned 299/300 on time in one run (p99 29.7 ms, max 84.8 ms), then 300/300 on a repeat (p99 23.9 ms, max 28.4 ms). Measurements were on this host under emulation and depend on load; the static stream does not establish official late rates or the effect on placement. The Go and Python builds also have different policies, so this is not a controlled language-only comparison.

On the same 300 fixed observations, the two policies' move directions were within 20 degrees on 97 of 297 observations where both moved, and their fire decisions agreed on 36 of 59 observations where either fired. This is not closed-loop parity or an estimate of score. The current Python build forces practice from tick one, while the Go reference infers the mode and uses other settings, so the divergence is expected and not attributable solely to Go versus Python.

## Historical Python practice policy (`8d52f44`)

That historical packaged controller starts in practice mode on tick one. Movement, target selection, firing and loadout share the same perception and routing code with FFA. The first uncredited decrease in the alive count selects FFA actions immediately. Five consecutive observations with a discrepancy lock in FFA. An explicit `BOT_PROFILE=final` selects FFA throughout. These are historical `8d52f44` behaviors, not the current practice-only policy. Compare its official placement against `835d4a7` (5.23).

Two 600-observation replay slices with clocks shifted to select practice for both policies matched firing on all 1,200 decisions and movement within 0.2 vector distance on 1,199. In an unmodified 2,691-tick recording, the overlapping practice interval matched firing on 1,762/1,762 ticks and movement on 1,674/1,762. The packaged protocol check answered 299/300 observations within 50 ms, with one late response. The user reported **5.00** for `8d52f44`.

## Active attacker priority

Commit `4933656` restored the packaged `835d4a7` policy and increased the practice target-selection bonus for a recent attacker from 40 to 160, retaining the near-lethal bonus. It passed the baseline's 102 tests and the restricted Docker protocol check (300/300 on-time replies). The user reported an official score of **4.90**, compared with 5.23 for `835d4a7`. This aggregate result does not establish causality, but does not justify retaining the trial; restore the 5.23 target weighting. Run ID, timestamp and scorer version were not supplied.

## Steady squad strafe

`BOT_SQUAD_STRAFE=steady` increases the interval between voluntary strafe-direction reconsiderations from 0.3–1 seconds to 3–5 seconds in squad combat. Existing wall-triggered reversals and FFA timing remain unchanged. The hypothesis is that more consistent lateral velocity reduces exposure to the coordinated house bots' projectile fire without giving up offense. The counter-hypothesis is that a predictable path or a persistent unfavorable direction makes incoming shots easier to land. This changes only the strafe timing on the `835d4a7` policy; the previous laser-timing and attacker-priority trials are disabled.

Eight counterbalanced proxy pairs on 422650–422657 gave 4.625 points for baseline and 5.125 for the trial, a paired difference of +0.50 (95% bootstrap interval −0.875 to +1.75), four better, two tied and two worse. The trial averaged 0.375 more kills and 45.8 more seconds alive, but had 9 late and 8 invalid replies versus zero for the baseline; these timing differences confound the comparison. This small proxy screen does not predict the official score. Raw evidence: `mech-testing/steady-strafe-422650/report.json` (git-ignored). A focused timing check, the baseline's 102 tests, and the packaged restricted Docker replay passed; the replay answered 300/300 on time (maximum 28.6 ms). User-reported official score for `e922fb0` was **4.65**; retain the 5.23 baseline.

## Prepared fight corridor

This official challenger starts from the `835d4a7` policy, with previous attacker-priority, laser-timing and steady-strafe trials disabled. In practice mode, at 12 or fewer alive or with two active threats, it considers nearby ground points that retain a firing line throughout a directly walkable approach and have a verified short exit with zone margin. It scores known extra firing angles and anonymous radial cover probes; the probes do not assert enemy positions. It follows a better candidate for up to 0.5 seconds, rechecking the path, target line, zone, target, body size and active attackers; otherwise it falls back to the prior controller. Projectile dodge, unsticking and urgent zone movement take priority. While following a corridor the controller does not divert to cubes. Direct-only routing is narrower than the proposed design; this version does not follow multi-segment corridors or explicitly score anonymous sounds. See [design](squad-corridor-design.md).

The hypothesis is that positioning before hunters converge helps maintain offense without simultaneous firing lines. Risks include sacrificing damage, becoming predictable, a mistaken cover model, or the corridor rarely activating. Ten focused synthetic tests cover pre-positioning, open ground, blocked paths and exits, disappearing target, changed line of fire, time limit, two-threat activation and urgent zone precedence. The 107-test baseline-plus-corridor suite passed with the corridor factor disabled; existing positional-field tests with the factor enabled expect the old movement mode and are not valid as unchanged-mode assertions. The packaged restricted Docker protocol replay passed with 300/300 replies on time, maximum 31.1 ms. There is no local placement claim; official score pending.

### Revised corridor

The revision compares candidate routes to the baseline controller's already-selected move; it considers visible secondary attackers, recent damage and approaching enemies separately from the selected target, and assigns uncertain sound sectors a smaller risk. It protects near-lethal targets and existing cube, dodge, retreat and zone decisions. It can attempt a verified two-segment path, checks a usable firing line at the endpoint and limits interruptions en route. Threat movement, damage, target movement, growth and zone changes invalidate cached routes. Failed searches are throttled, and planning is skipped if fewer than 4 ms remain in the controller's own budget. Candidate search is capped at eight endpoints and at most 5 ms within that budget. In-memory counters record calls, route selections, cache steps, no-route and deadline exhaustion; they are not emitted to the submission stream.

The baseline suite plus revised scenarios passed with the factor enabled (119 tests). The restricted Docker replay passed 300/300 on time, maximum 28.5 ms. These are compliance and behavior checks, not placement evidence. A forced-practice replay of five historical proxy observations initially selected a corridor on just one of 10,507 frames and frequently exhausted the search budget. After reducing geometry work, two of those recordings produced 3 and 13 corridor-mode frames respectively (2 and 5 routes selected), with 0 host actions over 50 ms, but 19/19 and 156/167 failed searches exhausted the planner deadline. Observations in these replays do not react to the new actions; forced practice also bypasses the baseline's FFA inference. Actual activation, overhead in live matches and official score remain unknown. This revision does not establish a meaningful score improvement, and the search budget remains an unresolved limitation.

### Practice-only and target exposure

This submission explicitly packages the integrated controller and runs practice behavior from the first tick. It no longer changes to FFA when an opponent dies without our kill credit. It is not suitable for qualifying FFA without a separate change and test. The corridor includes the selected target as an incoming shooter and weights rear attack directions more heavily, while retaining separate secondary-threat weights. A small bounded reward based on cached grid clearance favors positions near walls even when the next hunter is not observed. Clearance is a rough proxy, not proof that a wall blocks a shot; the firing line and route checks still apply. Official score and effect remain unknown.

The baseline suite and current corridor scenarios passed with the factor enabled (124 tests), including first-tick practice, an uncredited death, target/rear exposure and a single-hunter wall preference. The restricted Docker protocol replay passed 300/300 on time, maximum 16.5 ms; this fixed replay does not establish match-time latency or placement.

Potential CPU work, to measure separately: cache per-tick line-of-sight results shared between perception, the field and corridor; precompute conservative directional cover or corner/exit candidates in the baked map; shortlist candidates cheaply before running exact path and shot checks; reuse valid routes until geometry, body size or threat state changes; and profile the full controller by subsystem under the restricted container before changing budgets. Preserve exact body-size/path verification on finalists and avoid claiming approximate cached cover blocks a live shot.

### Geometry performance work

Profiling one 2,313-observation historical recording identified combat movement, ray clearance and line walkability as major controller costs. Profiling and static observations affect scheduling and do not establish official match timing. An experimental per-observation exact cache saw only 298 hits in 17,535 shot queries and 589 in 7,132 walkability queries; it was not adopted globally. The corridor now caches exact shot, danger and walkability queries within a single planning call, so no result persists across changing observations or body size.

For long rays the arena broad phase now enumerates intersected grid cells instead of every cell in the surrounding rectangle. Prism and terrain collision checks are unchanged. Against the prior implementation, 6,000 seeded random rays, including axis-aligned and grid-boundary cases, produced no collision differences. The long-ray-heavy random sample took 2.161 s before and 1.202 s after on this host. A separate set of 10,000 rays collected from a recorded match produced no differences; in a one-pass host timing, the selected 16-cell crossover took 0.945 s versus 1.026 s using the rectangle for every query. These timings are samples, not guarantees. The ray regression test compares 600 map queries against the previous rectangle broad phase.

On recorded observations from seeds 420400 and 420404, after both optimizations with the earlier 40-cell crossover the practice-only bot selected corridor mode for 0/2,313 and 18/2,315 observations respectively, and returned no actions over 50 ms on this host. Seed 420404 recorded 116 planner deadline exhaustions, so the search bottleneck is not solved. These observations do not react to the new actions and cannot establish official placement.

The final 16-cell crossover passed the baseline-plus-corridor suite (126 tests). The image also built for linux/amd64 and passed the restricted protocol replay with 300/300 on-time replies, maximum 28.3 ms on this host under emulation. This validates compatibility on the recorded stream, not native scorer latency or official placement. Earlier Docker checks used the host's arm64 image; the AMD64 check makes the distinction explicit.

### Optional early drone trial

`BOT_EARLY_DRONE=1` is an opt-in experiment and is not set in the submitted Dockerfile. In the first 60 seconds, with at least 14 mechs alive, health above 75%, no immediate danger or recently seen mech within 120 m, and a fresh drone no farther than 70 m along a directly walkable route, it increases the drone's objective value from 85 to 170. It otherwise keeps the existing objective selector and safety/zone rules. The hypothesis is to acquire two cubes and upgrades before more hunters arrive; the risks are delaying a weapon, early fight or zone rotation and taking drone damage. The factor is separate from the corridor, which can be disabled to isolate it. Scenario checks cover enabled/disabled, blocked route, a nearby threat, a stale drone and active danger. No proxy or official placement result exists.

With the factor enabled, the baseline suite plus current scenarios passed (133 tests). Restricted linux/amd64 Docker protocol replays passed for both default and enabled configurations: 300/300 replies on time, maximum 28.6 ms and 28.4 ms respectively under emulation on this host. The scored image uses the Dockerfile environment, so an official early-drone trial requires an explicit candidate commit enabling the factor; a local `docker run -e` does not modify the submitted image. No claim about official performance follows from these checks.

## Laser timing trial

On the `835d4a7` policy, `BOT_LASER_TIMING=reload` delays starting a laser charge in practice while the gun has ammunition, is not reloading and can reach the target. An already started charge completes; FFA behavior is unchanged. The hypothesis is that moving at full speed and keeping the shared torso on gun aim between reloads compensates for fewer laser shots. The counter-hypothesis is that losing laser damage makes fights longer. Across five old proxy traces, 382 observations had a visible or tracked mech, a loaded gun and a laser already charging; these are not official matches and do not measure missed shots.

Eight counterbalanced proxy pairs on seeds 422600–422607 averaged 5.875 for the baseline and 6.25 for the trial, paired difference +0.375 (95% bootstrap interval −0.625 to +1.50), with three improved, three tied and two worse. Mean kills fell by 0.25 and survival rose by 10.9 seconds. Baseline had four late/invalid replies; trial had two. A protocol check ran concurrently during part of the panel, adding possible load confounding. This screen is small and cannot predict official score; the local proxy has poor historical calibration. Raw results: `mech-testing/laser-reload-screen-422600/report.json` (git-ignored). The user reported **4.96** for `f2a61ab`; revert the trial.

The focused weapon checks covered a loaded gun, reload, a charge already in progress and FFA. The baseline's 102-test suite passed with the factor enabled. The packaged restricted-container protocol replay answered 300/300 on time (maximum 31.3 ms).

## Isolated wounded opponent trial

Parent `835d4a7` scored **5.23** in official practice. The packaged candidate enables `BOT_FINISH_APPROACH=1`. During practice, a healthy mech with a ready weapon closes to a desired range of 20 m against a wounded, isolated opponent and defers cube collection during the approach. The hypothesis is that maintaining contact converts a retreating opponent into a placement point. The risk is taking extra damage before the next hunter arrives. Commit `67f32ba` scored **5.08**, 0.15 below its parent. Retain the positional-field baseline and disable finishing in the next trial.

Ten focused behavior checks passed. The packaged protocol check passed with 298 of 300 replies on time, two late replies and zero malformed replies.

## Scoreboards

### Official practice

The following table records **old scoring setup** results. The separate builders-4 rescore of `835d4a7` is **5.21**, user-reported; its run ID and timestamp were not supplied.

| Commit / settings | Score | Squad-proxy mean / official minus proxy | Status / provenance |
| --- | ---: | --- | --- |
| `e922fb0`, steady squad strafe | 4.65 | 5.125, eight-pair proxy | User-reported official score; retain 5.23 baseline. |
| `f2a61ab`, laser during reload | 4.96 | 6.25, eight-pair proxy | User-reported official score; trial reverted. |
| `4933656`, active attacker priority | 4.90 | — | User-reported official practice score; restore the `835d4a7` target weighting. |
| `8d52f44`, dedicated practice policy | 5.00 | — | User-reported official practice score. |
| `6d086c3`, reload behind cover | 5.19 | — | User-reported official practice score. Finished 0.04 below the `835d4a7` positional-field baseline. |
| `67f32ba`, finish approach | 5.08 | — | User-reported official practice score. |
| `835d4a7`, positional field | **5.23** | — | User-reported official practice score. Retained as the baseline for the finish approach trial. |
| `c5aeebba81a5`, default, second run | **5.23** | — | Best reported official practice score. User-reported rerun of the 5.17 shared-torso entry. |
| `405bcde`, size-aware ground routing | 5.21 | — | User-reported official practice score. Working baseline for the positional-field trial. |
| `b99a6135379f`, gun-only drum magazine | 5.02 | — | User-reported official practice score. |
| `d8e77944b48b`, corner duel with gun-only drum magazine | 5.06 | — | User-reported official practice score. |
| `10fb916`, corner duel with shared-torso aim | 5.21 | — | User-reported official practice score. |
| `4d02e84`, supply drops and late-circle play with shared-torso gun aim | 5.13 | — | User-reported official practice score for the combined version. |
| `c68975862d2b`, supply drops and late-circle play with legacy gun aim | 5.17 | 5.56 on the 16-seed validation panel | User-reported official practice score. |
| `47291ba`, packaged cornered boost, cover recovery and spacing | 4.88 | Unknown | User-reported official trial. Scored 0.02 below the `26db76c` cornered-dodge trial and 0.29 below the then-best 5.17. |
| `4991fa6`, default | **5.17** | 3.81 / +1.36; approximate control, see note | First reported entry to reach 5.17. User confirmed commit and defaults; submission time and run ID unknown. |
| `c5aeebb`, default | **5.17** | 3.875 / +1.295; approximate candidate, see note | First reported shared-torso run. Submission time and run ID unknown. |
| `fb85097`, default | 5.10 | 3.33 / +1.77; approximate candidate, see note | Threat spacing with shared aim; user-reported score. Submission time and run ID unknown. |
| `37d1a1d`, default | 5.06 | 8.50 / −3.44; approximate candidate, see note | Combat cube restraint; user-reported score. Submission time and run ID unknown. |
| `ded4a9c`, default | 4.81 | Unknown | Squad cover and weapon readiness; user-reported score. No local placement screen, submission time or run ID recorded. |
| `ee4f342`, default | 5.04 | 5.125 / −0.085; approximate candidate, see note | Recovery enabled by default; user reported score. Submission time and run ID unknown. |
| `9ceca70`, presumed default | 5.06 | 5.75 / −0.69; approximate first control, see note | User reported current repository result; recovery defaults to legacy. Submission time, run ID, and environment overrides unknown. |
| `26db76c`, packaged cornered dodge | **4.90** | 4.52 / +0.38 on the 50-pair holdout | User-reported official trial, 0.27 below champion. [Trial record](m6_cornered_boost.md#official-result) |
| `184bb55`, default | 4.88 | 3.81 / +1.07; approximate control, see note | Previously reported official baseline; submission time and run ID unknown. |
| `2646e82` | 2.92 | 3.19 / −0.27 | Commit inferred from timestamp. |
| `9a73729` | 2.71 | 3.06 / −0.35 | Reported baseline. |
| `a528856` | 2.56 | Unknown | Commit association unverified. |

The comparison is **official score minus local squad-proxy mean**, not a prediction error against identical matches. The 3.81 control used `184bb55` with a dirty experimental patch and `BOT_GUN_AIM_CHECK=legacy`, simulator `e322ffe`, seeds 420100–420115 (16 matches); it approximates both default policies but is not a verified exact-commit run for either, and had 14 late/invalid responses. The 3.19 and 3.06 means used simulator `e322ffe` and seeds 420000–420015 (16 matches). Official and proxy seeds and opponents differ, and local timing varies; these differences do not establish predictive accuracy. See [calibration and raw-result details](experiments-history.md#squad-proxy-calibration-against-official-practice).

The 5.75 proxy control used the P01 dirty candidate tree based on `e224892`, with recovery disabled and seeds 420200–420215; it was not an exact-commit run of `9ceca70`. A repeat of that control averaged 5.00, illustrating timing variation. The 5.06 result is attributed to `9ceca70` as the current repository implementation, assuming default settings; confirm the submitted commit and environment if available.

The 5.125 proxy candidate used that same dirty tree and seeds with `BOT_SQUAD_RECOVERY=cover`; it predates `ee4f342` and is not an exact-commit run. Its difference from the official score is not a calibrated prediction error.

The 8.50 cube-restraint estimate is the eight-match P02 split screen on seeds 420320–420327, with recovery off; the 3.875 shared-aim estimate is the 16-match historical screen on seeds 420100–420115. Both used simulator `e322ffe` and dirty experimental trees, not verified exact-commit runs of the official candidates. Their timing and small-sample caveats are recorded below and in the [historical shared-aim record](experiments-history.md#candidate-shared-torso-gun-aim).

The 3.33 spacing estimate is the six-match P05 screen on seeds 420500–420505 with simulator `e322ffe`, before spacing became the default. It used a dirty experimental tree rather than a verified exact-commit run; see the [P05 record](#p05-navigation-probes-and-comparison).

`4991fa6` defaults to the integrated policy with `BOT_GUN_AIM_CHECK=legacy`. Its opt-in gun-aim change was **not active** in the reported 5.17 result; do not attribute the change in score to it. Fixed practice seeds do not eliminate runtime timing noise. The 5.17 versus 4.88 score difference has no paired match-level uncertainty.

### FFA

The best FFA candidate is **undetermined**. The gun-aim candidate's local FFA screen is recorded in the [historical FFA table](experiments-history.md#local-ffa-performance); a single lineup and 16 pairs do not establish a champion. FFA remains separate from the practice scoreboard and is deferred while qualification practice is the priority.

## Supply drops and late-circle practice play

The scored commit `c68975862d2b` used the gun aim and movement settings from the earlier 5.17 entry (`4991fa6`). When squad play is active and there is no immediate danger, the bot values reachable supply drops more highly as its health falls. It estimates travel, landing and capture time against the zone deadline and holds inside the ring. When the next radius reaches 140 m with more than three mechs alive, it switches to selective engagement. At three remaining it resumes squad combat. That commit shipped with `BOT_LATE_HIDE=1`, `BOT_NAV_METHOD=legacy` and `BOT_GUN_AIM_CHECK=legacy`.

| Squad-proxy panel | Official 5.17 build | Drops only | Drops and late-circle play | Also rush laser |
| --- | ---: | ---: | ---: | ---: |
| 12 native pairs, 422715–422726 | 3.42 | 4.08 | 4.17 | — |
| 10 restricted-container matches per build, 423815–423824 | 5.50 | — | 6.20 | 7.50 |
| 16 native matches per build, 422890–422905 | 5.19 | — | 5.56 | 4.63 |

The final 16 seeds were fresh for the champion and laser variant. The simpler candidate ran afterward in a separate block on those same starts. Its mean paired gain was +0.38 with a 95% seed-bootstrap interval of [-0.69, 1.62]. On that panel the simpler candidate recorded zero captures and zero late or invalid replies. It captured two drops in the 12-seed screen. The three panels support an official trial of the combined policy. Individual gains cannot be attributed to captures alone.

The optional `BOT_LASER_RUSH=1` variant scans for lasers when calm, prioritizes reachable lasers and boosts toward them above 60 energy. It acquired a laser within 30 seconds in 9 of 16 validation matches versus 4 of 16 for the champion, but lost 0.56 placement points per match on that panel. It stays off in the packaged candidate. The official score for `c68975862d2b` was **5.17**.

Commit `4d02e84` combined these supply-drop and late-circle tactics with the shared-torso gun check from `c5aeebba81a5` by setting `BOT_GUN_AIM_CHECK=actual`. It scored **5.13** in official practice, 0.04 below its parent’s 5.17 and 0.10 below the shared-torso entry’s best run.

All panels used simulator `e322ffe`. Local raw evidence is in `mech-testing/tactics-screen-422715/`, `mech-testing/tactics-image-panel/` and `mech-testing/tactics-validation-422890/` (the later comparison is under `drops/`).

## Size-aware ground routing

The official comparator is `d8e77944b48b` (5.06). The new candidate keeps its corner-duel and gun-only magazine settings. A byte per ground cell records the largest standard mech that fits horizontally and vertically, through double spawn size. Each observation supplies the actual radius and height. Larger or borderline dimensions use direct prism checks cached for the current body size. A size change invalidates the route, cover, shelter and unstuck direction. Shortcuts check diagonal side cells, and navigation waits or replans when it has no verified walkable step.

The real map cell at (25, −326) fits the spawn mech and rejects the six-cube footprint. A scripted low bridge admits a small mech and routes a taller one around it. Open ground and diagonal corner clearance were also checked. The packaged bot answered 300/300 protocol observations within 50 ms. Commit `405bcde` scored **5.21** in official practice, 0.15 above its parent. One run leaves the size of the placement benefit uncertain. Retain size-aware routing for its verified clearance behavior and use this build as the positional-field baseline.

## Positional-field practice trial

The packaged trial enables `BOT_POSITIONAL_FIELD=1` on the 5.21 size-aware build (`405bcde`). It keeps the selected combat target. In ground squad combat, two distinct aimed or recent attacking mechs must qualify before the field can choose a route. The field evaluates positions near indexed corners and passages, points on the active route, short radial alternatives and the current position. It ranks endpoints for firing opportunity, exposure, zone margin and uncertain sound bearings. Fresh, reachable loot supplies a small bonus. For the three shortlisted endpoints, it samples each verified approach and penalizes time exposed to overlapping enemy fire. A direct step or a complete size-aware ground path is required. If the search budget expires without a verified choice, the existing corner-duel and combat policies take over.

The bundled grid has 1,644 indexed approach cells. The planner considers up to 24 nearby candidates per update with a 3 ms search budget and a 0.5 s refresh interval. It rechecks the next step during travel. A changed body size or newly detected hunter invalidates the cached choice. The field keeps its score breakdown in memory for scripted checks.

In a controlled corner scenario the bot chose an 18 m sheltered approach over a 12 m crossing with cubes. Under contest container limits it selected moving field goals in 4 of 28 scripted two-hunter map positions. These positions check activation only. The protocol replay returned 300/300 answers within 50 ms (maximum 31.6 ms). Official practice score pending.

### Design and validation plan

Start with one decision in practice: choosing the approach to cover in a multi-hunter encounter. Keep the existing target selection, gun control, emergency dodge and urgent zone rotation. Compare this later candidate with the submitted size-aware build. In the first field trial, loot may break a tie between safe routes. A high-value pickup must never make a blocked or lethal route eligible.

1. **Generate reachable positions.** At build time, index candidate positions near the ends of building walls and around passages on the existing 2 m grid. Include positions on both sides of each corner. At decision time, add the current position and cells on the current route. Start with candidates within 40 m and discard positions outside the current footprint or without a route that beats the zone deadline. Treat the baked spawn-size component as a coarse filter. Verify the actual route at the observed size.
2. **Build a local scalar field.** Give each reachable position a higher score for a usable firing line to the selected target, hard cover against additional hunters, time inside the next circle and a reachable useful pickup. Penalize exposure to multiple shooters and the time spent getting there. Normalize features into bounded ranges. Sample weapon range, recent damage and muzzle-to-body rays for visible mechs. A recently lost track decays with age. A sound contributes a weaker, widening sector based on bearing, distance band and age. Merge compatible sounds with visible tracks and cap overlapping sound penalties. A sound alone cannot establish a firing line or the presence of a second hunter.
3. **Score the approach as well as the endpoint.** Shortlist the best few endpoints, then sample each route at intervals and estimate *seconds exposed to two shooters* using travel distance and current speed. Subtract this cost from destination value. A short run through open ground can lose to a longer route along a wall. Include staying put as a candidate. Recheck the next step every tick and keep the current destination until another offers a meaningful improvement or the route becomes invalid.
4. **Bound the work.** Start with at most 24 endpoints, three shortlisted routes, and one field update every 0.5 game seconds. Re-evaluate sooner on a new attacker, a material zone change or growth. Share one wall-clock allowance (initially 3 ms) across candidate evaluation and routing, inside the controller deadline. On timeout, use the best fully verified route or the existing controller action. The proposed limits are starting values to check in the protocol replay.
5. **Verify behavior before the official trial.** Use a corner with a short exposed approach and a longer sheltered one, a lone sound followed by a confirming sighting, tempting loot beyond an unsafe crossing, and a passage that closes after growth. Assert the route, the reason it won, and the response to an urgent zone. Record a compact breakdown of candidate scores in the local fixture harness. Use the restricted protocol check for latency and official practice for placement.

## Gun-only drum magazine trial

This candidate uses the 5.23 shared-torso settings with corner duels, supply-drop pursuit and late-circle hiding disabled. When the gun is the only equipped weapon, drum magazine takes priority over gun damage and fire rate. Plating, armor and nanites retain priority over the magazine. Equipping a secondary restores the original upgrade order. Official score **5.02** at `b99a6135379f`.

## Corner duel with gun-only drum magazine

This candidate uses the corner-duel configuration from `10fb916` (official score **5.21**) and the gun-only magazine preference from `b99a613`. Comparing it with `10fb916` tests the upgrade preference while holding combat tactics fixed. Official score **5.06** at `d8e77944b48b`.

## Corner duel practice trial

The packaged candidate uses the settings of the 5.23 shared-torso entry (`c5aeebba81a5`) and enables `BOT_CORNER_DUEL=1`. Supply-drop pursuit and late-circle hiding are disabled for this comparison. During inferred squad play, two mechs with open firing lines must be aiming toward us or have damaged us within three seconds. The controller checks reachable ground positions 6 or 12 m away for a shot on a single exposed hunter, favors lower HP, and skips cube detours during the maneuver. Open ground falls back to the existing policy. An urgent zone takes priority.

Three scripted controller checks passed. The packaged image answered 300 of 300 protocol observations within 50 ms. Commit `10fb916` scored **5.21** in official practice, between the baseline’s two reported runs of 5.17 and 5.23. The effect of the corner tactic remains inconclusive.

## Active practice candidates

The initial order is recovery, farming, positioning, aiming, and navigation; trace evidence can change it. One narrow candidate from each of P01–P05 has been tested officially. Each is described and challenged in the [implementation plan](practice-improvement-plan.md).

### Earlier dev experiments

| Version / commit | Change and reason | Simulated result | Official score | Status |
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
### Practice candidate index

| ID | Priority / candidate | Expected mechanism | Main risk | Status |
| --- | --- | --- | --- | --- |
| P01 | 1. [Recovery and disengagement](practice-improvement-plan.md#p01-recovery-and-disengagement) | Survive repeat encounters by reaching cover and allowing health regeneration. | Shared vision and pursuit prevent a safe break; retreat can expose rear armor. | Official 5.04; inconclusive versus timing noise; [record](#p01-first-recovery-screen) |
| P02 | 2. [Efficient farming](practice-improvement-plan.md#p02-efficient-farming) | Acquire damage, health, upgrades, and useful weapons early at favorable cost. | Farming delays kills and costs health or zone time. | Cube-restraint test 5.06; [record](#p02-split-screen) |
| P03 | 3. [Anti-squad positioning](practice-improvement-plan.md#p03-anti-squad-positioning) | Limit simultaneous enemy firing angles while retaining our own opportunities to deal damage. | Cover can block our shots, permit encirclement, or delay kills. | Cover/readiness test 4.81; [record](#official-positioning-candidate) |
| P04 | 4. [Aiming and kill conversion](practice-improvement-plan.md#p04-aiming-and-kill-conversion) | Land more shots and finish reachable threats to shorten fights. | Prediction errors or target fixation can reduce damage and increase exposure. | Shared-aim runs 5.17 and 5.23; [record](#official-shared-aim-candidate) |
| P05 | 5. [Navigation and zone pressure](practice-improvement-plan.md#p05-navigation-and-zone-pressure) | Reduce exposure and zone damage with better movement decisions. | Spacing can reduce damage dealt; cover or early rotation can delay kills. | Spacing scored 5.10 officially; [record](#p05-navigation-probes-and-comparison) |

The previous [shared-torso gun-aim experiment](experiments-history.md#candidate-shared-torso-gun-aim) was locally inconclusive. Its squad comparison had asymmetric late/invalid responses; its FFA comparison is not evidence of practice improvement. Its official test tied the best reported score, which does not establish a performance difference.

### P01 first recovery screen

- Parent `e224892` (documentation-only successor to `4991fa6`); dirty bot hash `b4bf4835573443275996ba3ed90be92863d81f4eb77806f110e8833b6c3906d7`, diff SHA-256 `d8e9ccb6d4a796ab8d9887644a8bcbee7c0c4caf5e1faf7a626ca4bb35b650c8`; saved local patch `mech-testing/p01-recovery-candidate.diff`. The local experiment used `BOT_SQUAD_RECOVERY=legacy` as control and `cover` as candidate. Commit `ee4f342` enabled `cover` by default for its official test; later commits returned to `legacy`.
- Baseline traces for seeds 420100, 420101 and 420108 show periods below 55% HP and firing during those periods; HP also increased during all three matches, so the traces do not establish an absence of healing. Raw traces: `mech-testing/p01-baseline-{420100,420101,420108}.jsonl`.
- Candidate sustains a cover retreat for up to 10 seconds, holds fire while recovering, and yields to an urgent zone, a threat within 35 m, a finishing opportunity, or unavailable cover. Hypothesis: a longer damage-free interval enables regeneration and improves placement. Counter-hypothesis: lost damage, shared enemy vision and exposure while retreating outweigh healing. Focused controller scenarios pass; they do not establish actual healing in a match. An already charged laser can release when its trigger is dropped.
- Squad proxy `e322ffe`, seeds 420200–420215, 16 matches per pass, run in order baseline → candidate → repeated baseline: means **5.75 → 5.125 → 5.00**, candidate minus first **−0.625 ± 0.584 SE**, repeated control minus first **−0.75 ± 0.423 SE**, candidate minus repeated control **+0.125 ± 0.407 SE**. Kills: 3.69 / 2.88 / 2.94; mean survival: 211.08 / 204.00 / 202.92 s; late/invalid: 2/2, 1/1, 2/2. Raw result: `mech-testing/p01-recovery-squad-420200.json`. Sequential ordering and timing-sensitive searches confound comparisons; matched seeds can diverge.
- Official `ee4f342`, default recovery enabled: **5.04**, reported by user; submission time and run ID unknown. Difference from best reported 5.17 is −0.13, but the 5.06 run with recovery off and repeated local controls demonstrate variability; no causal conclusion follows from aggregate scores.
- Decision: **investigate; retain 5.17 official champion**. Capture candidate and control traces with recovery-state and healing-window measurements for further investigation. FFA deferred.

### P02 first farming screen

- Parent `ee4f342`; recovery forced off in all variants to approximate the 5.17 policy while its official recovery test is pending. Dirty bot SHA-256 `a72861c975e2253fd2af7d39897e325e4a8b8c100d0812e3000975183b434978`, diff SHA-256 `66a6c6f6c0d73ae2cffa7d068ef91bef63c936cf009091896767da63f330a0fb`; saved local patch `mech-testing/p02-farming-candidate.diff`. Farming defaults to `legacy`; `BOT_SQUAD_FARMING=selective` enables the candidate.
- Hypothesis: prioritize pickups with unobstructed nearby paths and near-term upgrades, penalize stale NPC targets while valuing weakened ones, and avoid cube detours during active combat. Counter-hypothesis: an approximate blocked-line penalty rejects worthwhile routes; avoiding combat cubes forfeits upgrades and healing; these bundled changes cannot individually explain any outcome. The focused blocked-versus-clear cube scenario passed.
- Squad proxy `e322ffe`, seeds 420300–420307, 8 matches per pass in baseline → candidate → repeated-baseline order: means **4.50 → 3.875 → 4.875**; candidate minus first **−0.625 ± 0.625 SE**, repeated control minus first **+0.375 ± 0.420 SE**, candidate minus repeated control **−1.00 ± 0.732 SE**. Kills 2.375 / 1.875 / 2.75; survival 151.85 / 144.73 / 165.03 s; late/invalid 0/0 each. Raw result `mech-testing/p02-farming-squad-420300.json`. Small sample and sequential timing variation prevent a firm conclusion.
- Decision after this screen: **investigate**. The subsequent split and official cube-restraint result are recorded below; FFA deferred.

### P02 split screen

- Parent `ee4f342` with `BOT_SQUAD_RECOVERY=legacy` in every variant; dirty bot SHA-256 `f9629b50a8bdffe39a230c103ebdd208e3c2d848ac3d29ab5918f06ed26eb608`, diff SHA-256 `8db1d46d39aa981ad3fdd6d6329691ae696961e73c03306f183b2100818537e1`, saved patch `mech-testing/p02-split-candidate.diff`. `BOT_SQUAD_FARMING=route` changes objective scoring; `cubes` disables combat cube detours; `legacy` is the control. Both factors remain opt-in. They separate the previous bundled hypothesis, but the route variant still combines several scoring changes.
- Squad proxy `e322ffe`, seeds 420320–420327, eight matches each, sequential baseline → route → cubes → baseline: means **8.625 / 8.625 / 8.50 / 7.25**. Versus first control, route **0.00 ± 1.363 SE**, cubes **−0.125 ± 0.789 SE**, repeat control **−1.375 ± 1.267 SE**. Versus repeated control, route **+1.375 ± 1.164 SE**, cubes **+1.25 ± 1.221 SE**. Late/invalid counts 2/2, 4/4, 1/1, 0/0 respectively. Raw result `mech-testing/p02-split-squad-420320.json`. Small samples, differing late counts, order effects and substantial control variation preclude a conclusion.
- Official `37d1a1d`, default `cubes`, recovery disabled: **5.06**, user-reported, compared with 5.17 baseline; submission time and run ID unknown. Difference −0.11 is comparable in size to observed repeat variability and does not establish causation. Route remains a separate opt-in policy. Best official practice score remains 5.17.

### P05 navigation probes and comparison

- Base `c5aeebb`, default shared-torso gun aim retained. Five squad-proxy traces on seeds 420400–420404 produced 9, 3, 3, 10 and 7 placement points; all ended before a win. Each showed substantial gun damage; observed multi-enemy proximity varied from about 5 to 75 seconds. One trace had 2.7 seconds outside the zone and 270 observed zone damage. Commanded movement with low measured speed varied from 0.2 to 12.3 seconds, but includes ordinary acceleration and fighting, not necessarily stalls. Last observations and end events do not always unambiguously identify the lethal source. These proxy observations motivate combat spacing and cover as well as earlier rotation; they do not establish official-engine death causes. Raw traces `mech-testing/p05-probe-{420400,420401,420402,420403,420404}.jsonl`.
- Screened independent `BOT_NAV_METHOD` variants: `spacing` penalizes close proximity to observed enemies, especially lightning; `cover` increases the penalty for visibility to secondary enemies; `early_zone` starts rotation earlier. `legacy` is the prior behavior. Risk: spacing sacrifices firing angles, cover reduces damage or costs computation, and early rotation abandons fights. Squad proxy `e322ffe`, six pairs on 420500–420505, sequential legacy → spacing → cover → early_zone → repeated legacy. Local results select among approaches, not certify an official improvement.
- Mean points: **3.33 / 3.33 / 2.33 / 3.00 / 2.67**; candidate-minus-first-control ± SE: spacing **0.00 ± 0.68**, cover **−1.00 ± 0.68**, early zone **−0.33 ± 0.56**; repeated control **−0.67 ± 0.42**. Versus repeated control: spacing **+0.67 ± 0.71**, cover **−0.33 ± 0.33**, early zone **+0.33 ± 0.56**. Mean kills: 1.83 / 2.17 / 1.00 / 1.50 / 1.33; late/invalid: 0/0, 0/0, 4/4, 0/0, 1/1. Sequential order, timing variation, and six seeds make all estimates uncertain. Raw result `mech-testing/p05-navigation-420500.json`; dirty bot SHA-256 `2f4c9b37abd6c890200a1250a40766a527d3ecdc2628d3e8ab03e904a3bf6bc1`, diff SHA-256 `b20201dcf013708c6533a8f7cfa6724509e57162ccaa82d70f128d50d5a618d5`; saved patch `mech-testing/p05-navigation-candidates.diff`. Those hashes identify the screened opt-in versions, before selecting the default.
- Official `fb85097`, default spacing and shared aim: **5.10**, user-reported; submission time and run ID unknown. This is −0.07 versus the 5.17 `c5aeebb` parent, within the range of previously observed variation; the aggregate score does not establish whether spacing helped or hurt.
- Decision: **investigate**; retain the earlier 5.17 official champion. `spacing` is the committed default; `BOT_NAV_METHOD=legacy` restores the prior behavior, while the alternatives remain available. Recovery, farming and squad-cover experiments remain disabled by default; `c5aeebb` shared aim remains enabled.

## Operating loop

### Official positioning candidate

`ded4a9c` returns farming and recovery to `legacy` and enables `BOT_SQUAD_POSITION=cover` by default. In squad combat it seeks cover from an aimed charging laser when our beam is not hot and considers secondary-weapon readiness instead of treating any laser or lightning as ready. Hypothesis: reduce incoming fire while unable to deal effective damage. Risk: hiding can reduce our own damage or delay kills; local score unknown. The protocol replay passed with one late reply on this host. Official score **4.81**, user-reported, −0.36 versus 5.17; time and run ID unknown. Timing noise and no match-level breakdown prevent attributing this difference to the policy; investigate before reusing it.

### Official shared-aim candidate

`c5aeebb` returns positioning, farming and recovery to `legacy` and enables `BOT_GUN_AIM_CHECK=actual` by default. It suppresses a gun trigger when the final shared torso command is aiming elsewhere for the laser or mortar. Hypothesis: avoid wasting ammunition; risk: a later physics tick could align, so withheld fire can reduce damage. The prior local screen is inconclusive and timing-confounded. Protocol replay passed on this host with no late replies. The user reported **5.17 on the first run** and **5.23 on the second run** of the same commit. Submission times and run IDs are unknown.

1. Start from a specific trace, official result, or protocol mechanic. State the tactical alternative, affected situations, expected placement mechanism, counter-hypothesis, and where simulator behavior may not transfer.
2. Challenge the premise in a second reasoning pass. Select a small discriminating scenario and define the decision before looking at results. Prioritize expected placement impact, frequency, transferability, cost, and uncertainty.
3. Run the scenario and screen candidate versus parent on paired **squad-proxy** seeds, starting with 16–32 pairs where feasible. Expand close or consequential comparisons, rotate validation seeds, inspect traces and late/invalid actions, and repeat control against itself to estimate timing noise. The runner executes all seeds of one variant before the next; account for order and machine load. Equal seeds do not make divergent matches identical.
4. For two interacting policies, define a 2×2 comparison (baseline, A, B, A+B), expected interaction, and decision rule in advance. Treat local interactions as exploratory. Use official slots on informative cells only when justified.
5. Before official submission, run protocol, relevant scenario/unit, and restricted-container checks. Submit an exact clean commit; record settings, timestamp, run ID, score, and comparator. Local checks are gates, not proof of official improvement. Official practice is the authority for practice selection.
6. Update the official scoreboard and candidate record; keep raw outcomes and rejected ideas. Revisit interactions and calibrate local versus official candidate-minus-parent deltas over multiple distinct changes. Track FFA separately when that objective resumes.

The published track and status pages have stated **four submissions per hour**, while the team reported six. Verify the live platform limit and cutoff before submitting; until confirmed, plan around four per hour. Keep the best official practice entry, current working champion, and best FFA candidate separate.

## Experiment record template

Give each candidate a stable ID; place detailed records in a linked document as the index grows. Keep official and local results separate and do not infer missing provenance.

```text
ID / status / parent commit and factors / candidate commit and factors:
Observation and evidence (trace, protocol, or official result):
Hypothesis, mechanism, affected situations, expected placement impact:
Counter-hypothesis, failure mode, simulator assumptions:
Discriminating scenario, expected behavior, and decision rule:
Local suite, simulator revision and dirtiness, lineup, seeds, match count:
Paired placement delta ± SE; survival, kills, late/invalid; timing-control results:
Raw result, trace, bot hash, and dirty diff location:
2×2 interaction and predeclared decision, if applicable:
Official submission commit, settings, timestamp, run ID, score, comparator:
Decision (promote / reject / investigate / retest) and next question:
```

## Running and retaining results

```sh
python3 tools/experiment.py --sim competitors/updated/shanmukha-here--eagle-eye-mech-royale \
  --factor BOT_POLICY=legacy,integrated --factor BOT_STRAFE=legacy,steady \
  --seed-start 420000 --seeds 16 --out mech-testing/study.json
```

The runner records per-seed outcomes, factors, paired differences, a two-factor interaction, bot and diff hashes, and simulator revision. The first factor value is control; `BOT_STRAFE` in this example affects only the legacy policy. Without `--opponent` the runner uses the squad proxy; with opponents it runs FFA. Use the same simulator revision and seeds for each comparison and record lineup and runtime conditions. The proxy is not the official engine.

`mech-testing/` is Git-ignored: its raw files and saved diffs are local, not shared by committing documentation. Preserve the exact diff and bot hash for dirty runs, record where artifacts are stored, and arrange durable sharing separately when needed. Missing local files must be marked unavailable, not silently treated as version-controlled evidence.
