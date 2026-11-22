"""Per-match memory with uncertain enemy and anonymous sound tracks."""
import math
from .geometry import distance, angle_diff


class World:
    def __init__(self, config, arena):
        self.config, self.arena = config, arena
        self.tracks = {}
        self.sounds = []
        self.loot = {}
        self.last_damage = -1000
        self.last_dealt = -1000
        self.last_damage_bearing = None
        self.last_damage_by = None
        self.laser_shot_at = -1000
        self.laser_shot_pos = None
        self.laser_charge = {}
        self.obs = None
        self.field = 'opening'
        self.initial_alive = None
        self.own_kills = set()
        self.unexplained = 0
        self.last_field_tick = -1
        self.attackers = {}
        self.damage_log = []

    def update(self, obs):
        self.obs = obs; now = obs['t']; me = obs['self']
        if self.initial_alive is None:
            self.initial_alive = obs['alive']
        fresh = obs['tick'] > self.last_field_tick
        if fresh:
            for event in obs.get('events', []):
                if event['type'] == 'kill' and event.get('target') is not None:
                    self.own_kills.add(event['target'])
                if event['type'] == 'damaged':
                    if event.get('by') is not None:
                        self.attackers[event['by']] = now
                    self.damage_log.append((now, event.get('amount', 0)))
            if self.field != 'ffa':
                missing = self.initial_alive - obs['alive'] > len(self.own_kills)
                self.unexplained = self.unexplained + 1 if missing else 0
                if self.unexplained >= 5: self.field = 'ffa'
                elif now >= 20: self.field = 'squad'
            self.last_field_tick = obs['tick']
        self.damage_log = [(t, amount) for t, amount in self.damage_log if now-t < 2.5]
        self.attackers = {ident:t for ident,t in self.attackers.items() if now-t < 8}
        for slot, weapon in enumerate(me.get('weapons', [])):
            if not weapon or weapon.get('kind') != 'laser':
                self.laser_charge.pop(slot, None)
                continue
            charge = weapon.get('charge', 0)
            if self.laser_charge.get(slot, 0) > 0 and charge == 0 and weapon.get('cooldown', 0) > 0:
                self.laser_shot_at, self.laser_shot_pos = now, me['pos'][:]
            self.laser_charge[slot] = charge
        for actor in obs.get('mechs', []):
            eye = me['pos'][:2] + [me['pos'][2] + me.get('stats', {}).get('eye_height', 8)]
            center = actor['pos'][:2] + [actor['pos'][2] + (4.5 if actor['kind']=='mech' else 1.75)]
            d = distance(me['pos'], actor['pos'])
            vision = self.config.get('vision', {})
            near = vision.get('near_range',45)+me.get('stats',{}).get('near_range_bonus',0)
            far = vision.get('range',200)+me.get('stats',{}).get('vision_bonus',0)
            in_view = d <= near or (d <= far and abs(angle_diff(math.atan2(actor['pos'][1]-eye[1], actor['pos'][0]-eye[0]), me['aim'][0])) <= math.radians(vision.get('fov_deg',120)/2))
            visible = in_view and self.arena.clear(eye, center)
            self.tracks[actor['id']] = {'actor': actor, 'updated': now, 'visible': visible, 'confidence': 1.0 if visible else .65}
        for key, track in list(self.tracks.items()):
            if track['updated'] != now:
                track['visible'] = False
                track['confidence'] = max(0, .65 * (1-(now-track['updated'])/8))
                if track['confidence'] <= 0: del self.tracks[key]
        for sound in obs.get('sounds', []):
            if sound['kind'] in ('death','drop','crate'): continue
            near = self.config.get('sound',{}).get('near',60); mid = self.config.get('sound',{}).get('mid',160)
            dist = {'near':near*.6,'mid':(near+mid)/2,'far':mid+70}.get(sound['dist'],mid)
            self.sounds.append({'pos':[me['pos'][0]+dist*math.cos(sound['bearing']), me['pos'][1]+dist*math.sin(sound['bearing'])], 'time':now-sound.get('age',0), 'kind':sound['kind']})
        self.sounds = [s for s in self.sounds if now-s['time'] < 4][-20:]
        for e in obs.get('events', []):
            if e['type'] == 'damaged':
                self.last_damage = now
                self.last_damage_by = e.get('by')
                if e.get('bearing') is not None:
                    self.last_damage_bearing = e['bearing']
                    self.sounds.append({'pos':[me['pos'][0]+50*math.cos(e['bearing']),me['pos'][1]+50*math.sin(e['bearing'])], 'time':now, 'kind':'damage'})
            if e['type'] == 'hit': self.last_dealt = now
            if e['type'] == 'took' or (e['type'] == 'take_failed' and e.get('reason') == 'gone'):
                self.loot.pop(e.get('id'), None)
        seen = set()
        for kind in ('cubes', 'pickups', 'crates'):
            for item in obs.get(kind, []):
                seen.add(item['id'])
                self.loot[item['id']] = {'kind':kind, 'item':dict(item), 'seen':now}
        for ident, remembered in list(self.loot.items()):
            if ident in seen: continue
            pos = remembered['item']['pos']; age = now-remembered['seen']
            # Only discard on absence at close range, where we could reasonably
            # verify it; a turn or a wall can otherwise hide a real pickup.
            close = distance(me['pos'],pos) < 8 and abs(me['pos'][2]-pos[2]) < 4
            if age > 90 or (close and self.arena.clear([me['pos'][0],me['pos'][1],me['pos'][2]+8], [pos[0],pos[1],pos[2]+1])):
                del self.loot[ident]

    def enemies(self):
        return [v for v in self.tracks.values() if v['actor']['kind'] == 'mech']

    def projectile_risk(self, pos, horizon=1.0):
        """Approximate closest approach of visible projectiles to a mech center."""
        risk = 0.0
        center = [pos[0], pos[1], pos[2] + self.obs['self'].get('stats', {}).get('height', 9)/2]
        for projectile in self.obs.get('projectiles', []):
            rel = [projectile['pos'][i]-center[i] for i in range(3)]
            vel = projectile['vel']; speed2 = sum(v*v for v in vel)
            if speed2 < 1: continue
            t = max(0, min(horizon, -sum(rel[i]*vel[i] for i in range(3))/speed2))
            miss = math.sqrt(sum((rel[i]+vel[i]*t)**2 for i in range(3)))
            radius = 12 if projectile['kind'] == 'mortar' else 6
            if miss < radius: risk += (1-miss/radius) * (1-t/(horizon+0.1))
        return risk

    def threat(self, pos):
        value = 0
        for t in self.enemies():
            d = distance(pos,t['actor']['pos'])
            value += t['confidence'] * max(0, 1-d/240)**2
        for s in self.sounds:
            value += .18 * max(0, 1-distance(pos,s['pos'])/130) * max(0,1-(self.obs['t']-s['time'])/4)
        return value + self.projectile_risk(pos) * 1.5


