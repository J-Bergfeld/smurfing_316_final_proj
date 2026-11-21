"""Replaceable tactical position scoring over ground and roof candidates."""
import math
from .geometry import distance
from .loadout import pickup_slot


class Positioner:
    def __init__(self, arena):
        self.arena = arena
        self.goal = None
        self.goal_until = 0
        self.reloading = None
        self.last_laser_shot = -1000
        self.reload_origin = None
        self.peek_until = 0

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
            for key, reward in (('cubes',42),('pickups',38),('crates',22),('drops',45)):
                items = obs.get(key,[]) if key == 'drops' else [v['item'] for v in world.loot.values() if v['kind'] == key]
                for item in items:
                    if key=='pickups' and not pickup_slot(item,world)[0]: continue
                    if key=='drops':
                        if item.get('lands_in',0)>15 or item.get('holder') not in (None,me['id']): continue
                        if any(t['confidence']>.3 and distance(t['actor']['pos'],item['pos'])<120 for t in world.enemies()): continue
                        arrival=distance(p,item['pos'])/max(1,me['stats'].get('walk_speed',11.7))
                        if now + arrival + item.get('capture_s',4) > z['shrink_end'] and distance(item['pos'],z['next_center']) > z['next_radius']-10: continue
                    bonus = 25 * (1-me['hp']/max(1,me['max_hp'])) if key=='drops' else 0
                    candidates.append((item['pos'],reward+bonus))
        held={w['kind'] for w in me['weapons'] if w}
        hostile_weapons=enemy['actor'].get('weapons',[]) if enemy else []
        desired = 35 if 'lightning' in held and 'laser' not in held else 120
        if 'lightning' in hostile_weapons and ('gun' in held or 'laser' in held): desired=max(desired,75)
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
        return self.goal

