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


def pressure_pickup(kind, weapons):
    """Choose an empty slot or a meaningful upgrade without discarding a gun."""
    if any(w and w['kind'] == kind for w in weapons): return False, None
    values = {'gun': 2.0, 'lightning': 2.1, 'laser': 2.4, 'mortar': 2.6}
    if kind not in values: return False, None
    if any(w is None for w in weapons): return True, None
    candidates = [(values.get(w['kind'], 0), i) for i, w in enumerate(weapons)
                  if w['kind'] != 'gun' and not (w['kind'] == 'laser' and w.get('charge', 0) > 0)]
    if not candidates: return False, None
    value, slot = min(candidates)
    return (True, slot) if values[kind] > value + .3 else (False, None)


def choose_loadout(obs, config, pressure=False, state=None):
    out={}
    me=obs['self']; p=me['pos']
    pickup_value = {'gun': 2., 'lightning': 2.1, 'laser': 2.4, 'mortar': 2.6}
    best_pickup_value = -1.
    pickups = obs.get('pickups',[])
    if pressure and state is not None and hasattr(state, 'items'):
        pickups = [item for kind,item,seen in state.items.values() if kind == 'pickups' and obs['t']-seen <= .5]
    for pickup in pickups:
        if pressure and state is not None and obs['t'] < getattr(state, 'pressure_take_until', -1): break
        if math.dist(p[:2],pickup['pos'][:2])>config['loot']['pickup_radius']-.3 or abs(p[2]-pickup['pos'][2])>(3.7 if pressure else 3.6): continue
        held={w['kind'] for w in me['weapons'] if w}; kind=pickup['kind']
        if pressure:
            wanted, replacement = pressure_pickup(kind, me['weapons'])
            if not wanted: continue
            if pickup_value.get(kind, 0) <= best_pickup_value: continue
            best_pickup_value = pickup_value[kind]
            out['take'] = pickup['id']
            if replacement is not None: out['drop'] = replacement
            else: out.pop('drop', None)
            continue
        if kind in held or kind in ('mortar','gun'): continue
        current=me['weapons'][1] if len(me['weapons'])>1 else None
        ranking={'laser':4,'lightning':3,'mortar':1}
        if current and ranking.get(kind,0)<=ranking.get(current['kind'],0): continue
        if current and current['kind']=='laser' and current.get('charge',0)>0: continue
        out['take']=pickup['id']
        if current is not None: out['drop']=1
        break
    if pressure and state is not None and 'take' in out:
        state.pressure_take_until = obs['t'] + .25
    if obs.get('offer'):
        if pressure:
            values = {'sensors': .98, 'gyros': .95, 'jets': .92, 'mortar_splash': .90,
                      'mortar_reload': .88, 'mortar_velocity': .85, 'capacitor': .82,
                      'reactor': .80, 'laser_pierce': .78, 'lightning_chain': .75,
                      'servos': .68, 'nanites': .62, 'gun_mag': .55, 'gun_velocity': .52,
                      'laser_charge': .48, 'gun_rate': .45, 'gun_damage': .42,
                      'laser_damage': .40, 'lightning_range': .38, 'lightning_efficiency': .35,
                      'armor': .30, 'plating': .28}
            lightning = any(w and w['kind'] == 'lightning' for w in me['weapons'])
            def upgrade_value(choice):
                kind = choice['id']
                return values.get(kind, .25) + (.3 if lightning and kind in ('reactor', 'capacitor') else 0)
            out['pick'] = max(range(len(obs['offer']['choices'])), key=lambda i: upgrade_value(obs['offer']['choices'][i]))
            return out
        order=['plating','armor','laser_damage','laser_charge','nanites','gun_damage','gun_rate','lightning_efficiency','lightning_range','servos','gun_mag','gun_velocity','gyros','lightning_chain','reactor','capacitor','mortar_reload','mortar_splash','mortar_velocity','sensors','jets','laser_pierce']
        if {w['kind'] for w in me['weapons'] if w} == {'gun'}:
            order.remove('gun_mag')
            order.insert(order.index('gun_damage'), 'gun_mag')
        out['pick']=min(range(len(obs['offer']['choices'])),key=lambda i:order.index(obs['offer']['choices'][i]['id']) if obs['offer']['choices'][i]['id'] in order else len(order))
    return out

