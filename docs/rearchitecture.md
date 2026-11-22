# Pressure controller and reference integration

The image runs the integrated Python pressure controller with threat memory,
retreat, supply objectives, weapon-aware spacing, route steering, roof
access, exposure holding and laser peeking. Immediate projectile avoidance
and urgent zone rotation retain priority. `BOT_DECISION_POLICY=classic`
selects the earlier coordinator. The tactical planner is a separate classic
controller experiment and is not enabled in the image.

Gun aim uses live projectile speed and bounded per-opponent virtual-shot
history, with a damped default while evidence accumulates. It can aim at an
exposed upper body. Laser release considers rear and cook-off multipliers;
observed enemy laser shots inform target selection during cooldown. Movement
considers projectile height, relative motion, direct mortar impacts, laser
occlusion and lightning carriers. A bounded surface search supports roof
travel, jet climbs, drops and reachable rooftop loot. Pressure steering
evaluates up to 34 movement choices. Repeated distant beams ending near
another mech can signal a free-for-all. Memory cleanup checks proximity range
and tree trunks; exploration sight also checks canopy attenuation.

The surface search can return partial routes and remains an approximation of
the reference's overland graph. The movement and opponent models are also
approximations rather than a full port of the reference engine.

Run `python3 -m unittest discover -s tests -q` for internal tests. The recorded
protocol checker verifies response format and timing; it is not a reactive
game or a performance comparison.
