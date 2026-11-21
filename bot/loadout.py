"""Contextual value for weapon pickups; the server still handles equip time."""
import os
import math
from .geometry import distance, zone_deadline


def weapon_value(kind, world):
    me=world.obs['self']; zone=world.obs['zone']
    nearby=[t['actor'] for t in world.enemies() if t['confidence']>.3 and distance(me['pos'],t['actor']['pos'])<100]
    if kind == 'gun': return 3.0
    if kind == 'laser': return 4.0 if not any('lightning' in e.get('weapons',[]) and distance(me['pos'],e['pos'])<55 for e in nearby) else 2.5
    if kind == 'lightning': return 4.5 if zone['radius']<80 or any('laser' in e.get('weapons',[]) for e in nearby) else 2.5
    if kind == 'mortar': return 3.5 if any('lightning' in e.get('weapons',[]) for e in nearby) else 1.5
    return 0


def pickup_slot(item, world):
    weapons=world.obs['self']['weapons']
    if any(w and w['kind']==item['kind'] for w in weapons): return False,None
    if os.getenv('BOT_LOADOUT','legacy') == 'preserve_gun':
        kind=item['kind']
        if kind=='gun': return (bool(weapons and weapons[0] is None),None)
        if kind not in ('laser','lightning') or len(weapons)<2: return False,None
        current=weapons[1]
        if current is None: return True,None
        if current['kind']=='laser' and current.get('charge',0)>0: return False,None
        ranking={'laser':4,'lightning':3,'mortar':1,'gun':0}
        return (True,1) if ranking[kind]>ranking.get(current['kind'],0) else (False,None)
    if any(w is None for w in weapons): return True,None
    worst=min(range(len(weapons)),key=lambda i:weapon_value(weapons[i]['kind'],world))
    old=weapons[worst]
    if old['kind']=='laser' and old.get('charge',0)>0: return False,None
    return weapon_value(item['kind'],world)>weapon_value(old['kind'],world),worst


def choose_loadout(obs, config):
    out={}
    me=obs['self']; p=me['pos']
    for pickup in obs.get('pickups',[]):
        if math.dist(p[:2],pickup['pos'][:2])>config['loot']['pickup_radius']-.3 or abs(p[2]-pickup['pos'][2])>3.6: continue
        held={w['kind'] for w in me['weapons'] if w}; kind=pickup['kind']
        if kind in held or kind in ('mortar','gun'): continue
        current=me['weapons'][1] if len(me['weapons'])>1 else None
        ranking={'laser':4,'lightning':3,'mortar':1}
        if current and ranking.get(kind,0)<=ranking.get(current['kind'],0): continue
        if current and current['kind']=='laser' and current.get('charge',0)>0: continue
        out['take']=pickup['id']
        if current is not None: out['drop']=1
        break
    if obs.get('offer'):
        order=['plating','armor','laser_damage','laser_charge','nanites','gun_damage','gun_rate','lightning_efficiency','lightning_range','servos','gun_mag','gun_velocity','gyros','lightning_chain','reactor','capacitor','mortar_reload','mortar_splash','mortar_velocity','sensors','jets','laser_pierce']
        out['pick']=min(range(len(obs['offer']['choices'])),key=lambda i:order.index(obs['offer']['choices'][i]['id']) if obs['offer']['choices'][i]['id'] in order else len(order))
    return out

def choose_objective(state, obs, hp, danger, squad):
    """Rank reachable pickups and farming targets."""
    me=obs['self']; p=me['pos']; t=obs['t']; z=obs['zone']
    best=None; score=0.; held={w['kind'] for w in me['weapons'] if w}
    candidates=list(state.items.items())
    if hp>(.5 if squad else .7) and not danger and (squad or t<150) and me['cubes']<state.cfg['cubes']['stat_cap']:
        candidates += [(ident,('npc',tr['actor'],tr['seen'])) for ident,tr in state.tracks.items() if tr['actor']['kind']=='npc' and t-tr['seen']<12]
    for ident,(kind,item,when) in candidates:
        d=math.dist(p[:2],item['pos'][:2])
        if d>260 or ident in state.bad and state.bad[ident]>t: continue
        if kind=='pickups':
            if item['kind'] in held or item['kind'] in ('gun','mortar'): continue
            current=me['weapons'][1] if len(me['weapons'])>1 else None
            ranking={'laser':4,'lightning':3,'mortar':1}
            if current and ranking.get(item['kind'],0)<=ranking.get(current['kind'],0): continue
            limit=240 if squad and item['kind']=='laser' else 150 if squad else 90
            if d>=limit: continue
            value=150 if item['kind']=='laser' and squad else 130 if None in me['weapons'] else 60
        elif kind=='cubes' and d<max(60,(150 if squad else 90)*.7): value=75 if me['cubes']<state.cfg['cubes']['stat_cap'] else 25
        elif kind=='crates' and d<(150 if squad else 90) and hp>(.5 if squad else .7) and not danger and (squad or t<150): value=45 if me['cubes']<state.cfg['cubes']['stat_cap'] else 15
        elif kind=='npc' and d<(150 if squad else 90): value=85
        else: continue
        if item['pos'][2]-state.world.ground(*item['pos'][:2])>3.2: continue
        free=state.world.nearest_free(state.world.cell(*item['pos'][:2]))
        if free is None or (state.world.baked and state.world.baked['component'][free[1]*state.world.baked['nx']+free[0]]!=state.world.baked['main']): continue
        if math.dist(item['pos'][:2],z['center'])>z['radius']-6: continue
        if t+d*1.4/me['stats']['walk_speed']+5>zone_deadline(state.hold,z,*item['pos'][:2],6): continue
        util=value/(d+18)*(1.35 if ident==state.loot_id else 1)
        if util>score: best=(ident,kind,item,d,when); score=util
    return best
