"""Mode selection, positioning and inventory decisions."""
import math
from .geometry import distance, angle_diff


class Strategy:
    def __init__(self, arena, combat, config, profile='practice'):
        self.arena, self.combat, self.config, self.profile = arena, combat, config, profile
        self.mode = 'hold'; self.until = None; self.goal = None; self.goal_until = 0
        self.waypoint = None; self.route_until = 0; self.history = []

    def choose(self, world):
        obs = world.obs; me = obs['self']; now = obs['t']; enemies = world.enemies()
        if self.until is None: self.until = now + 2.5
        closest = min(enemies,key=lambda e:distance(me['pos'],e['actor']['pos']),default=None)
        d = distance(me['pos'],closest['actor']['pos']) if closest else 9999
        recent = now-world.last_damage < 2
        zone = obs['zone']; next_d = distance(me['pos'],zone['next_center'])
        urgency = not me.get('in_zone',True) or (next_d > zone['next_radius']-20 and now + max(0,next_d-zone['next_radius']+25)/max(1,me['stats'].get('walk_speed',11.7)) > zone['shrink_end']-4)
        visible_threat = closest and closest['visible'] and d < 160
        ratio = self.combat.estimate(me,closest['actor'],len(enemies)) if closest else 0
        nearby = [e['actor'] for e in enemies if e['visible'] and distance(me['pos'],e['actor']['pos']) < 180]
        # A second nearby combatant is enough to disengage an existing fight;
        # before engaging, require evidence that two enemies face each other.
        fighting = any(abs(angle_diff(a.get('aim',[0])[0], math.atan2(b['pos'][1]-a['pos'][1], b['pos'][0]-a['pos'][0]))) < .35 for a in nearby for b in nearby if a['id'] != b['id'] and distance(a['pos'],b['pos'])<200)
        third_party = self.profile == 'final' and (fighting or (self.mode == 'attack' and len(nearby)>=2))
        if urgency or third_party: proposed = 'flee'
        elif recent or visible_threat:
            proposed = 'attack' if ratio > (1.3 if now < 100 else .9) and not third_party else 'flee'
        elif any(obs.get(k) for k in ('cubes','pickups','crates','drops')): proposed = 'loot'
        else: proposed = 'hold'
        projectile_threat = any(distance(me['pos'], q['pos']) < 35 and (q['vel'][0]*(me['pos'][0]-q['pos'][0])+q['vel'][1]*(me['pos'][1]-q['pos'][1])) > 0 for q in obs.get('projectiles', []))
        if projectile_threat and proposed != 'attack': proposed = 'flee'
        emergency = urgency or recent or projectile_threat or bool(visible_threat and self.mode not in ('attack','flee')) or third_party
        if proposed != self.mode and (now >= self.until or emergency):
            self.mode = proposed; self.until = now + (1.5 if proposed in ('attack','flee') else 2.5); self.goal_until = 0
        return self.mode, closest, urgency

    def goal_for(self, world, mode, enemy, urgent):
        obs = world.obs; me = obs['self']; now = obs['t']; p = me['pos']; z = obs['zone']; arena = self.arena
        if now < self.goal_until and self.goal is not None and not urgent: return self.goal
        candidates = [(p[:],0)]
        for radius in (25,55,100):
            for i in range(12):
                a = i*math.pi/6; x = p[0]+radius*math.cos(a); y = p[1]+radius*math.sin(a)
                if arena.walkable(x,y,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)):
                    candidates.append(([x,y,arena.height(x,y)],0))
        candidates.append(([z['next_center'][0],z['next_center'][1],arena.height(*z['next_center'])],0))
        if mode == 'loot':
            for key, reward in (('cubes',42),('pickups',38),('crates',22),('drops',45)):
                for item in obs.get(key,[]):
                    if key=='pickups' and any(w and w['kind']==item['kind'] for w in me['weapons']): continue
                    if key=='drops' and item.get('lands_in',0)>15: continue
                    candidates.append((item['pos'],reward))
        def score(item):
            pos, reward = item; travel = distance(p,pos); outside = max(0,distance(pos,z['next_center'])-max(0,z['next_radius']-18))
            value = reward - travel*.18 - outside*(2 if urgent else .4) - world.threat(pos)*70
            if enemy:
                ed = distance(pos,enemy['actor']['pos']); old = distance(p,enemy['actor']['pos'])
                if mode=='flee': value += (ed-old)*.5
                if mode=='attack': value -= abs(ed-100)*.13
                if mode in ('flee','hold'):
                    a=[pos[0],pos[1],pos[2]+7]; b=enemy['actor']['pos'][:2]+[enemy['actor']['pos'][2]+7]
                    if not arena.clear(a,b): value += 25
            if urgent: value -= distance(pos,z['next_center'])*.6
            return value
        self.goal = list(max(candidates,key=score)[0]); self.goal_until = now+1.5
        return self.goal

    def movement(self, world, goal, urgent):
        obs=world.obs; me=obs['self']; p=me['pos']; now=obs['t']; arena=self.arena
        self.history.append((now,p[:2])); self.history = [v for v in self.history if now-v[0]<1.5]
        stuck = len(self.history)>5 and now-self.history[0][0]>1 and distance(p,self.history[0][1])<2 and distance(p,goal)>8
        elevated = goal[2]-p[2]>3 and distance(p,goal)<40
        if elevated and me['energy']>25:
            waypoint=goal
        elif now >= self.route_until or stuck or self.waypoint is None or distance(p,self.waypoint)<6:
            self.waypoint=arena.route(p,goal,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)); self.route_until=now+1.5
            waypoint=self.waypoint or goal
        else: waypoint=self.waypoint
        dx,dy=waypoint[0]-p[0],waypoint[1]-p[1]; d=math.hypot(dx,dy)
        move=[dx/d,dy/d] if d>2 else [0,0]
        jet = elevated or (stuck and me['energy']>35)
        return {'move':move,'jump':bool(jet and me['grounded']), 'boost':bool((jet and not me['grounded']) or (urgent and me['energy']>20 and d>20))}

    def inventory(self, world):
        obs=world.obs; me=obs['self']; out={}; offer=obs.get('offer')
        priorities={'nanites':10,'armor':9,'plating':8,'servos':7,'jets':6,'reactor':6,'gun_mag':6,'laser_charge':6,'laser_damage':6,'gun_damage':5,'sensors':5}
        if offer: out['pick']=max(range(len(offer['choices'])),key=lambda i:priorities.get(offer['choices'][i]['id'],3))
        held=[w['kind'] for w in me['weapons'] if w]
        rank={'laser':4,'lightning':3,'gun':2,'mortar':1}
        for item in sorted(obs.get('pickups',[]),key=lambda i: distance(me['pos'],i['pos'])):
            if distance(me['pos'],item['pos']) > self.config.get('loot',{}).get('pickup_radius',4) or abs(me['pos'][2]-item['pos'][2])>4 or item['kind'] in held: continue
            empty=next((i for i,w in enumerate(me['weapons']) if w is None),None)
            if empty is not None: out['take']=item['id']; break
            worst=min(range(len(me['weapons'])),key=lambda i:rank.get(me['weapons'][i]['kind'],0))
            w=me['weapons'][worst]
            if rank.get(item['kind'],0)>rank.get(w['kind'],0) and not (w['kind']=='laser' and w.get('charge',0)>0): out.update(take=item['id'],drop=worst); break
        return out
