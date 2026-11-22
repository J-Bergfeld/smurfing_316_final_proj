"""Bounded, short-horizon position selection for contested fights.

This is deliberately a geometric approximation, not a physics simulator. Long
routes, immediate projectile dodges, weapon control and zone emergencies remain
the responsibility of the controller.
"""
import math
import time

from .geometry import angle_diff, zone_at


class TacticalPlanner:
    def __init__(self, world):
        self.world = world
        self.previous = None
        self.context = None

    def choose(self, state, obs, target):
        me, now = obs['self'], obs['t']
        start = me['pos'][:2]
        threats = []
        for ident, track in state.tracks.items():
            actor, age = track['actor'], now - track['seen']
            if actor['kind'] != 'mech' or age > 1.5:
                continue
            distance = math.dist(start, actor['pos'][:2])
            reach = max((state.cfg['weapons'].get(w, {}).get('range', 200)
                         for w in actor.get('weapons', [])), default=0)
            if distance > reach + 20:
                continue
            facing = math.atan2(start[1]-actor['pos'][1], start[0]-actor['pos'][0])
            active = (abs(angle_diff(facing, actor['aim'][0])) < .4 or
                      now-state.attacker_memory.get(ident, -100) < 3)
            if not active and (not target or ident != target['id']):
                continue
            scale = 1 + actor.get('cubes', 0)*state.cfg['cubes']['size_per_cube']
            muzzle = (*actor['pos'][:2], actor['pos'][2]+state.cfg['mech']['muzzle_height']*scale)
            threats.append((distance, ident, actor, muzzle, reach, (1-age/2)* (1. if active else .45)))
        threats.sort(key=lambda item: item[0])
        threats = threats[:3]
        if not threats or target is None or target['kind'] != 'mech':
            self.previous = self.context = None
            return None

        # Do not let a partial search replace the existing movement policy.
        deadline = min(state.action_deadline - .002, time.perf_counter() + .004)
        if time.perf_counter() >= deadline:
            return None
        stats = me['stats']
        speed = stats['walk_speed'] * (.5 if any(w and w['kind'] == 'laser' and w.get('charge', 0) > 0 for w in me['weapons']) else 1.)
        step = max(4., min(12., speed * 1.0))
        ready = any(w and ((w['kind'] == 'gun' and w.get('ammo', 0) > 0 and w.get('reload', 0) <= .25)
                           or (w['kind'] == 'laser' and w.get('cooldown', 0) <= .25)
                           or (w['kind'] == 'lightning' and me['energy'] >= w['stats'].get('energy', 3)))
                    for w in me['weapons'])
        reach = max((w['stats'].get('range', 0) for w in me['weapons'] if w), default=0)
        scale = 1 + target.get('cubes', 0)*state.cfg['cubes']['size_per_cube']
        center = (*target['pos'][:2], target['pos'][2] + state.cfg['mech']['height']*scale*.5)
        context = (target['id'], state.body_size, tuple(obs['zone']['next_center']), obs['zone']['next_radius'])
        loot = [item['pos'] for kind, item, seen in state.items.values()
                if kind == 'cubes' and now-seen < 2 and math.dist(start, item['pos'][:2]) < 25]
        candidates = [(0., 0.)] + [(math.cos(i*math.pi/4), math.sin(i*math.pi/4)) for i in range(8)]
        scored = []
        for dx, dy in candidates:
            if time.perf_counter() >= deadline:
                return None
            end = (start[0]+dx*step, start[1]+dy*step)
            if (dx or dy) and not self.world.line_walkable(start, end):
                continue
            cx, cy, radius = zone_at(state.hold, obs['zone'], now+step/max(1., speed)+1)
            if math.dist(end, (cx, cy)) + stats['radius'] >= radius:
                continue
            exposure = 0.
            for fraction in (.5, 1.):
                q = (start[0]+dx*step*fraction, start[1]+dy*step*fraction)
                chest = (*q, self.world.walk_at(*q)+stats['height']*.6)
                lines = sum(weight for _, _, _, muzzle, enemy_reach, weight in threats
                            if math.dist(q, muzzle[:2]) <= enemy_reach and self.world.shot_clear(muzzle, chest))
                exposure += lines*.5 + max(0., lines-1)*.6
            muzzle = (*end, self.world.walk_at(*end)+stats['muzzle_height'])
            distance = math.dist(end, target['pos'][:2])
            shot = distance < reach*.96 and self.world.shot_clear(muzzle, center)
            score = -1.4*exposure + (1.5 if ready else .25)*shot
            if dx or dy:
                score += .1
            # Keep a workable distance without sacrificing a shot to chase.
            score -= max(0., 55-distance)*.012 + max(0., distance-150)*.005
            if loot:
                score += max(max(0., 1-math.dist(end, p[:2])/18)*.2 for p in loot)
            if self.context == context and self.previous is not None:
                score += max(0., 1-math.dist(end, self.previous)/step)*.18
            scored.append((score, end, (dx, dy)))
        if time.perf_counter() >= deadline or not scored:
            return None
        _, self.previous, move = max(scored, key=lambda row: row[0])
        self.context = context
        return list(move)
