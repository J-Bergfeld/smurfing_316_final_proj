"""Small, deterministic rule primitives for the local match engine."""
import math


def future_circle(zone, now, horizon):
    """Advance the already-current circle toward its next phase."""
    start = max(now, zone['shrink_start'])
    remaining = zone['shrink_end'] - start
    elapsed = max(0., now + horizon - start)
    fraction = min(1., elapsed / remaining) if remaining > 0 else (1. if now >= zone['shrink_end'] else 0.)
    center = tuple(zone['center'][i] + (zone['next_center'][i]-zone['center'][i])*fraction for i in range(2))
    radius = zone['radius'] + (zone['next_radius']-zone['radius'])*fraction
    return center, max(0., radius)


def accelerate(velocity, command, speed, acceleration, dt):
    """Approach commanded horizontal velocity with a bounded acceleration."""
    magnitude = math.hypot(*command)
    scale = max(1., magnitude)
    desired = (command[0]*speed/scale, command[1]*speed/scale)
    delta = (desired[0]-velocity[0], desired[1]-velocity[1])
    length = math.hypot(*delta)
    fraction = min(1., acceleration*dt/length) if length else 0.
    return tuple(velocity[i]+delta[i]*fraction for i in range(2))


def turn(actual, desired, yaw_rate, pitch_rate, dt):
    diff = math.remainder(desired[0]-actual[0], math.tau)
    yaw = actual[0] + max(-yaw_rate*dt, min(yaw_rate*dt, diff))
    pitch = actual[1] + max(-pitch_rate*dt, min(pitch_rate*dt, desired[1]-actual[1]))
    return [math.remainder(yaw, math.tau), pitch]


def projectile(origin, velocity, gravity, elapsed):
    return [origin[0]+velocity[0]*elapsed, origin[1]+velocity[1]*elapsed,
            origin[2]+velocity[2]*elapsed-.5*gravity*elapsed*elapsed]


def regen(hp, maximum, elapsed_since_damage, delay, per_second, dt, in_zone=True):
    if not in_zone or elapsed_since_damage <= delay:
        return hp
    effective = min(dt, elapsed_since_damage-delay)
    return min(maximum, hp+per_second*effective)
