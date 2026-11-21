"""Contextual value for weapon pickups; the server still handles equip time."""
from .geometry import distance


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
    if any(w is None for w in weapons): return True,None
    worst=min(range(len(weapons)),key=lambda i:weapon_value(weapons[i]['kind'],world))
    old=weapons[worst]
    if old['kind']=='laser' and old.get('charge',0)>0: return False,None
    return weapon_value(item['kind'],world)>weapon_value(old['kind'],world),worst
