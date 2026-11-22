"""Bounded per-opponent virtual-shot tracking for gun lead."""
from collections import deque
import math


class LeadTracker:
    def __init__(self):
        self.tracks = {}

    def observe(self, actor, me, now):
        if actor.get('kind') != 'mech': return
        gun = next((w for w in me.get('weapons', []) if w and w['kind'] == 'gun'), None)
        if not gun: return
        speed = gun.get('stats', {}).get('speed', 0)
        if speed <= 0: return
        ident=actor['id']; track=self.tracks.setdefault(ident, {'samples': deque(maxlen=64), 'n': 0., 'still': 0., 'lead': 0.})
        samples=track['samples']
        if samples and now<=samples[-1][0]: return
        if samples and now-samples[-1][0]>.25: samples.clear()
        pos=actor['pos']; distance=math.dist(me['pos'][:2],pos[:2])
        flight=max(0.,distance-3.)/speed
        target_time=now-(.075+flight)
        sample=min(samples,key=lambda s:abs(s[0]-target_time),default=None)
        if sample and abs(sample[0]-target_time)<.075 and 55<distance<240:
            _, x, y, vx, vy, sx, sy=sample
            # Compare lateral error: range error along the ray does not change
            # whether a direct shot intersects the target.
            def miss(px,py):
                dx,dy=px-sx,py-sy; length=math.hypot(dx,dy)
                if length<1e-6: return 6.
                return min(6.,abs((pos[0]-sx)*dy-(pos[1]-sy)*dx)/length)
            predicted=(x+vx*(.075+flight),y+vy*(.075+flight))
            track['n']=track['n']*.997+1
            track['still']=track['still']*.997+miss(x,y)
            track['lead']=track['lead']*.997+miss(*predicted)
        velocity=actor.get('vel',(0,0,0))
        samples.append((now,pos[0],pos[1],velocity[0],velocity[1],me['pos'][0],me['pos'][1]))

    def factor(self, actor):
        if actor.get('kind') != 'mech': return 1.
        track=self.tracks.get(actor.get('id'))
        if not track or track['n']<12: return .45
        delta=(track['still']-track['lead'])/track['n']
        if delta>.15: return 1.
        if delta<-.15: return 0.
        return .45
