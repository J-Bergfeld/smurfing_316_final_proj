"""Mode selection, positioning and inventory decisions."""
import math
from .geometry import distance, angle_diff
from .positioning import Positioner
from .loadout import pickup_slot


class Strategy:
    def __init__(self, arena, combat, config, profile='practice', navigation=None):
        self.arena, self.combat, self.config, self.profile = arena, combat, config, profile
        self.navigation = navigation
        self.mode = 'hold'; self.until = None; self.positioner = Positioner(arena)
        self.waypoint = None; self.route_until = 0; self.route_goal = None; self.path = []; self.history = []
        self.projectile_replan_at = 0
        self.zone_urgent = False
        self.target_id = None

    def choose(self, world):
        obs = world.obs; me = obs['self']; now = obs['t']; enemies = world.enemies()
        first_decision = self.until is None
        if first_decision: self.until = now + 2.5
        def target_cost(track):
            actor = track['actor']
            return (distance(me['pos'],actor['pos'])*.5 + actor.get('hp',1400)*.09
                    + (0 if track['visible'] else 60) - (15 if actor['id']==self.target_id else 0))
        previous_target = self.target_id
        closest = min(enemies,key=target_cost,default=None)
        close_visible = [e for e in enemies if e['visible'] and distance(me['pos'],e['actor']['pos']) < 45]
        if close_visible:
            closest = min(close_visible,key=lambda e:distance(me['pos'],e['actor']['pos']))
        self.target_id = closest['actor']['id'] if closest else None
        d = distance(me['pos'],closest['actor']['pos']) if closest else 9999
        recent = now-world.last_damage < 2
        zone = obs['zone']; next_d = distance(me['pos'],zone['next_center'])
        urgency = not me.get('in_zone',True) or (next_d > zone['next_radius']-20 and now + max(0,next_d-zone['next_radius']+25)/max(1,me['stats'].get('walk_speed',11.7)) > zone['shrink_end']-4)
        edge_gap = zone['radius'] - distance(me['pos'],zone['center'])
        remaining = max(1,zone['shrink_end']-max(now,zone['shrink_start']))
        edge_speed = max(0,zone['radius']-zone['next_radius']+distance(zone['center'],zone['next_center']))/remaining
        if now >= zone['shrink_start']-14 and next_d > zone['next_radius']-20:
            urgency = urgency or edge_gap < 22 + min(14,max(0,now+14-zone['shrink_start']))*edge_speed
        if urgency and not self.zone_urgent: self.positioner.goal_until = 0
        self.zone_urgent = urgency
        # Target preference may favor a weak enemy farther away; do not let it
        # hide a different opponent who is an immediate danger.
        visible_threat = any(e['visible'] and distance(me['pos'],e['actor']['pos']) < 160 for e in enemies)
        nearby_count = sum(distance(me['pos'],e['actor']['pos'])<220 and e['confidence']>.3 for e in enemies)
        engaged = bool(closest and ((self.mode=='attack' and previous_target==closest['actor']['id']) or (recent and world.last_damage_by==closest['actor']['id'])))
        ratio = self.combat.estimate(me,closest['actor'],nearby_count,engaged=engaged) if closest else 0
        nearby = [e['actor'] for e in enemies if e['visible'] and distance(me['pos'],e['actor']['pos']) < 180]
        projectile_threat = world.projectile_risk(me['pos']) > .15
        # A second nearby combatant is enough to disengage an existing fight;
        # before engaging, require evidence that two enemies face each other.
        fighting = any(abs(angle_diff(a.get('aim',[0])[0], math.atan2(b['pos'][1]-a['pos'][1], b['pos'][0]-a['pos'][0]))) < .35 for a in nearby for b in nearby if a['id'] != b['id'] and distance(a['pos'],b['pos'])<200)
        third_party = self.profile == 'final' and (fighting or (self.mode == 'attack' and len(nearby)>=2))
        if urgency or third_party: proposed = 'flee'
        elif recent or visible_threat:
            # Later circles require more willingness to commit than the opening.
            threshold = 1.35 if now < 100 and obs['alive'] > 9 else (1.0 if obs['alive'] > 4 else .7)
            proposed = 'attack' if ratio > threshold and not third_party else 'flee'
        elif me['hp'] < me['max_hp']*.9 and me.get('in_zone',True) and not projectile_threat: proposed = 'recover'
        elif world.loot or obs.get('drops'): proposed = 'loot'
        else: proposed = 'hold'
        if projectile_threat and proposed != 'attack': proposed = 'flee'
        emergency = urgency or recent or projectile_threat or bool(visible_threat and self.mode not in ('attack','flee')) or third_party
        if proposed != self.mode and (first_decision or now >= self.until or emergency):
            self.mode = proposed; self.until = now + (1.5 if proposed in ('attack','flee') else 2.5); self.positioner.goal_until = 0
        elif projectile_threat and now >= self.projectile_replan_at:
            self.positioner.goal_until = 0
            self.projectile_replan_at = now + .3
        return self.mode, closest, urgency

    def goal_for(self, world, mode, enemy, urgent):
        return self.positioner.goal_for(world, mode, enemy, urgent)

    def movement(self, world, goal, urgent, mode=None, enemy=None):
        obs=world.obs; me=obs['self']; p=me['pos']; now=obs['t']; arena=self.arena
        self.history.append((now,p[:2])); self.history = [v for v in self.history if now-v[0]<1.5]
        stuck = len(self.history)>5 and now-self.history[0][0]>1 and distance(p,self.history[0][1])<2 and distance(p,goal)>8
        while self.path and distance(p,self.path[0])<6 and abs(p[2]-self.path[0][2])<3:
            self.path.pop(0)
        changed = self.route_goal is None or distance(goal,self.route_goal)>12 or abs(goal[2]-self.route_goal[2])>3
        if changed or stuck or not self.path or now >= self.route_until:
            path = self.navigation.route(p,goal,me['energy']) if self.navigation else None
            if not path:
                fallback = arena.route(p,goal,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9))
                path = [fallback or goal]
            self.path=path; self.route_until=now+1.5
            self.route_goal=goal[:]
        waypoint=self.path[0]
        elevated = waypoint[2]-p[2]>3 and distance(p,waypoint)<40
        dx,dy=waypoint[0]-p[0],waypoint[1]-p[1]; d=math.hypot(dx,dy)
        move=[dx/d,dy/d] if d>2 else [0,0]
        if mode == 'attack' and enemy and enemy['visible'] and distance(p,goal)<8 and me['grounded']:
            target=enemy['actor']['pos']; ex,ey=target[0]-p[0],target[1]-p[1]; ed=math.hypot(ex,ey)
            if ed>1:
                side=1 if int(now/2.5)%2==0 else -1
                sx,sy=-ey/ed*side,ex/ed*side
                zone=obs['zone']; nx,ny=p[0]+sx*5,p[1]+sy*5
                safe = arena.supported(nx,ny,p[2],me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)) if hasattr(arena,'supported') else arena.walkable(nx,ny,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9))
                if safe and distance((nx,ny),zone['center']) < zone['radius']-5:
                    move=[sx*.65,sy*.65]
        jet = elevated or (stuck and me['energy']>35)
        return {'move':move,'jump':bool(jet and me['grounded']), 'boost':bool((jet and not me['grounded']) or (urgent and me['energy']>20 and d>20))}

    def inventory(self, world):
        obs=world.obs; me=obs['self']; out={}; offer=obs.get('offer')
        priorities={'nanites':10,'armor':9,'plating':8,'servos':7,'jets':6,'reactor':6,'gun_mag':6,'laser_charge':6,'laser_damage':6,'gun_damage':5,'sensors':5}
        if offer: out['pick']=max(range(len(offer['choices'])),key=lambda i:priorities.get(offer['choices'][i]['id'],3))
        for item in sorted(obs.get('pickups',[]),key=lambda i: distance(me['pos'],i['pos'])):
            if distance(me['pos'],item['pos']) > self.config.get('loot',{}).get('pickup_radius',4) or abs(me['pos'][2]-item['pos'][2])>4: continue
            want, slot = pickup_slot(item,world)
            if want:
                out['take']=item['id']
                if slot is not None: out['drop']=slot
                break
        return out
