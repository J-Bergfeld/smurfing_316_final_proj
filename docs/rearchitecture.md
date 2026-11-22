# Tactical rearchitecture candidate

The submission image enables `BOT_TACTICAL_PLANNER=1`. During a grounded,
non-emergency fight, the controller evaluates nine short reachable moves
jointly, instead of choosing combat positioning and then diverting to cubes
through separate priority rules. It considers firing opportunity and weapon
readiness, exposure at two points along each move, additional crossfire,
spacing, nearby cubes, and the predicted zone. It accounts for the reduced
movement speed while charging a laser and adds a small preference for the
previous selection. Immediate projectile avoidance, urgent zone rotation,
unsticking, aiming, inventory decisions and long-distance navigation retain
their existing controllers. Set `BOT_TACTICAL_PLANNER=0` to restore the previous
movement selection; the Dockerfile's other settings are unchanged.

The planner uses approximate map visibility and a one-second horizon; it is
not a physics simulation. It considers at most three recent threats, stops on
a cooperative four-millisecond budget and discards an incomplete search in
favor of the previous policy. Geometry calls cannot be preempted. The model
may give up useful damage or fail to predict enemy movement, so official
practice remains necessary. In particular, the repository's historical local
calibration did not reliably rank official scores.

Validation on the development host: 168 unit tests passed (15 skipped); the restricted linux/amd64 container
passed the 300-observation protocol replay with zero late or invalid replies
(one older queued observation dropped). A single squad-proxy smoke match,
seed 425100, finished ninth with two kills and zero late or invalid replies.
This match is not a predictive performance comparison. Container execution
was emulated on an ARM host, and the replay is recorded rather than reactive.