def pressure_objective(state, obs, hp, danger):
    """Score useful nearby items by value per estimated collection time."""
    me, t, zone = obs['self'], obs['t'], obs['zone']
    pos = me['pos']; speed = max(1., me['stats']['walk_speed'])
    brawl = obs['alive'] > 2 and (state.ffa or t < 6 or t-getattr(state, 'credit_absorbed_at', -100) < 25)
    radius = 150 if obs['alive'] <= 2 else 220 if brawl else 250
    want_cubes = 40 if obs['alive'] <= 2 else 10 if brawl else 26
    candidates = list(state.items.items())
    if me['cubes'] < want_cubes and not danger:
        candidates.extend((ident, ('npc', tr['actor'], tr['seen'])) for ident, tr in state.tracks.items()
                          if tr['actor']['kind'] == 'npc' and t-tr['seen'] < 20)
    if state.supply_drops:
        candidates.extend((drop['id'], ('drops', drop, t)) for drop in obs.get('drops', []))
    best = None; best_score = 0.
    values = {'gun': 2., 'lightning': 2.1, 'laser': 2.4, 'mortar': 2.6}
    grid = state.world.baked
    current = state.world.nearest_free(state.world.cell(*pos[:2])) if grid else None
    component = grid['component'][current[1]*grid['nx']+current[0]] if current is not None else (grid['main'] if grid else None)
    for ident, (kind, item, seen) in candidates:
        d = math.dist(pos[:2], item['pos'][:2])
        if d > (300 if kind == 'drops' else radius) or state.bad.get(ident, 0) > t: continue
        handling = 0.
        if kind == 'pickups':
            wanted, slot = pressure_pickup(item['kind'], me['weapons'])
            if not wanted: continue
            value = values[item['kind']]*4
            if slot is not None: value -= values.get(me['weapons'][slot]['kind'], 0)*4
            handling = .5
        elif kind == 'cubes' and me['cubes'] < want_cubes: value = 11.
        elif kind == 'crates' and me['cubes'] < want_cubes: value, handling = 7., 2.5
        elif kind == 'npc' and me['cubes'] < want_cubes and not danger: value, handling = 11., 5.
        elif kind == 'drops':
            if item['lands_in'] > d/speed*1.3+6 and ident != state.loot_id: continue
            if brawl and me['cubes'] >= want_cubes and hp > .7: continue
            value = 30. * (1.5 if hp < .6 else 1.)
            handling = 4 + item['lands_in']*.3
        else: continue
        if item['pos'][2]-state.world.ground(*item['pos'][:2]) > 3.2: continue
        free = state.world.nearest_free(state.world.cell(*item['pos'][:2]))
        if free is None or (grid and grid['component'][free[1]*grid['nx']+free[0]] != component): continue
        travel = d*1.25/speed + handling
        # Estimate the circle at arrival plus the reference's slack. The
        # current observed circle is the starting point for interpolation.
        x,y=item['pos'][:2]
        if math.hypot(x-zone['center'][0],y-zone['center'][1]) > zone['radius']-6: continue
        future=t+travel+12
        if future>zone['shrink_start']:
            duration=zone['shrink_end']-zone['shrink_start']
            fraction=max(0.,min(1.,(future-zone['shrink_start'])/duration)) if duration>0 else 1.
            cx=zone['center'][0]+(zone['next_center'][0]-zone['center'][0])*fraction
            cy=zone['center'][1]+(zone['next_center'][1]-zone['center'][1])*fraction
            r=zone['radius']+(zone['next_radius']-zone['radius'])*fraction
            if math.hypot(x-cx,y-cy)>r-6: continue
        if kind != 'cubes' and any(tr['actor']['kind'] == 'mech' and t-tr['seen'] < 6
                                   and math.dist(tr['actor']['pos'][:2], item['pos'][:2]) < 45
                                   for tr in state.tracks.values()): value *= .35
        score = value/(travel+1.5) * (1.25 if ident == state.loot_id else 1.)
        if brawl and score>best_score:
            for tr in state.tracks.values():
                actor=tr['actor']
                if actor['kind']!='mech' or t-tr['seen']>4: continue
                if math.dist(actor['pos'][:2],item['pos'][:2])>=230: continue
                scale=1+actor.get('cubes',0)*state.cfg['cubes'].get('size_per_cube',.05)
                eye=(*actor['pos'][:2],actor['pos'][2]+8*scale)
                target=(x,y,item['pos'][2]+4.5)
                if state.world.shot_clear(eye,target):
                    score*=.5
                    break
        if score > best_score:
            best, best_score = (ident, kind, item, d, seen), score
    return best


