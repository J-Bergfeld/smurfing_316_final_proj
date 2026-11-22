"""Choose a verified ground route during a multi-hunter practice encounter."""
import math
import time
from collections import defaultdict

from .geometry import angle_diff, zone_at


def corner_cells(width, height, blocked):
    """Sample corner approaches and passages on the 2 m static grid."""
    for y in range(3, height - 3, 3):
        for x in range(3, width - 3, 3):
            i = y * width + x
            if blocked[i]:
                continue
            corners = [blocked[i + dy*width + dx] for dy in (-3, 3) for dx in (-3, 3)]
            passage = (blocked[i-3] and blocked[i+3]) or (blocked[i-3*width] and blocked[i+3*width])
            if sum(corners) in (1, 3) or passage:
                yield i


def corner_index(world):
    bins = defaultdict(list)
    grid = world.baked
    if grid:
        width = grid['nx']
        cells = grid.get('field_cells')
        if cells is None:
            cells = corner_cells(width, grid['ny'], grid['blocked'])
        for i in cells:
            point = tuple(world.cell_pos((i % width, i // width)))
            bins[math.floor(point[0]/40), math.floor(point[1]/40)].append(point)
    return bins


class PositionalField:
    def __init__(self, world):
        self.world = world
        self.anchors = corner_index(world)
        self.route = []
        self.key = None
        self.refresh = 0.
        self.sounds = []
        self.breakdown = {}

    def hear(self, obs):
        now = obs['t']
        self.sounds = [s for s in self.sounds if now - s[0] < 2]
        for sound in obs.get('sounds', []):
            if sound['kind'] in ('gun', 'laser', 'laser_charge', 'lightning', 'mortar'):
                self.sounds.append((now-sound['age'], tuple(obs['self']['pos'][:2]),
                                    sound['bearing'], sound['dist']))
        self.sounds = self.sounds[-12:]

    def candidates(self, start, previous, path):
        bx, by = (math.floor(v/40) for v in start)
        nearby = [p for x in range(bx-1,bx+2) for y in range(by-1,by+2)
                  for p in self.anchors.get((x,y), ()) if math.dist(start,p) <= 40]
        points = [start, *previous, *(self.world.cell_pos(c) for c in path[2:18:5])]
        points.extend(sorted(nearby, key=lambda p: math.dist(start,p))[:12])
        for radius in (12, 28):
            for i in range(8):
                a = i*math.pi/4
                points.append((start[0]+radius*math.cos(a), start[1]+radius*math.sin(a)))
        return list(dict.fromkeys(p for p in points if math.dist(start,p) <= 40))[:24]

    def steer(self, start):
        while self.route and math.dist(start,self.route[0]) <= .8:
            self.route.pop(0)
        if not self.route:
            return [0.,0.]
        point = self.route[0]
        if not self.world.line_walkable(start,point):
            self.route.clear()
            self.key = None
            return None
        d = math.dist(start,point)
        return [(point[0]-start[0])/d,(point[1]-start[1])/d]

    def sound_sectors(self, now, threats):
        # Ignore bearings consistent with a tracked shooter; an anonymous sound
        # can tilt a score but cannot activate the field or count as a shooter.
        sectors = []
        for heard, origin, yaw, band in self.sounds:
            age = now-heard
            width = .25+.15*age
            def matches(muzzle):
                d = math.dist(origin,muzzle[:2])
                category = 'near' if d < 60 else 'mid' if d < 160 else 'far'
                return category == band and abs(angle_diff(math.atan2(muzzle[1]-origin[1],muzzle[0]-origin[0]),yaw)) < width
            if age < 2 and not any(matches(m) for m,_,_ in threats):
                sectors.append((origin,yaw,width,(1-age/2)*{'near':1.,'mid':.5,'far':.2}[band]))

        return sectors

    def hunters(self, state, now, start):
        threats = []
        active = []
        for ident, tr in state.tracks.items():
            actor, age = tr['actor'], now-tr['seen']
            if actor['kind'] != 'mech' or age > 2.5:
                continue
            p = actor['pos']
            reach = max((state.cfg['weapons'][w].get('range',200) for w in actor['weapons']), default=0)
            if math.dist(start,p[:2]) > reach + 40:
                continue
            facing = math.atan2(start[1]-p[1],start[0]-p[0])
            hit = now-state.attacker_memory.get(ident,-100) < 3
            if not hit and abs(angle_diff(facing,actor['aim'][0])) > .22:
                continue
            if age == 0 and (tr['los'] or hit):
                active.append(ident)
            scale = 1 + actor.get('cubes',0)*state.cfg['cubes']['size_per_cube']
            muzzle = (*p[:2], p[2]+state.cfg['mech']['muzzle_height']*scale)
            threats.append((muzzle, reach, 1-age/2.5))

        return threats, active

    def choose(self, state, obs, target):
        now, me, zone = obs['t'], obs['self'], obs['zone']
        start = tuple(me['pos'][:2])
        stats = me['stats']
        deadline = min(time.perf_counter()+.003, state.action_deadline)
        threats, active = self.hunters(state, now, start)
        context = (target['id'] if target else None, state.body_size, tuple(zone['next_center']), zone['next_radius'])
        # Finish the verified step when its own cover hides the second hunter.
        if (active and self.breakdown and self.key and self.key[1:] == context
                and set(active) <= self.key[0] and now < self.refresh):
            return self.steer(start)
        if len(active) < 2 or target is None:
            self.key = None
            self.route.clear()
            self.breakdown.clear()
            return None
        key = (frozenset(active), *context)
        if self.key == key and now < self.refresh:
            return self.steer(start) if self.breakdown else None
        previous = self.route[-1:] if self.key == key else []
        self.key, self.refresh = key, now+.5
        self.route, self.breakdown = [], {}
        candidates = self.candidates(start, previous, state.movement.path)
        sectors = self.sound_sectors(now, threats)
        exposure = {}
        def lines(point):
            if point not in exposure:
                chest = (*point,self.world.walk_at(*point)+stats['height']*.6)
                exposure[point] = sum(weight for muzzle,reach,weight in threats
                                      if math.dist(point,muzzle[:2]) <= reach and self.world.shot_clear(muzzle,chest))
            return exposure[point]

        target_pos = target['pos']
        height = state.cfg['mech']['height']*(1+target.get('cubes',0)*state.cfg['cubes']['size_per_cube'])
        center = (*target_pos[:2],target_pos[2]+height*.5)
        reach = max((w['stats'].get('range',200) for w in me['weapons'] if w),default=0)
        speed = max(1.,stats['walk_speed'])
        def zone_margin(point, elapsed):
            cx,cy,r = zone_at(state.hold,zone,now+elapsed)
            return r-math.hypot(point[0]-cx,point[1]-cy)-stats['radius']

        shortlist = []
        held = {w['kind'] for w in me['weapons'] if w}
        loot = [item['pos'] for kind,item,when in state.items.values()
                if now-when <= 4 and (kind=='cubes' or (kind=='pickups' and item['kind']=='laser' and 'laser' not in held))]
        for point in candidates:
            if time.perf_counter() > deadline-.0015:
                break
            d = math.dist(start,point)
            if zone_margin(point,d/speed+1) <= 0 or not self.world.free_cell(self.world.cell(*point)):
                continue
            if math.dist(point,target_pos[:2]) > reach*.96 or lines(point) >= 1.99:
                continue
            muzzle = (*point,self.world.walk_at(*point)+stats['muzzle_height'])
            if not self.world.shot_clear(muzzle,center):
                continue
            sound = max((weight*max(0.,1-abs(angle_diff(math.atan2(point[1]-origin[1],point[0]-origin[0]),yaw))/width)
                         for origin,yaw,width,weight in sectors if point != origin), default=0.)
            bonus = .08 if any(math.dist(point,p[:2]) < 4 and abs(muzzle[2]-stats['muzzle_height']-p[2]) < 3.6
                               and self.world.line_walkable(point,p) for p in loot) else 0.
            next_margin = zone['next_radius'] - math.dist(point, zone['next_center'])
            zone_value = .25 * max(-1., min(1., next_margin/20))
            score = zone_value + bonus - .3*sound - .5*lines(point) - .2*d/speed
            if previous and point == previous[0]:
                score += .25
            shortlist.append((score,point))
        best = -math.inf
        for base, goal in sorted(shortlist,reverse=True)[:3]:
            if time.perf_counter() >= deadline:
                break
            route = [goal]
            if not self.world.line_walkable(start,goal):
                if not self.world.free_cell(self.world.cell(*start)):
                    continue
                cells, complete = self.world.path(start,goal,budget_s=max(0.,(deadline-time.perf_counter())*.5))
                if not complete:
                    continue
                route = [self.world.cell_pos(c) for c in cells[1:]] + [goal]
            elapsed = exposed = 0.
            a = start
            for b in route:
                if time.perf_counter() >= deadline or not self.world.line_walkable(a,b):
                    break
                length = math.dist(a,b)
                steps = max(1, math.ceil(length/6))
                dt = length/(steps*speed)
                for j in range(steps):
                    f = (j+.5)/steps
                    q = (a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f)
                    if time.perf_counter() >= deadline or zone_margin(q,elapsed+dt) <= 0:
                        break
                    exposed += dt * min(1.,max(0.,lines(q)-1))
                    elapsed += dt
                else:
                    a = b
                    continue
                break
            else:
                total = base - 3*exposed - .25*elapsed
                if total > best and zone_margin(goal,elapsed+1)>0 and time.perf_counter() <= deadline:
                    best, self.route = total, list(route)
                    self.breakdown = dict(goal=goal,score=total,endpoint=base,
                                          dual_exposure_s=exposed,travel_s=elapsed)
        return self.steer(start) if self.breakdown else None
