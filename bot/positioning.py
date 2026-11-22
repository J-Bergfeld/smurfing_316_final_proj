"""Replaceable tactical position scoring over ground and roof candidates."""
import math
import os
import time
from .geometry import distance
from .loadout import pickup_slot
from .ranges import desired_distance


class Positioner:
    def __init__(self, arena):
        self.arena = arena
        self.goal = None
        self.goal_until = 0
        self.reloading = None
        self.last_laser_shot = -1000
        self.reload_origin = None
        self.peek_until = 0
        self.objective = None
        self.objective_since = 0
        self.ignored = {}
        self.laser_peek = os.getenv('BOT_LASER_PEEK', 'off') == 'on'
        self.range_position = os.getenv('BOT_RANGE_POSITION', 'off') == 'on'
        self.last_peek_at = -1000
        self.practice_economy = os.getenv('BOT_ECONOMY', 'legacy') == 'adaptive'

    def goal_for(self, world, mode, enemy, urgent):
        obs = world.obs; me = obs['self']; now = obs['t']; p = me['pos']; z = obs['zone']; arena = self.arena
        guns = [w for w in me['weapons'] if w and w['kind']=='gun']
        reloading = bool(guns and any(w.get('reload',0)>0 or w.get('ammo',1) <= max(1,w.get('stats',{}).get('mag',12)*.25) for w in guns))
        if reloading and not self.reloading:
            self.reload_origin = p[:]
        if self.reloading is not None and self.reloading != reloading:
            self.goal_until = 0
            if not reloading: self.peek_until = now + 2
        if world.laser_shot_at > self.last_laser_shot:
            self.goal_until = 0
            self.last_laser_shot = world.laser_shot_at
        self.reloading = reloading
        # Reacquire a recently seen target from the nearest clear position once
        # the laser is ready. The normal post-shot cover scoring handles retreat.
        lasers = [w for w in me['weapons'] if w and w['kind']=='laser']
        if (self.laser_peek and not urgent and mode == 'attack' and enemy and lasers
                and now-world.laser_shot_at < 5 and now-enemy['updated'] < 2
                and lasers[0].get('cooldown',0) <= .3 and me.get('grounded',True)):
            ep=enemy['actor']['pos']; target=[ep[0],ep[1],ep[2]+4.5]
            muzzle=me.get('stats',{}).get('muzzle_height',7)
            if not arena.clear([p[0],p[1],p[2]+muzzle],target):
                radius=me.get('stats',{}).get('radius',2.5); height=me.get('stats',{}).get('height',9)
                for step in (6,12,18):
                    options=[]
                    for i in range(16):
                        a=i*math.pi/8; dx,dy=math.cos(a),math.sin(a)
                        x,y=p[0]+dx*step,p[1]+dy*step
                        if distance((x,y),z['center']) > z['radius']-5: continue
                        def supported(t):
                            sx,sy=p[0]+dx*step*t,p[1]+dy*step*t
                            return arena.supported(sx,sy,p[2],radius,height) if hasattr(arena,'supported') else arena.walkable(sx,sy,radius,height)
                        if not all(supported(t) for t in (.25,.5,.75,1)): continue
                        q=[x,y,p[2]]
                        if arena.clear([x,y,p[2]+muzzle],target): options.append(q)
                    if options:
                        self.last_peek_at = now
                        self.goal=min(options,key=world.threat); self.goal_until=now+.25
                        return self.goal
        if now < self.goal_until and self.goal is not None: return self.goal
        candidates = [(p[:],0)]
        for radius in (25,55,100):
            for i in range(8):
                a = i*math.pi/4; x = p[0]+radius*math.cos(a); y = p[1]+radius*math.sin(a)
                if arena.walkable(x,y,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)):
                    candidates.append(([x,y,arena.height(x,y)],0))
        # Rotate toward the near side of the next circle, not automatically its center.
        center=z['next_center']; dx,dy=p[0]-center[0],p[1]-center[1]; d=math.hypot(dx,dy)
        edge=max(0,z['next_radius']-25)
        if d>edge and d>0: zx,zy=center[0]+dx/d*edge,center[1]+dy/d*edge
        else: zx,zy=p[0],p[1]
        candidates.append(([zx,zy,arena.height(zx,zy)],0))
        if enemy and mode in ('attack', 'hold') and me['energy'] > 55 and hasattr(arena, 'roof_candidates'):
            for roof in arena.roof_candidates(p):
                if max(0, roof[2]-p[2]) < me['energy']*.5:
                    candidates.append((roof, 10 if distance(p,enemy['actor']['pos']) > 90 else 2))
        if mode == 'loot':
            self.ignored = {ident:until for ident,until in self.ignored.items() if until > now}
            if self.objective is not None and now-self.objective_since > 30:
                self.ignored[self.objective] = now+60
                self.objective = None
            for key, reward in (('cubes',42),('pickups',38),('crates',22),('drops',45)):
                items = obs.get(key,[]) if key == 'drops' else [v['item'] for v in world.loot.values() if v['kind'] == key]
                for item in items:
                    if item.get('id') in self.ignored: continue
                    if key=='pickups' and not pickup_slot(item,world)[0]: continue
                    if key=='drops':
                        if item.get('lands_in',0)>15 or item.get('holder') not in (None,me['id']): continue
                        if any(t['confidence']>.3 and distance(t['actor']['pos'],item['pos'])<120 for t in world.enemies()): continue
                        arrival=distance(p,item['pos'])/max(1,me['stats'].get('walk_speed',11.7))
                        if now + arrival + item.get('capture_s',4) > z['shrink_end'] and distance(item['pos'],z['next_center']) > z['next_radius']-10: continue
                    bonus = 25 * (1-me['hp']/max(1,me['max_hp'])) if key=='drops' else 0
                    if self.practice_economy and world.field == 'squad' and key == 'pickups' and item.get('kind') == 'laser' and not any(w and w['kind']=='laser' for w in me['weapons']):
                        bonus += 35
                    if key == 'crates':
                        if me['hp'] < .55*me['max_hp'] or me.get('cubes',0) >= world.config.get('cubes',{}).get('stat_cap',10): continue
                        dx,dy=p[0]-item['pos'][0],p[1]-item['pos'][1]; length=math.hypot(dx,dy)
                        if length < 1: dx,dy,length=1,0,1
                        stand=[item['pos'][0]+dx/length*25,item['pos'][1]+dy/length*25,arena.height(item['pos'][0]+dx/length*25,item['pos'][1]+dy/length*25)]
                        if arena.walkable(stand[0],stand[1],me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)):
                            candidates.append((stand,reward+bonus))
                    else:
                        candidates.append((item['pos'],reward+bonus))
            farm_health = .5 if self.practice_economy and world.field == 'squad' else .7
            if me['hp'] > farm_health*me['max_hp'] and me.get('cubes',0) < world.config.get('cubes',{}).get('stat_cap',10):
                for track in world.tracks.values():
                    actor=track['actor']
                    if actor['kind']!='npc' or not track['visible'] or distance(p,actor['pos'])>110: continue
                    dx,dy=p[0]-actor['pos'][0],p[1]-actor['pos'][1]; length=max(1,math.hypot(dx,dy))
                    x,y=actor['pos'][0]+dx/length*50,actor['pos'][1]+dy/length*50
                    if arena.walkable(x,y,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)):
                        candidates.append(([x,y,arena.height(x,y)],30))
        held={w['kind'] for w in me['weapons'] if w}
        hostile_weapons=enemy['actor'].get('weapons',[]) if enemy else []
        desired = 35 if 'lightning' in held and 'laser' not in held else 120
        if 'lightning' in hostile_weapons and ('gun' in held or 'laser' in held): desired=max(desired,75)
        if self.range_position: desired = desired_distance(me,enemy['actor'] if enemy else None,world.config)
        shot_recent = world.laser_shot_pos is not None and now-world.laser_shot_at < 1.65
        def score(item):
            pos, reward = item; travel = distance(p,pos); outside = max(0,distance(pos,z['next_center'])-max(0,z['next_radius']-18))
            climb = max(0,pos[2]-p[2]); travel_time = travel/max(1,me['stats'].get('walk_speed',11.7)) + climb/8
            value = reward - travel_time*2.1 - outside*(2 if urgent else .4) - world.threat(pos)*70 - climb*.12
            midpoint = [(pos[i]+p[i])/2 for i in range(3)]
            value -= world.threat(midpoint)*12
            if enemy:
                ed = distance(pos,enemy['actor']['pos']); old = distance(p,enemy['actor']['pos'])
                if mode=='flee': value += (ed-old)*.5
                if mode=='attack': value -= abs(ed-desired)*.13
                if 'lightning' in hostile_weapons and ('gun' in held or 'laser' in held) and ed < 60: value -= (60-ed)*.8
                if mode in ('flee','hold','recover') or (mode == 'attack' and (reloading or shot_recent)):
                    a=[pos[0],pos[1],pos[2]+7]; b=enemy['actor']['pos'][:2]+[enemy['actor']['pos'][2]+7]
                    if not arena.clear(a,b): value += 35 if reloading or shot_recent else 25
                elif mode == 'attack':
                    a=[pos[0],pos[1],pos[2]+7]; b=enemy['actor']['pos'][:2]+[enemy['actor']['pos'][2]+5]
                    if arena.clear(a,b): value += 8
                    if now < self.peek_until and self.reload_origin is not None:
                        value += min(20,distance(pos,self.reload_origin))*.35
                if shot_recent: value += min(15,distance(pos,world.laser_shot_pos))*.3
            if urgent: value -= distance(pos,(zx,zy))*.6
            return value
        self.goal = list(max(candidates,key=score)[0]); self.goal_until = now+(.25 if urgent else 1.5)
        if mode == 'loot':
            nearby = [(distance(self.goal,v['item']['pos']),ident) for ident,v in world.loot.items() if ident not in self.ignored]
            ident = min(nearby)[1] if nearby and min(nearby)[0] < 30 else None
            if ident != self.objective:
                self.objective, self.objective_since = ident, now
        return self.goal
