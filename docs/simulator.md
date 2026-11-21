# Simulator

The in-repository engine is **not complete**. `sim/physics.py` currently provides isolated movement,
turning, circle, projectile and healing primitives with unit tests; it does not run matches. Do not use
these primitives as a score prediction.

Until a complete engine is implemented and calibrated, `tools/experiment.py` runs the external local
simulator described in [local-simulator.md](local-simulator.md). Without `--opponent` it uses that
simulator's squad proxy; with opponents it uses FFA. Record its revision and treat results as diagnostics.

Still needed: match state and 16 actors; map collision and roofs; observations and protocol timing;
weapons and damage; loot, NPCs and zone phases; house-squad and FFA policies; replay and calibration.
Compare mechanics to the recorded stream, and score rankings to several official submissions before
using simulation to select changes. The real house behavior remains unknown.