def choose_objective(state, obs, hp, danger, squad):
    """Rank reachable pickups and farming targets."""
    if getattr(state, 'decision_policy', '') == 'pressure':
        return pressure_objective(state, obs, hp, danger)
    me=obs['self']; p=me['pos']; t=obs['t']; z=obs['zone']
    best=None; score=0.; held={w['kind'] for w in me['weapons'] if w}
    candidates=list(state.items.items())
    if hp>(.5 if squad else .7) and not danger and (squad or t<150) and me['cubes']<state.cfg['cubes']['stat_cap']:
        candidates += [(ident,('npc',tr['actor'],tr['seen'])) for ident,tr in state.tracks.items() if tr['actor']['kind']=='npc' and t-tr['seen']<12]
    if squad and state.supply_drops and not danger:
        candidates.extend((drop['id'], ('drops', drop, t)) for drop in obs.get('drops', []))
    for ident,(kind,item,when) in candidates:
        d=math.dist(p[:2],item['pos'][:2])
        if d>260 or ident in state.bad and state.bad[ident]>t: continue
        if kind == 'drops':
            travel = max(0., d - item['radius'] * .65) * 1.4 / me['stats']['walk_speed']
            wait = max(0., item['lands_in'] - travel)
            if item['holder'] not in (None, state.slot) or wait > 8:
                continue
            finish = t + travel + wait + item['capture_s'] - item['progress']
            if finish >= zone_deadline(state.hold, z, *item['pos'][:2], 6):
                continue
            value = 240 + 240 * (1 - hp)
        elif kind=='pickups':
            if getattr(state, 'decision_policy', '') == 'pressure':
                wanted, replacement = pressure_pickup(item['kind'], me['weapons'])
                if not wanted or d >= 150: continue
                values = {'gun': 2.0, 'lightning': 2.1, 'laser': 2.4, 'mortar': 2.6}
                value = values[item['kind']] * 40
                if replacement is not None:
                    value -= values.get(me['weapons'][replacement]['kind'], 0) * 40
            else:
                if item['kind'] in held or item['kind'] in ('gun','mortar'): continue
                current=me['weapons'][1] if len(me['weapons'])>1 else None
                ranking={'laser':4,'lightning':3,'mortar':1}
                if current and ranking.get(item['kind'],0)<=ranking.get(current['kind'],0): continue
                limit=240 if squad and item['kind']=='laser' else 150 if squad else 90
                rush_laser = state.laser_rush and item['kind'] == 'laser' and not state.ffa and not danger and not state.retreat
                if rush_laser: limit = 250
                if d>=limit: continue
                value=150 if item['kind']=='laser' and squad else 130 if None in me['weapons'] else 60
                if rush_laser: value = 340
        elif kind=='cubes' and d<max(60,(150 if squad else 90)*.7): value=75 if me['cubes']<state.cfg['cubes']['stat_cap'] else 25
        elif kind=='crates' and d<(150 if squad else 90) and hp>(.5 if squad else .7) and not danger and (squad or t<150): value=45 if me['cubes']<state.cfg['cubes']['stat_cap'] else 15
        elif kind=='npc' and d<(150 if squad else 90):
            value=85
            # Optional, separate practice trial: exploit the relatively quiet
            # opening without committing to a distant or blocked drone.
            if (os.getenv('BOT_EARLY_DRONE') == '1' and squad and t < 60
                    and hp > .75 and obs['alive'] >= 14 and d <= 70
                    and t-when < 1 and not danger
                    and not any(tr['actor']['kind'] == 'mech' and t-tr['seen'] < 3
                                and math.dist(p[:2],tr['actor']['pos'][:2]) < 120
                                for tr in state.tracks.values())
                    and getattr(state.world,'line_walkable',lambda *_:False)(p,item['pos'])):
                value=170
        else: continue
        if item['pos'][2]-state.world.ground(*item['pos'][:2])>3.2: continue
        free=state.world.nearest_free(state.world.cell(*item['pos'][:2]))
        if free is None: continue
        if state.world.baked:
            grid = state.world.baked
            component = grid['main']
            if getattr(state, 'decision_policy', '') == 'pressure':
                current = state.world.nearest_free(state.world.cell(*p[:2]))
                if current is not None:
                    component = grid['component'][current[1]*grid['nx']+current[0]]
            if grid['component'][free[1]*grid['nx']+free[0]] != component: continue
        if math.dist(item['pos'][:2],z['center'])>z['radius']-6: continue
        if t+d*1.4/me['stats']['walk_speed']+5>zone_deadline(state.hold,z,*item['pos'][:2],6): continue
        cost=d+18
        if squad and getattr(state,'farming_policy','legacy') in ('selective','route'):
            if d<100 and not state.world.line_walkable(p,item['pos']): cost+=45
            if kind=='npc':
                cost+=min(30,max(0,t-when)*4)
                value*=1+.3*max(0,min(1,1-item.get('hp',350)/350))
            if kind in ('cubes','npc','crates'):
                thresholds=state.cfg['cubes'].get('upgrade_thresholds',[1,3,6,10])
                remaining=min((n-me['cubes'] for n in thresholds if n>me['cubes']),default=99)
                if remaining <= (2 if kind=='npc' else 1): value*=1.25
        util=value/cost*(1.35 if ident==state.loot_id else 1)
        if util>score: best=(ident,kind,item,d,when); score=util
    return best
