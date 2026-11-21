"""Replaceable tactical position scoring over ground and roof candidates."""
import math
from .geometry import distance


class Positioner:
    def __init__(self, arena):
        self.arena = arena
        self.goal = None
        self.goal_until = 0
        self.reloading = None

    def goal_for(self, world, mode, enemy, urgent):
        obs = world.obs; me = obs['self']; now = obs['t']; p = me['pos']; z = obs['zone']; arena = self.arena
        guns = [w for w in me['weapons'] if w and w['kind']=='gun']
        reloading = bool(guns and any(w.get('reload',0)>0 or w.get('ammo',1)==0 for w in guns))
        if self.reloading is not None and self.reloading != reloading:
            self.goal_until = 0
        self.reloading = reloading
        if now < self.goal_until and self.goal is not None: return self.goal
        candidates = [(p[:],0)]
        for radius in (25,55,100):
            for i in range(8):
                a = i*math.pi/4; x = p[0]+radius*math.cos(a); y = p[1]+radius*math.sin(a)
                if arena.walkable(x,y,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)):
                    candidates.append(([x,y,arena.height(x,y)],0))
        candidates.append(([z['next_center'][0],z['next_center'][1],arena.height(*z['next_center'])],0))
        if enemy and mode in ('attack', 'hold') and me['energy'] > 55 and hasattr(arena, 'roof_candidates'):
            for roof in arena.roof_candidates(p):
                if max(0, roof[2]-p[2]) < me['energy']*.5:
                    candidates.append((roof, 10 if distance(p,enemy['actor']['pos']) > 90 else 2))
        if mode == 'loot':
            for key, reward in (('cubes',42),('pickups',38),('crates',22),('drops',45)):
                items = obs.get(key,[]) if key == 'drops' else [v['item'] for v in world.loot.values() if v['kind'] == key]
                for item in items:
                    if key=='pickups' and any(w and w['kind']==item['kind'] for w in me['weapons']): continue
                    if key=='drops' and (item.get('lands_in',0)>15 or item.get('holder') not in (None,me['id'])): continue
                    bonus = 25 * (1-me['hp']/max(1,me['max_hp'])) if key=='drops' else 0
                    candidates.append((item['pos'],reward+bonus))
        def score(item):
            pos, reward = item; travel = distance(p,pos); outside = max(0,distance(pos,z['next_center'])-max(0,z['next_radius']-18))
            climb = max(0,pos[2]-p[2]); travel_time = travel/max(1,me['stats'].get('walk_speed',11.7)) + climb/8
            value = reward - travel_time*2.1 - outside*(2 if urgent else .4) - world.threat(pos)*70 - climb*.12
            midpoint = [(pos[i]+p[i])/2 for i in range(3)]
            value -= world.threat(midpoint)*12
            if enemy:
                ed = distance(pos,enemy['actor']['pos']); old = distance(p,enemy['actor']['pos'])
                if mode=='flee': value += (ed-old)*.5
                if mode=='attack': value -= abs(ed-100)*.13
                if mode in ('flee','hold') or (mode == 'attack' and reloading):
                    a=[pos[0],pos[1],pos[2]+7]; b=enemy['actor']['pos'][:2]+[enemy['actor']['pos'][2]+7]
                    if not arena.clear(a,b): value += 35 if reloading else 25
                elif mode == 'attack' and pos[2] > p[2]+3:
                    a=[pos[0],pos[1],pos[2]+7]; b=enemy['actor']['pos'][:2]+[enemy['actor']['pos'][2]+5]
                    if arena.clear(a,b): value += 8
            if urgent: value -= distance(pos,z['next_center'])*.6
            return value
        self.goal = list(max(candidates,key=score)[0]); self.goal_until = now+(.25 if urgent else 1.5)
        return self.goal

