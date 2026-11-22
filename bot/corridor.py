"""Compare a short covered combat route with the controller's actual move."""
import math
import time
from collections import Counter

from .geometry import angle_diff, zone_at


def incoming_risk(world, point, chest, target_pos, attackers):
    """Estimate visible incoming lines, including rear exposure while aiming."""
    facing = math.atan2(target_pos[1]-point[1], target_pos[0]-point[0])
    risk = 0.
    for _, muzzle, reach, weight in attackers:
        if math.dist(point,muzzle[:2]) > reach or not world.shot_clear(muzzle,chest):
            continue
        bearing = math.atan2(muzzle[1]-point[1], muzzle[0]-point[0])
        rear = abs(angle_diff(bearing, facing)) > math.pi*.5
        risk += weight*(1.5 if rear else 1.)
    return risk


def potential_cover(world, point):
    """Cheap bounded near-wall proxy, not a claim about a hidden shooter."""
    grid = getattr(world, 'baked', None)
    if not grid:
        return 0.
    x,y = world.cell(*point)
    if not (0 <= x < grid['nx'] and 0 <= y < grid['ny']):
        return 0.
    return max(0., min(1., (6-grid['clearance'][y*grid['nx']+x])/6))


class FightCorridor:
    def __init__(self, field):
        self.field = field
        self.route = []
        self.key = None
        self.until = 0.
        self.retry_at = 0.
        self.breakdown = {}
        self.metrics = Counter()

    def clear(self):
        self.route = []
        self.key = None
        self.breakdown = {}

    def choose(self, state, obs, target, baseline_move):
        self.metrics['calls'] += 1
        now, me, zone = obs['t'], obs['self'], obs['zone']
        start = tuple(me['pos'][:2]); world = state.world
        if target is None or not me['grounded']:
            self.clear()
            return None
        if state.action_deadline-time.perf_counter() < .004:
            self.metrics['budget_skipped'] += 1
            return None
        deadline = min(state.action_deadline, time.perf_counter() + .005)
        speed = max(1., me['stats']['walk_speed']); radius = me['stats']['radius']
        target_pos = target['pos']; target_id = target['id']
        # Keep a near-lethal target in the baseline's existing finish behavior.
        if target.get('hp', math.inf) <= .2*target.get('max_hp', 1400):
            self.clear()
            return None
        threats = []
        for ident, tr in state.tracks.items():
            actor = tr['actor']; age = now-tr['seen']
            if ident == target_id or actor['kind'] != 'mech' or age > 2.5:
                continue
            pos = actor['pos']; dist = math.dist(start, pos[:2])
            reach = max((state.cfg['weapons'].get(w, {}).get('range', 0) for w in actor.get('weapons', [])), default=0)
            if dist > max(180, reach+30):
                continue
            velocity = actor.get('vel', [0,0,0])
            closing = ((start[0]-pos[0])*velocity[0]+(start[1]-pos[1])*velocity[1])/max(1,dist)
            bearing = math.atan2(start[1]-pos[1], start[0]-pos[0])
            aimed = abs(angle_diff(actor['aim'][0],bearing)) < .22
            recent = now-state.attacker_memory.get(ident, -100) < 3
            if not (recent or aimed or closing > 2):
                continue
            weight = (1. if recent or aimed else .55) * max(.2, 1-age/3)
            scale = 1+actor.get('cubes',0)*state.cfg['cubes'].get('size_per_cube',.05)
            muzzle = (pos[0],pos[1],pos[2]+state.cfg['mech']['muzzle_height']*scale)
            threats.append((ident,muzzle,max(reach,60),weight))
        if obs['alive'] > 12 and not threats:
            self.clear()
            return None
        # Quantized positions force a rescore when a known hunter moves materially.
        threat_key = tuple(sorted((ident, round(p[0]/5), round(p[1]/5), round(weight*4))
                                  for ident,p,_,weight in threats))
        damage_key = tuple(sorted((k,round(v,1)) for k,v in state.attacker_memory.items() if now-v < 3))
        key = (target_id, round(target_pos[0]/5), round(target_pos[1]/5), state.body_size,
               tuple(zone['next_center']), zone['next_radius'], threat_key, damage_key)
        if self.key != key:
            self.clear(); self.retry_at = 0
        if not self.route and now < self.retry_at:
            return None
        scale = 1+target.get('cubes',0)*state.cfg['cubes'].get('size_per_cube',.05)
        center = (*target_pos[:2],target_pos[2]+state.cfg['mech']['height']*scale*.5)
        reach = max((w['stats'].get('range',0) for w in me['weapons'] if w),default=0)
        if reach <= 0 or time.perf_counter() >= deadline:
            return None
        ready = any(w and w.get('cooldown',0) <= .3 and
                    (w['kind'] != 'gun' or (w.get('ammo',0)>0 and w.get('reload',0)<=.3))
                    for w in me['weapons'])
        sectors = self.field.sound_sectors(now, [(p,r,w) for _,p,r,w in threats]) if hasattr(self.field,'sound_sectors') else []
        target_reach = max((state.cfg['weapons'].get(w,{}).get('range',0)
                            for w in target.get('weapons',[])),default=0)
        target_muzzle = (*target_pos[:2],target_pos[2]+state.cfg['mech']['muzzle_height']*scale)
        # Include target fire separately; it is not an additional hunter.
        incoming = list(threats)
        if target_reach > 0:
            incoming.append((target_id,target_muzzle,target_reach,1.))
        walk_cache = {}
        shot_cache = {}
        danger_cache = {}

        def walk(a,b):
            key_ = (tuple(a[:2]),tuple(b[:2]))
            if key_ not in walk_cache:
                walk_cache[key_] = world.line_walkable(a,b)
            return walk_cache[key_]

        def margin(point, elapsed):
            cx,cy,r = zone_at(state.hold,zone,now+elapsed)
            return r-math.hypot(point[0]-cx,point[1]-cy)-radius

        def shot(point):
            if point not in shot_cache:
                muzzle = (*point,world.walk_at(*point)+me['stats']['muzzle_height'])
                shot_cache[point] = math.dist(point,target_pos[:2]) <= reach*.96 and world.shot_clear(muzzle,center)
            return shot_cache[point]

        def danger(point):
            if point in danger_cache:
                return danger_cache[point]
            chest = (*point,world.walk_at(*point)+me['stats']['height']*.6)
            value = incoming_risk(world,point,chest,target_pos,incoming)
            for origin,yaw,width,weight in sectors:
                if point != origin:
                    err = abs(angle_diff(math.atan2(point[1]-origin[1],point[0]-origin[0]),yaw))
                    value += .25*weight*max(0.,1-err/width)
            danger_cache[point] = value
            return value

        def exit_ok(goal, elapsed):
            dx,dy=zone['next_center'][0]-goal[0],zone['next_center'][1]-goal[1]
            norm=math.hypot(dx,dy)
            if norm < 1: dx,dy=1.,0.
            else: dx,dy=dx/norm,dy/norm
            for x,y in ((dx,dy),(-dy,dx),(dy,-dx)):
                q=(goal[0]+8*x,goal[1]+8*y)
                if margin(q,elapsed+3)>0 and walk(goal,q):
                    return True
            return False

        def valid_route(route):
            a=start; elapsed=0.; samples=[]
            for b in route:
                if time.perf_counter() >= deadline or not walk(a,b): return None
                length=math.dist(a,b); elapsed+=length/speed
                for f in (.5,1.):
                    q=(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f)
                    if margin(q,elapsed+2)<=0: return None
                    samples.append(q)
                a=b
            if not samples or not shot(route[-1]) or not exit_ok(route[-1],elapsed): return None
            # At most one sample may lose line of fire; penalize it below.
            if sum(not shot(q) for q in samples) > 1: return None
            return samples,elapsed

        def value(samples,elapsed):
            return (-2*sum(danger(q) for q in samples)/len(samples)
                    -(1.5 if ready else .6)*sum(not shot(q) for q in samples)/len(samples)
                    +.5*potential_cover(world,samples[-1])
                    -.15*elapsed)

        if self.route and self.key == key and now < self.until:
            while self.route and math.dist(start,self.route[0]) < 1:
                self.route.pop(0)
            if self.route and valid_route(self.route) is not None:
                d=math.dist(start,self.route[0])
                self.metrics['cache_steps'] += 1
                return [(self.route[0][0]-start[0])/d,(self.route[0][1]-start[1])/d]
        self.clear(); self.key=key
        if time.perf_counter() >= deadline:
            self.retry_at=now+.4
            return None
        # Evaluate the movement actually selected by the baseline controller.
        mag=math.hypot(*baseline_move)
        base_end=(start[0]+baseline_move[0]*speed, start[1]+baseline_move[1]*speed)
        if mag < .01 or not walk(start,base_end): base_end=start
        midpoint=((start[0]+base_end[0])*.5,(start[1]+base_end[1])*.5)
        base=value([midpoint,base_end],1.)
        best=base+.35; chosen=None; examined=0
        for point in self.field.candidates(start,[],state.movement.path)[:8]:
            if time.perf_counter() >= deadline: break
            distance=math.dist(start,point)
            if distance < 4 or distance > 40: continue
            examined+=1
            route=[point]
            if not walk(start,point):
                if not hasattr(world,'path') or time.perf_counter() >= deadline-.0005: continue
                cells,complete=world.path(start,point,budget_s=max(0.,(deadline-time.perf_counter())*.45))
                if not complete or len(cells)<2: continue
                middle=world.cell_pos(cells[len(cells)//2])
                route=[middle,point]
            checked=valid_route(route)
            if checked is None: continue
            samples,elapsed=checked
            score=value(samples,elapsed)
            if score>best and time.perf_counter()<deadline:
                best,chosen=score,route
        if chosen is None:
            self.metrics['no_route'] += 1
            if time.perf_counter() >= deadline:
                self.metrics['deadline_exhausted'] += 1
            self.retry_at=now+.4
            return None
        self.route,self.key,self.until=chosen,key,now+.5
        self.breakdown={'goal':chosen[-1],'score':best,'baseline':base,'examined':examined}
        self.metrics['routes_selected'] += 1
        while self.route and math.dist(start,self.route[0]) < 1:
            self.route.pop(0)
        if not self.route:
            self.clear()
            return None
        d=math.dist(start,self.route[0])
        return [(self.route[0][0]-start[0])/d,(self.route[0][1]-start[1])/d]