def update_perception(state,obs):
    t=obs['t']; me=obs['self']; p=me['pos']; muzzle=(p[0],p[1],p[2]+me['stats']['muzzle_height'])
    for actor in obs.get('mechs',[]):
        height=state.cfg['npc']['height'] if actor['kind']=='npc' else state.cfg['mech']['height']*(1+actor.get('cubes',0)*state.cfg['cubes'].get('size_per_cube',.05))
        center=(actor['pos'][0],actor['pos'][1],actor['pos'][2]+height*.5)
        los=state.world.shot_clear(muzzle,center)
        if not los and actor['kind']=='mech': los=state.world.shot_clear(muzzle,(*actor['pos'][:2],actor['pos'][2]+height*.85))
        state.tracks[actor['id']]={'actor':actor,'seen':t,'los':los}
    state.tracks={k:v for k,v in state.tracks.items() if t-v['seen']<=(120 if v['actor']['kind']=='npc' else 20)}
    for typ in ('crates','cubes','pickups'):
        seen={item['id'] for item in obs.get(typ,[])}
        for item in obs.get(typ,[]): state.items[item['id']]=(typ,item,t)
        for ident,(kind,item,when) in list(state.items.items()):
            if kind!=typ or ident in seen or t-when<=.35 or math.dist(p[:2],item['pos'][:2])>=40: continue
            eye=(p[0],p[1],p[2]+me['stats']['eye_height']); at=(*item['pos'][:2],item['pos'][2]+1.5)
            if state.world.shot_clear(eye,at): del state.items[ident]
    for event in obs.get('events',[]):
        if event['type']=='damaged' and event.get('by') is not None:
            state.last_hurt=t
            state.attacker_memory[event['by']]=t
            if event['by'] in state.tracks: state.hits[event['by']]=t
            if event.get('bearing') is not None: state.hurt_bearing=event['bearing']
        if event['type']=='damaged' and event.get('weapon')=='npc':
            state.npc_hurt=t; state.npc_id=event.get('by'); state.npc_bearing=event.get('bearing')
        elif event['type']=='kill':
            state.kills.add(event['target']); state.tracks.pop(event['target'],None)
        elif event['type'] in ('took','take_failed'):
            state.items.pop(event.get('id'),None)
    state.attacker_memory={ident:when for ident,when in state.attacker_memory.items() if t-when<8}
    if state.initial is None: state.initial=obs['alive']
    z=obs['zone']
    if state.phase!=z['shrink_start'] or t<=z['shrink_start']:
        state.phase=z['shrink_start']; state.hold=(*z['center'],z['radius'])
