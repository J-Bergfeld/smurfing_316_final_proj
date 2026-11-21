"""Target evaluation, aiming and weapon trigger control."""
import math
from .geometry import distance, angle_diff


def intercept(origin, target, velocity, speed):
    r = [target[i]-origin[i] for i in range(3)]
    a = sum(v*v for v in velocity)-speed*speed
    b = 2*sum(r[i]*velocity[i] for i in range(3)); c = sum(x*x for x in r)
    disc = b*b-4*a*c
    times = []
    if abs(a) < 1e-8:
        if abs(b)>1e-8: times = [-c/b]
    elif disc >= 0:
        times = [(-b-math.sqrt(disc))/(2*a),(-b+math.sqrt(disc))/(2*a)]
    t = min((x for x in times if x >= 0), default=0)
    return [target[i]+velocity[i]*t for i in range(3)]


def aim_at(origin, target):
    dx,dy,dz = (target[i]-origin[i] for i in range(3))
    return [math.atan2(dy,dx),math.atan2(dz,math.hypot(dx,dy))]


def mortar_pitch(origin, target, speed, gravity):
    d = distance(origin,target); dz = target[2]-origin[2]
    if d < 1: return None
    disc = speed**4 - gravity*(gravity*d*d+2*dz*speed*speed)
    if disc < 0: return None
    return math.atan((speed*speed-math.sqrt(disc))/(gravity*d))


