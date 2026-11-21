"""Local wall steering and staged recovery for the navigation controller."""
import math
from .geometry import distance


class MovementSupport:
    def __init__(self):
        self.history=[]
        self.last_move=[0,0]
        self.recovery=None
        self.stalls=0

    def record(self, move):
        self.last_move=list(move)

    def observe(self, me, goal, now):
        p=me['pos']
        self.history.append((now,p[0],p[1],math.hypot(*self.last_move)))
        self.history=[h for h in self.history if now-h[0] <= 1.4]
        if self.recovery or not me['grounded'] or distance(p,goal)<4 or len(self.history)<5:
            return False
        old=self.history[0]; elapsed=now-old[0]
        commanded=sum(h[3]>.5 for h in self.history)
        expected=elapsed*me.get('stats',{}).get('walk_speed',11.7)*.6
        if elapsed>=1 and commanded>=5 and math.hypot(p[0]-old[1],p[1]-old[2])<expected*.2:
            direction=self.last_move; mag=math.hypot(*direction)
            if mag<.1: return False
            dx,dy=direction[0]/mag,direction[1]/mag
            self.stalls+=1; side=1 if self.stalls%2 else -1
            self.recovery={'phase':'back','until':now+.6,'dir':[-.6*dx-.8*side*dy,-.6*dy+.8*side*dx],
                           'forward':[dx,dy],'z':p[2]}
            self.history=[]
            return True
        return False

    def recover(self, me, now):
        rec=self.recovery
        if not rec: return None
        if now>=rec['until']:
            if rec['phase']=='back' and me['energy']>35:
                rec.update(phase='jet',until=now+1.4,z=me['pos'][2],jumped=False)
            else:
                self.recovery=None
                return None
        if rec['phase']=='back': return {'move':rec['dir'][:], 'jump':False,'boost':False}
        jump=me['grounded'] and not rec['jumped']
        if jump: rec['jumped']=True
        if rec['jumped'] and me['grounded'] and not jump:
            self.recovery=None
            return None
        return {'move':rec['forward'][:], 'jump':jump,
                'boost':bool(not me['grounded'] and me['energy']>8 and me['pos'][2]<rec['z']+7)}

    def steer(self, arena, me, move, zone):
        mag=math.hypot(*move)
        if mag<.01 or not me['grounded']: return move
        p=me['pos']; stats=me.get('stats',{}); radius=stats.get('radius',2.5); height=stats.get('height',9)
        def safe(x,y):
            if distance((x,y),zone['center'])>max(zone['radius']-2,distance(p,zone['center'])): return False
            return arena.supported(x,y,p[2],radius,height) if hasattr(arena,'supported') else arena.walkable(x,y,radius,height)
        # If the current footing is off our coarse model, leave the direction
        # intact so that recovery/jet movement can get back onto the graph.
        if not safe(p[0],p[1]): return move
        heading=math.atan2(move[1],move[0])
        for degrees in (0,20,-20,40,-40,60,-60,80,-80,100,-100):
            a=heading+math.radians(degrees); dx,dy=math.cos(a),math.sin(a)
            if all(safe(p[0]+dx*d,p[1]+dy*d) for d in (2.5,5)):
                return [dx*mag,dy*mag]
        return [0,0]
