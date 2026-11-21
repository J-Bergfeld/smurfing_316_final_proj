"""Per-match memory with uncertain enemy and anonymous sound tracks."""
import math
from .geometry import distance, angle_diff


class World:
    def __init__(self, config, arena):
        self.config, self.arena = config, arena
        self.tracks = {}
        self.sounds = []
        self.last_damage = -1000
        self.last_dealt = -1000
        self.obs = None

    def update(self, obs):
        self.obs = obs; now = obs['t']; me = obs['self']
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
                if e.get('bearing') is not None:
                    self.sounds.append({'pos':[me['pos'][0]+50*math.cos(e['bearing']),me['pos'][1]+50*math.sin(e['bearing'])], 'time':now, 'kind':'damage'})
            if e['type'] == 'hit': self.last_dealt = now

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