class Combat:
    def __init__(self, config): self.config = config

    def estimate(self, me, enemy, count, engaged=False):
        d = distance(me['pos'], enemy['pos']); our = 0
        for w in me.get('weapons',[]):
            if not w: continue
            s = w['stats']; kind = w['kind']
            if kind == 'gun' and d <= s.get('range',230):
                ready = .35 if w.get('reload',0)>0 or w.get('ammo',1)==0 else 1
                our += ready*s.get('damage',45)/max(.1,s.get('cooldown',.24))*.55
            if kind == 'laser' and d <= s.get('range',280): our += s.get('damage',315)/(s.get('charge',.75)+s.get('cooldown',1.65))*.65
            if kind == 'lightning' and d <= s.get('range',45): our += s.get('damage',60)/max(.1,s.get('cooldown',.25))*.8
            if kind == 'mortar' and 20 < d < 200: our += s.get('damage',200)/max(.1,s.get('cooldown',2.6))*.5
        weapons = enemy.get('weapons',['gun']); incoming = 65 + (55 if 'laser' in weapons and d < 280 else 0) + (100 if 'lightning' in weapons and d < 50 else 0)
        incoming *= max(1, count*.8)
        bearing = math.atan2(me['pos'][1]-enemy['pos'][1],me['pos'][0]-enemy['pos'][0])
        if engaged and abs(angle_diff(bearing,enemy.get('aim',[bearing])[0])) > math.pi/2:
            our *= self.config.get('mech',{}).get('rear_mult',1.5)
        return (our/max(1,enemy.get('hp',1400))) / (incoming/max(1,me['hp']))

    def action(self, world, target, mode):
        obs = world.obs; me = obs['self']; out = {'fire':[False,False]}
        if not target:
            for w in me.get('weapons', []):
                if w and w['kind']=='gun' and w.get('reload',0)<=0 and w.get('ammo',0)<w.get('stats',{}).get('mag',12): out['reload']=True
            # A charged laser cannot be cancelled. Point away from the arena
            # before releasing it, while respecting the weapon's hold limit.
            for i,w in enumerate(me.get('weapons',[])[:2]):
                if w and w['kind']=='laser' and w.get('charge',0)>0:
                    high=me.get('stats',{}).get('max_pitch',1.3)
                    out['aim']=[me['aim'][0],high]
                    out['fire'][i]=bool(me['aim'][1] < high-.08 and w['charge'] < w['stats'].get('charge',.75)+w['stats'].get('hold_s',2)-.2)
            return out
        actor = target['actor']; pos = actor['pos']; d = distance(me['pos'],pos)
        mz = me.get('stats',{}).get('muzzle_height',7)
        origin = [me['pos'][0],me['pos'][1],me['pos'][2]+mz]
        height = 4.5 if actor.get('kind') == 'mech' else (1.75 if actor.get('kind') == 'npc' else 1.2)
        dest = [pos[0],pos[1],pos[2]+height]
        weapons = me.get('weapons',[])
        preferred = next((w for w in weapons if w and w['kind']=='laser' and w.get('charge',0)>0),None)
        if not preferred: preferred = next((w for w in weapons if w and w['kind']=='gun' and w.get('reload',0)<=0 and w.get('ammo',0)>0),None)
        if not preferred: preferred = next((w for w in weapons if w and w['kind']!='gun'),None)
        if not preferred: preferred = next((w for w in weapons if w),None)
        gun = next((w for w in weapons if w and w['kind']=='gun' and w.get('reload',0)<=0 and w.get('ammo',0)>0),None)
        laser = next((w for w in weapons if w and w['kind']=='laser' and w.get('charge',0)>0),None)
        # During early charge, a gun can lead while the torso has enough time
        # to return to the laser solution before the beam is ready.
        if laser and gun:
            beam_aim=aim_at(origin,dest)
            gun_dest=intercept(origin,dest,actor.get('vel',[0,0,0]),gun['stats'].get('speed',252))
            gun_aim=aim_at(origin,gun_dest)
            stats=me.get('stats',{}); turn=max(.01,stats.get('turn_rate',4)); pitch=max(.01,stats.get('pitch_rate',4))
            remaining=laser['stats'].get('charge',.75)-laser.get('charge',0)
            return_time=max(abs(angle_diff(gun_aim[0],beam_aim[0]))/turn,abs(gun_aim[1]-beam_aim[1])/pitch)
            if remaining > return_time+.2: preferred=gun
        if preferred and preferred['kind']=='gun': dest = intercept(origin,dest,actor.get('vel',[0,0,0]),preferred['stats'].get('speed',252))
        aim = aim_at(origin,dest)
        # Mortar needs a ballistic elevation and cannot share aim with a gun accurately.
        use_mortar = preferred and preferred['kind']=='mortar'
        if use_mortar:
            s = preferred['stats']; pitch = mortar_pitch(origin,dest,s.get('speed',72),s.get('gravity',22))
            if pitch is not None: aim[1] = pitch
        out['aim'] = aim
        yaw_error = abs(angle_diff(aim[0],me['aim'][0])); pitch_error = abs(aim[1]-me['aim'][1])
        airborne = not me.get('grounded',True)
        aligned = yaw_error < max(.018,math.atan2(1.5 if airborne else 2.0,max(1,d))) and pitch_error < max(.025, math.atan2(2.0 if airborne else 3.0,max(1,d)))
        clear = target.get('visible',False) and world.arena.clear(origin,[pos[0],pos[1],pos[2]+height])
        if mode == 'flee' and actor.get('kind') == 'mech': clear = clear and d < 110
        for i,w in enumerate(weapons[:2]):
            if not w: continue
            s = w['stats']; kind = w['kind']; cd = w.get('cooldown',0)
            if kind == 'gun':
                gun_dest=intercept(origin,[pos[0],pos[1],pos[2]+height],actor.get('vel',[0,0,0]),s.get('speed',252))
                gun_aim=aim_at(origin,gun_dest)
                gun_aligned=abs(angle_diff(gun_aim[0],me['aim'][0])) < max(.018,math.atan2(1.5 if airborne else 2.0,max(1,d))) and abs(gun_aim[1]-me['aim'][1]) < max(.025,math.atan2(2.0 if airborne else 3.0,max(1,d)))
                out['fire'][i] = bool(clear and gun_aligned and d <= s.get('range',230) and w.get('ammo',1)>0 and w.get('reload',0)<=0 and not use_mortar and world.arena.clear(origin,gun_dest))
                if w.get('reload',0)<=0 and w.get('ammo',1)<s.get('mag',12)*.4 and (not clear or mode in ('flee','hold','recover')): out['reload'] = True
            elif kind == 'laser':
                charge = w.get('charge',0); ready = cd <= 0 and d <= s.get('range',280)
                # Releasing the trigger fires; release immediately when the target is lost.
                beam_aim=aim_at(origin,[pos[0],pos[1],pos[2]+height])
                beam_aligned=abs(angle_diff(beam_aim[0],me['aim'][0])) < max(.018,math.atan2(2.0,max(1,d))) and abs(beam_aim[1]-me['aim'][1]) < max(.025,math.atan2(3.0,max(1,d)))
                acquire=abs(angle_diff(beam_aim[0],me['aim'][0])) < .35 and abs(beam_aim[1]-me['aim'][1]) < .25
                out['fire'][i] = bool(clear and ready and not use_mortar and ((charge == 0 and acquire) or (charge > 0 and (charge < s.get('charge',.75) or not beam_aligned))))
            elif kind == 'lightning':
                direction=math.atan2(pos[1]-origin[1],pos[0]-origin[0])
                out['fire'][i] = bool(clear and abs(angle_diff(direction,me['aim'][0])) < math.radians(s.get('cone_deg',30)/2)*.8 and d <= s.get('range',45) and me['energy'] >= s.get('energy',3))
            elif kind == 'mortar' and use_mortar:
                pitch=mortar_pitch(origin,dest,s.get('speed',72),s.get('gravity',22))
                arc_clear=False
                if pitch is not None and aligned and 25 < d < 200:
                    speed=s.get('speed',72); gravity=s.get('gravity',22)
                    duration=d/max(1,speed*math.cos(pitch)); previous=origin; arc_clear=True
                    for step in range(1,9):
                        t=duration*step/8
                        point=[origin[0]+math.cos(aim[0])*speed*math.cos(pitch)*t,origin[1]+math.sin(aim[0])*speed*math.cos(pitch)*t,origin[2]+speed*math.sin(pitch)*t-.5*gravity*t*t]
                        if not world.arena.clear(previous,point): arc_clear=False; break
                        previous=point
                out['fire'][i] = bool(clear and aligned and arc_clear)
        return out
