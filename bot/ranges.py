"""Range estimates for positioning; opponents' upgrades are not observable."""
from .geometry import distance


def weapon_range(weapon, config):
    kind = weapon['kind']
    stats = dict(config.get('weapons', {}).get(kind, {}))
    stats.update(weapon.get('stats', {}))
    if kind == 'mortar':
        # Approximate same-height ballistic reach, not a guaranteed shot.
        return stats.get('speed', 72)**2 / max(1, stats.get('gravity', 22))
    return stats.get('range', {'gun':230, 'laser':280, 'lightning':45}.get(kind, 0))


def desired_distance(me, enemy, config):
    """Pick a practical engagement distance, bounded by what we can see."""
    weapons = [w for w in me.get('weapons', []) if w]
    kinds = {w['kind'] for w in weapons}
    usable = [w for w in weapons if w['kind'] != 'gun' or w.get('ammo', 1)>0]
    if not usable: usable = weapons
    far = [w for w in usable if w['kind'] in ('gun','laser','mortar')]
    if 'laser' in {w['kind'] for w in far}:
        laser = next(w for w in far if w['kind']=='laser')
        desired = min(175, weapon_range(laser, config)*.7)
    elif far:
        desired = min(135, max(weapon_range(w,config) for w in far)*.65)
    elif 'lightning' in kinds:
        lightning = next(w for w in weapons if w['kind']=='lightning')
        desired = weapon_range(lightning,config)*.75
    else:
        desired = 120
    # Enemy observations expose kinds but not individual upgraded stats.
    enemy_kinds = enemy.get('weapons', []) if enemy else []
    if 'lightning' in enemy_kinds and far:
        enemy_range = weapon_range({'kind':'lightning'},config)
        desired = max(desired, enemy_range+25)
    vision = config.get('vision',{}).get('range',200)+me.get('stats',{}).get('vision_bonus',0)
    return max(0, min(desired, vision-15))


def engagement_range(me, config):
    """React to visible threats within usable weapon range and vision."""
    weapons = [w for w in me.get('weapons',[]) if w and (w['kind'] != 'gun' or w.get('ammo',1)>0)]
    if not weapons: return 160
    reach = max(weapon_range(w,config) for w in weapons)
    vision = config.get('vision',{}).get('range',200)+me.get('stats',{}).get('vision_bonus',0)
    return max(160, min(vision, reach*.9))


def incoming_dps(enemy, distance_m, config):
    """Rough sustained damage by weapons that can reach the current distance."""
    values = {'gun': .35, 'laser': .42, 'lightning': .42, 'mortar': .58}
    total = 0.0
    for kind in enemy.get('weapons', ['gun']):
        if kind not in values: continue
        stats = config.get('weapons', {}).get(kind, {})
        # Opponent upgrades are hidden; keep a small conservative margin.
        if distance_m > weapon_range({'kind':kind},config)*1.05: continue
        if kind == 'mortar' and distance_m < 20: continue
        damage = stats.get('damage', {'gun':45,'laser':315,'lightning':60,'mortar':200}[kind])
        cycle = stats.get('cooldown', {'gun':.24,'laser':1.65,'lightning':.25,'mortar':2.6}[kind])
        if kind == 'laser': cycle += stats.get('charge',.75)
        total += damage/max(.1,cycle)*values[kind]
    return total


def unsafe_to_close(me, enemy, config, clear):
    """Avoid a long exposed approach while unable to answer the enemy."""
    if not clear: return False
    d = distance(me['pos'],enemy['pos'])
    weapons = [w for w in me.get('weapons',[]) if w and
               (w['kind'] != 'gun' or (w.get('ammo',1)>0 and w.get('reload',0)<=0))]
    reach = max((weapon_range(w,config) for w in weapons), default=0)
    close_time = max(0,d-reach*.9)/max(1,me.get('stats',{}).get('walk_speed',11.7))
    # A low-ammo/reloading gun can recover without walking into the opponent.
    if not weapons: return incoming_dps(enemy,d,config)>0
    expected = incoming_dps(enemy,d,config)*close_time
    return close_time > 1.0 and expected > .25*max(1,me['hp'])
