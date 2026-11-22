# Evaluation audit

Audited d87f5992a2d7376e66ced0a30747f6dda5e6e51c and local simulator e322ffe872a52ef83a89ab194b6500edc0da36df. The supplied brief is docs/mech_royale_evaluation_codex_plan.md.

## Execution and scoring

The root Dockerfile copies main.py, mechfight.py and bot/ into a Python 3.13 slim image. main.Bot selects Controller by default. BOT_POLICY=legacy selects Strategy. Controller routes observation memory through world.update_perception, engagement through combat.assess_combat and apply_weapon_control, zone urgency and movement priority through Controller.act, pathing/evasion through Movement, and objectives and upgrades through loadout. The controller's 27 ms search deadline and the wire client's 50 ms response budget make trajectories timing-sensitive.

The kit's protocol sections 3–4 specify a public GitHub commit with a root Dockerfile, a 20 MB repository limit, linux/amd64 build within ten minutes, conformance replay and 48 official practice matches. Runtime is unprivileged, offline, read-only with 64 MB /tmp, 1 CPU, 512 MB and 128 processes/threads. Local and official placement award 16 minus place. Kills affect the game but have no additive score component. Historical user-reported practice scores are in docs/experiments.md. Official seed selection, opponent implementation, game build and current platform limits are unavailable from the simulator.

tools/run_local_match.py compiles local_sim/geometry.c, loads Map, constructs Match with an integer seed and shuffled role assignments, and exchanges protocol messages with Client. Each action covers up to two advance calls. The subject greeting seed derives from its slot. Default field is a scripted cooperating squad. --opponent and --opponent-image select FFA. tools/competitor_match.py reads the ignored local lineup. tools/replay_match.py reruns a lineup. --trace logs subject observations/actions and a terminal state. check/check.py plays a fixed stream, and sim/physics.py contains primitives. Neither runs a complete match. Match.obs mutates observation memory and consumes RNG for sounds. Instrument the existing observation exactly once.

## Plan and measurement boundaries

1. Profile the unmodified suite and serial match runner, including a full-trace repeat. Existing unittest discovery runs zero full matches. Experiment cost is variants × seeds (default eight games per variant). The historical P05 screen used 30 matches. There is no single ten-minute test target.
2. Add optional runner-side telemetry after Client.act and at termination. Store existing events losslessly, sample self state and accepted movement/fire commands, fingerprint starting layout, and read fatal_source/fatal_weapon and phase directly from the pinned simulator. Save a source snapshot, hashes and effective bot settings. Use fresh consecutive seeds and retain terminal windows. Internal goals, field weights, LOS, collision reasons and decisions cannot be recovered reliably from wire actions. Hit events include crates and NPCs. Actors can persist in vision memory. A trigger is not proof of discharge.
3. After reporting baseline measurements, select focused existing controller and geometry fixtures as deterministic L0/L1 probes. Full duels, contested pickups, enclosure escape and late-game transitions need engine state and actor setup or curated full-match seeds. No checkpoint save/restore contract exists. The small closed-loop legacy fixture integrates XY commands only. Avoid presenting it as an engine simulation.
4. Extend existing paired analysis for three-way screening and independent confirmation. Use common initial fingerprints and fixed field identity. Reuse immutable local sources. Parallelize independent decision tests first; concurrent deadline-sensitive games require separate CPU capacity and timing controls. Keep manual official results distinct from proxy evidence.

## Unmodified runtime profile

On this Mac, /usr/bin/time -p python3 -m unittest discover -s tests -v passed 79 tests in 0.402 s (0.63 s wall, 0.47 user, 0.10 system). Serial squad seeds 421000–421002 took 6.82, 15.98 and 6.89 s wall. Mean 9.90 s, median 6.89 s, nearest-rank p95 15.98 s (only three observations). Aggregate process-tree CPU was 92% of one core from user+system divided by elapsed time. Seed 421000 repeated with full JSONL took 6.27 s versus 6.82 untraced, with game time 228.1 versus 227.8 s. This single repeat cannot resolve trace overhead. Commands from repository root:

```sh
SIM=competitors/updated/ß
/usr/bin/time -p python3 -m unittest discover -s tests -v
for s in 421000 421001 421002; do
  /usr/bin/time -p python3 tools/run_local_match.py --sim "$SIM" --kit . --bot main.py --seed "$s"
done
/usr/bin/time -p python3 tools/run_local_match.py --sim "$SIM" --kit . --bot main.py --seed 421000 --trace /tmp/full.jsonl
/usr/bin/time -p cc -O3 -shared -fPIC "$SIM/local_sim/geometry.c" -lm -o /tmp/botted-profile-geometry.so
```

Standalone geometry compilation took 0.34 s wall. The full trace occupied 5.1 MiB on disk. On its 2,282 predecoded steps, six alternating-order passes through tools/bench_observer.py measured median loop times of 0.35 ms off, 7.63 ms for compact telemetry (130,299 bytes) and 82.96 ms for full trace (4,958,227 bytes reserialized). The compact observer added about 3.2 microseconds per step in this workload. This isolates CPU and buffered writes; it excludes bot deadlines, terminal emission and startup. Measure simulator preparation and handshake separately via ready_seconds (includes compile_seconds) in the baseline summaries. Existing performance varies strongly by seed.
