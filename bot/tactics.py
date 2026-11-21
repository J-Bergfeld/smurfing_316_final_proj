"""Short-horizon defensive moves, independent of strategic mode."""
import math
from .geometry import angle_diff, distance


def dodge(world):
    obs=world.obs; me=obs['self']; p=me['pos']; arena=world.arena
    if not me.get('grounded',True): return None
    incoming=[]
    for shot in obs.get('projectiles',[]):
        vx,vy=shot['vel'][:2]; speed=math.hypot(vx,vy)
        if speed < 1: continue
        rx,ry=p[0]-shot['pos'][0],p[1]-shot['pos'][1]
        t=(rx*vx+ry*vy)/(speed*speed)
        if 0 <= t <= .8:
            miss=math.hypot(rx-vx*t,ry-vy*t)
            gravity=world.config.get('weapons',{}).get('mortar',{}).get('gravity',22) if shot['kind']=='mortar' else 0
            z=shot['pos'][2]+shot['vel'][2]*t-.5*gravity*t*t
            if miss < (12 if shot['kind']=='mortar' else 8) and abs(z-(p[2]+me.get('stats',{}).get('height',9)/2)) < 10:
                incoming.append((t,vx/speed,vy/speed))
    for track in world.enemies():
        actor=track['actor']
        if not track['visible'] or not actor.get('charging'): continue
        dx,dy=p[0]-actor['pos'][0],p[1]-actor['pos'][1]
        if math.hypot(dx,dy)<280 and abs(angle_diff(math.atan2(dy,dx),actor['aim'][0])) < .12:
            incoming.append((.6,math.cos(actor['aim'][0]),math.sin(actor['aim'][0])))
    if not incoming: return None
    _,vx,vy=min(incoming); options=[]; current=world.threat(p); zone=obs['zone']
    for sign in (-1,1):
        ux,uy=-vy*sign,vx*sign; x,y=p[0]+ux*6,p[1]+uy*6
        if distance((x,y),zone['center']) > max(zone['radius']-3,distance(p,zone['center'])): continue
        if hasattr(arena,'supported'):
            safe=arena.supported(x,y,p[2],me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9))
        else: safe=arena.walkable(x,y)
        if not safe: continue
        q=[x,y,p[2]]; risk=world.threat(q)
        options.append((risk,ux,uy))
    if not options: return None
    risk,ux,uy=min(options)
    if risk > current+1: return None
    return [ux,uy]


def blend_dodge(world, desired, evasive, urgent=False):
    """Choose a safe short step that balances escape with the active route."""
    if evasive is None: return desired
    me=world.obs['self']; p=me['pos']; arena=world.arena; zone=world.obs['zone']
    options=[]
    for weight in (.5, .75, 1.):
        x=desired[0]*(1-weight)+evasive[0]*weight
        y=desired[1]*(1-weight)+evasive[1]*weight
        mag=math.hypot(x,y)
        if mag < .01: continue
        x,y=x/mag,y/mag
        q=[p[0]+x*5,p[1]+y*5,p[2]]
        safe = arena.supported(q[0],q[1],q[2],me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9)) if hasattr(arena,'supported') else arena.walkable(q[0],q[1])
        if not safe: continue
        if distance(q,zone['center']) > max(zone['radius']-2,distance(p,zone['center'])): continue
        progress=x*desired[0]+y*desired[1]
        score=world.projectile_risk(q)*3+world.threat(q)*.2-progress*(.6 if urgent else .2)
        options.append((score,[x,y]))
    return min(options,key=lambda item:item[0])[1] if options else desired
