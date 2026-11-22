"""Target evaluation, aiming and weapon trigger control."""
import math
import os
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


def shot_to_surface_clear(world, origin, target, radius):
    """Test the unobstructed path only as far as the target's near surface."""
    length = math.dist(origin, target)
    if length <= radius*.9 + .5: return True
    fraction = (length-radius*.9)/length
    end = tuple(origin[i]+(target[i]-origin[i])*fraction for i in range(3))
    return world.shot_clear(origin, end)


def mortar_pitch(origin, target, speed, gravity):
    d = distance(origin,target); dz = target[2]-origin[2]
    if d < 1: return None
    disc = speed**4 - gravity*(gravity*d*d+2*dz*speed*speed)
    if disc < 0: return None
    return math.atan((speed*speed-math.sqrt(disc))/(gravity*d))


def pressure_gun_hit(d, ours, real_model):
    if real_model:
        points = ((30,.95),(60,.86),(100,.55),(150,.28),(200,.18),(230,.12)) if ours else \
                 ((30,.92),(60,.78),(100,.57),(150,.32),(200,.15),(230,.10))
        if d <= points[0][0]: return points[0][1]
        for (x0,y0),(x1,y1) in zip(points,points[1:]):
            if d <= x1: return y0+(y1-y0)*(d-x0)/(x1-x0)
        return points[-1][1]
    if ours:
        if d < 60: return .95
        if d < 120: return .95-(d-60)/60*.12
        if d < 180: return .83-(d-120)/60*.10
        if d < 230: return .73-(d-180)/50*.15
        return .05
    if d < 40: return .97
    if d < 80: return .97-(d-40)/40*.12
    if d < 120: return .85-(d-80)/40*.40
    if d < 180: return .45-(d-120)/60*.20
    return .12


def pressure_dps(config, kinds, cubes, distance_m, ours, real_model, energy_ok=True):
    weapons=config['weapons']; total=0.
    if 'gun' in kinds and distance_m < weapons['gun'].get('range',230):
        g=weapons['gun']; mag=g.get('mag',12)
        total+=g.get('damage',45)*mag/max(.1,mag*g.get('cooldown',.24)+g.get('reload',2.4))*pressure_gun_hit(distance_m,ours,real_model)
    if 'laser' in kinds and distance_m < weapons['laser'].get('range',280):
        w=weapons['laser']; total+=w.get('damage',315)/max(.1,w.get('charge',.75)+w.get('cooldown',1.65))*(.75 if real_model else .85)
    if 'lightning' in kinds and energy_ok and distance_m < weapons['lightning'].get('range',45)+6:
        w=weapons['lightning']; total+=w.get('damage',60)/max(.1,w.get('cooldown',.25))
    if 'mortar' in kinds and 12 < distance_m < 200:
        w=weapons['mortar']; total+=w.get('damage',200)/max(.1,w.get('cooldown',2.6))*.25
    cube=config['cubes']
    return total*(1+min(cubes,cube.get('stat_cap',10))*cube.get('damage_per_cube',.04))


def pressure_advantage(config, me, enemy, real_model=False):
    """Estimate exchange outcomes now and after closing to practical fight ranges."""
    current=math.dist(me['pos'],enemy['pos'])
    ours={w['kind'] for w in me.get('weapons',[]) if w}
    theirs=set(enemy.get('weapons',[])) or {'gun'}
    enemy_hp=enemy.get('hp',enemy.get('max_hp',1400)) or enemy.get('max_hp',1400)
    armor=max(0.,min(.95,me.get('stats',{}).get('armor',0)))
    our_energy=me.get('energy',0)>15
    def dps_at(d):
        enemy_kinds=theirs
        if 'lightning' in ours and me.get('energy',0)>20 and d<config['weapons']['lightning'].get('range',45)-3:
            enemy_kinds=theirs-{'laser'}
        return (pressure_dps(config,ours,me.get('cubes',0),d,True,real_model,our_energy),
                pressure_dps(config,enemy_kinds,enemy.get('cubes',0),d,False,real_model)*(1-armor))
    best=0.
    for r, here in ((current,True),(24.,False),(38.,False)):
        mine,incoming=dps_at(r)
        if mine < 1: continue
        move=abs(current-r); cost=gain=0.
        if not here and move>8:
            mid_mine,mid_incoming=dps_at((current+r)*.5)
            cost=mid_incoming*(move/9)*.8
            if real_model: gain=mid_mine*(move/9)*.8
            if r>current: cost+=60
        remaining=me['hp']-cost
        if remaining<=0: continue
        enemy_left=max(20,enemy_hp-gain)
        advantage=10. if incoming<1 else (remaining/incoming)/(enemy_left/mine)
        if here: advantage*=1.05
        best=max(best,advantage)
    return best


class Combat:
    def __init__(self, config):
        self.config = config
        self.predict_slew = os.getenv('BOT_FIRE_CONTROL', 'legacy') == 'predictive'

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
                yaw_error=abs(angle_diff(gun_aim[0],me['aim'][0])); pitch_error=abs(gun_aim[1]-me['aim'][1])
                if self.predict_slew:
                    turn=me.get('stats',{}).get('turn_rate',0)*.05
                    pitch=me.get('stats',{}).get('pitch_rate',0)*.05
                    yaw_delta=angle_diff(aim[0],me['aim'][0]); pitch_delta=aim[1]-me['aim'][1]
                    next_yaw=me['aim'][0]+max(-turn,min(turn,yaw_delta))
                    next_pitch=me['aim'][1]+max(-pitch,min(pitch,pitch_delta))
                    yaw_error=abs(angle_diff(gun_aim[0],next_yaw)); pitch_error=abs(gun_aim[1]-next_pitch)
                gun_aligned=yaw_error < max(.018,math.atan2(1.5 if airborne else 2.0,max(1,d))) and pitch_error < max(.025,math.atan2(2.0 if airborne else 3.0,max(1,d)))
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


def lead(muzzle, target, velocity, speed, grounded):
    if speed <= 0:
        speed = 252.
    travel = 0.
    for _ in range(4):
        t = .075 + travel
        x, y = target[0]+velocity[0]*t, target[1]+velocity[1]*t
        z = target[2] if grounded else target[2]+velocity[2]*t*.5
        travel = max(0., math.dist((x,y,z),muzzle)-3.)/speed
    return math.atan2(y-muzzle[1],x-muzzle[0]), math.atan2(z-muzzle[2],math.hypot(x-muzzle[0],y-muzzle[1]))

def mortar_solution(world,tube,foot,velocity,speed,gravity,stats,pressure=False):
    if speed<=0 or gravity<=0: return None
    if pressure:
        # Try the lower trajectory first, then an elevated arc if an obstacle
        # blocks it. Lead is damped as flight time grows.
        for high_arc in (False, True):
            duration=.6
            for _ in range(5):
                damp=max(.95,1-max(0,duration-.3)*.1)
                x=foot[0]+velocity[0]*(.075+duration*damp)
                y=foot[1]+velocity[1]*(.075+duration*damp)
                distance=math.hypot(x-tube[0],y-tube[1]); height=foot[2]+.3-tube[2]
                disc=speed**4-gravity*(gravity*distance*distance+2*height*speed*speed)
                if disc<0 or distance<1: break
                pitch=math.atan2(speed*speed+(1 if high_arc else -1)*math.sqrt(disc),gravity*distance)
                if math.cos(pitch)<.05: break
                duration=distance/(speed*math.cos(pitch))
            else:
                if not stats['min_pitch']<=pitch<=stats['max_pitch'] or duration>6.7: continue
                yaw=math.atan2(y-tube[1],x-tube[0]); steps=int(duration/.12)+2
                clear=True
                for step in range(1,steps):
                    t=duration*step/steps; d=speed*math.cos(pitch)*t
                    if world.solid(tube[0]+math.cos(yaw)*d,tube[1]+math.sin(yaw)*d,tube[2]+speed*math.sin(pitch)*t-.5*gravity*t*t):
                        clear=False; break
                if clear: return yaw,pitch
        return None
    duration=0.
    for _ in range(3):
        x=foot[0]+velocity[0]*(.075+duration); y=foot[1]+velocity[1]*(.075+duration)
        distance=math.hypot(x-tube[0],y-tube[1]); height=foot[2]-tube[2]
        disc=speed**4-gravity*(gravity*distance*distance+2*height*speed*speed)
        if disc<0 or distance<1: return None
        pitch=math.atan((speed*speed-math.sqrt(disc))/(gravity*distance)); yaw=math.atan2(y-tube[1],x-tube[0])
        duration=distance/(speed*math.cos(pitch))
    if pitch<stats['min_pitch'] or pitch>stats['max_pitch']: return None
    t=.1
    while t<duration*.9:
        distance=speed*math.cos(pitch)*t
        if world.solid(tube[0]+math.cos(yaw)*distance,tube[1]+math.sin(yaw)*distance,tube[2]+speed*math.sin(pitch)*t-.5*gravity*t*t): return None
        t+=.1
    return yaw,pitch

def aim_and_fire(me, target, config, squad=False, world=None, pressure=False, allow_fire=True):
    """Aim at an already selected, shootable target and set weapon triggers.

    The caller chooses targets, verifies visibility, and manages charging
    when a target is hidden.
    """
    p=me['pos']; vel=me['vel']; st=me['stats']; pos=target['pos']; tv=target.get('vel',[0,0,0])
    kind=target['kind']; scale=1+target.get('cubes',0)*config['cubes'].get('size_per_cube',.05)
    if kind=='mech': radius,height=config['mech']['radius']*scale,config['mech']['height']*scale
    elif kind=='npc': radius,height=config['npc']['radius'],config['npc']['height']
    else: radius,height=config['crates']['radius'],config['crates']['height']
    use_dev_aim=os.getenv('BOT_AIM_MODEL','sam') == 'dev'
    muzzle=(p[0]+vel[0]*.075,p[1]+vel[1]*.075,p[2]+st['muzzle_height']+(vel[2]*.075 if pressure and not me.get('grounded',True) else 0))
    gun_muzzle=(p[0],p[1],p[2]+st['muzzle_height']) if use_dev_aim and not pressure else muzzle
    center=(pos[0],pos[1],pos[2]+height*.5); dist=math.hypot(center[0]-p[0],center[1]-p[1])
    if pressure: dist=math.dist(muzzle, center)
    weapons=me['weapons']; gun=next((w for w in weapons if w and w['kind']=='gun'),None)
    # Account for input latency; the pressure policy tracks the target's
    # near-term position rather than extrapolating its entire bullet flight.
    gun_point=tuple(center[i]+tv[i]*.075 if i < 2 else center[i] for i in range(3)) if gun and pressure else (intercept(gun_muzzle,center,tv,gun['stats']['speed']) if gun and use_dev_aim else None)
    gy,gp=aim_at(gun_muzzle,gun_point) if gun_point is not None else (lead(muzzle,center,tv,gun['stats']['speed'],abs(tv[2])<.5) if gun else (0.,0.))
    latency=.075 if pressure else .125
    dx=center[0]+tv[0]*latency-muzzle[0]; dy=center[1]+tv[1]*latency-muzzle[1]
    hy,hp=math.atan2(dy,dx),math.atan2(center[2]-muzzle[2],math.hypot(dx,dy))
    beam_clear = True
    if pressure and callable(getattr(world, 'shot_clear', None)) and any(w and w['kind'] in ('laser', 'lightning') for w in me['weapons']):
        point = (center[0]+tv[0]*latency, center[1]+tv[1]*latency, center[2])
        beam_clear = shot_to_surface_clear(world, muzzle, point, radius)
    aim=[gy,gp] if gun else [hy,hp]; fire=[False,False]
    laser=next((w for w in weapons if w and w['kind']=='laser'),None)
    laser_ready=False
    if pressure and laser and laser.get('charge',0)>0:
        ls=laser['stats']; charge=laser['charge']; full=ls['charge']
        damage=ls['damage']*(ls['min_frac']+(1-ls['min_frac'])*min(1,(charge+.1)/full))
        damage*=1+config['cubes']['damage_per_cube']*min(me['cubes'],config['cubes']['stat_cap'])
        laser_ready=charge>=full-.16 or damage>=target.get('hp',math.inf)
    tol_y=math.atan2(radius*(2.2 if pressure else .75),max(dist,1))
    tol_p=math.atan2(height*(.72 if pressure else .4),max(dist,1))
    actual=me['aim']; ey=lambda y:abs(angle_diff(y,actual[0])); ep=lambda x:abs(x-actual[1])
    for i,w in enumerate(weapons[:2]):
        if not w: continue
        s=w['stats']; wk=w['kind']
        if wk=='gun':
            gun_range=min(s['range']-5,120 if kind!='mech' else 230) if pressure else s['range']*.96
            fire[i]=bool(dist<gun_range and w.get('ammo',0)>0 and w.get('reload',0)<=0 and
                         max(0.,ey(gy)-st['turn_rate']*(.045 if pressure else .05))<tol_y and max(0.,ep(gp)-st['pitch_rate']*(.045 if pressure else .05))<tol_p)
            if fire[i] and use_dev_aim and world is not None:
                fire[i]=shot_to_surface_clear(world,gun_muzzle,gun_point,radius) if pressure else world.shot_clear(gun_muzzle,gun_point)
        elif wk=='lightning':
            if pressure:
                relative_speed=math.hypot(tv[0]-vel[0],tv[1]-vel[1])
                fire[i]=bool(beam_clear and dist<s['range']-1-.05*relative_speed
                             and max(0.,ey(hy)-st['turn_rate']*.045)<math.radians(s['cone_deg'])*.4
                             and me['energy']>=s['energy'])
            else:
                fire[i]=bool(dist<s['range']-1.5 and ey(hy)<math.radians(s['cone_deg'])*.5-.05 and me['energy']>=s['energy'])
        elif wk=='laser' and (kind=='mech' or pressure) and (dist<(s['range']-4 if pressure else s['range']*.97) or (pressure and w.get('charge',0)>0)):
            charge=w.get('charge',0); full=s['charge']; lethal=False
            if pressure:
                damage_scale=1+config['cubes']['damage_per_cube']*min(me['cubes'],config['cubes']['stat_cap'])
                def beam_damage(value):
                    return s['damage']*(s['min_frac']+(1-s['min_frac'])*min(1,value/full))*damage_scale
                if charge>0 and (charge>=full-.16 or beam_damage(charge+.1)>=target.get('hp',math.inf)):
                    aim=[hy,hp]
                if charge>0:
                    lethal=charge>=s['min_charge'] and beam_damage(charge)>=target.get('hp',math.inf)
                    yaw_left=max(0.,ey(hy)-st['turn_rate']*.045)
                    pitch_left=max(0.,ep(hp)-st['pitch_rate']*.045)
                    aligned=yaw_left<math.atan2(radius*2,max(dist,1)) and pitch_left<math.atan2(height*.68,max(dist,1))
                    fire[i]=not ((charge>=full-.001 or lethal) and aligned and beam_clear and dist<s['range']-4)
                else:
                    fire[i]=w.get('cooldown',0)<=.12 and dist<s['range']-4
                continue
            if squad and s['min_charge']<=charge<full-.051:
                count=min(me['cubes'],config['cubes']['stat_cap'])
                damage=s['damage']*(s['min_frac']+(1-s['min_frac'])*charge/full)*(1+config['cubes']['damage_per_cube']*count)
                if 'mortar' in target.get('weapons',[]): damage*=1+s['cookoff']
                lethal=damage*.7>=target.get('hp',math.inf) and ey(hy)<tol_y*.9 and ep(hp)<tol_p
            if lethal:
                aim=[hy,hp]
            elif charge<full-.051:
                fire[i]=bool(charge > 0 or not pressure or w.get('cooldown', 0) <= .12)
                if charge>full*.45: aim=[hy,hp]
            else:
                aim=[hy,hp]; fire[i]=not (ey(hy)<tol_y*.9 and ep(hp)<tol_p)
        elif wk=='mortar' and allow_fire and world is not None and not laser_ready and (kind=='mech' or pressure) and w.get('cooldown',0)<=(.15 if pressure else .25) and 16<=dist<=200:
            tube=(muzzle[0],muzzle[1],p[2]+st['height']+.5)
            solution=mortar_solution(world,tube,pos,tv,s.get('speed',0),s.get('gravity',0),st,pressure)
            if solution:
                yaw,pitch=solution
                gun_idle=not gun or gun.get('reload',0)>0 or gun.get('ammo',0)==0 or dist>gun['stats']['range']*.96
                flight=dist/max(1.,s.get('speed',72)*math.cos(pitch))
                miss=math.hypot(tv[0],tv[1])*flight*(.5 if kind=='mech' else .2)
                promising=pressure and dist>s.get('splash_radius',7)+st['radius']+3 and miss<s.get('splash_radius',7)*.75
                if gun_idle or promising: aim=[yaw,pitch]
                if (not pressure or w.get('cooldown',0)<=.05) and (not pressure or gun_idle or promising):
                    fire[i]=max(0.,ey(yaw)-st['turn_rate']*.05)<.04 and max(0.,ep(pitch)-st['pitch_rate']*.05)<.03
    aim[1]=max(st['min_pitch'],min(st['max_pitch'],aim[1]))
    if gun and os.getenv('BOT_GUN_AIM_CHECK', 'actual') == 'actual':
        gun_primary=not pressure or (abs(angle_diff(aim[0],gy))<1e-8 and abs(aim[1]-gp)<1e-8)
        step=(.045 if pressure else .05) if gun_primary else 0.
        yaw_step=max(-st['turn_rate']*step,min(st['turn_rate']*step,angle_diff(aim[0],actual[0])))
        pitch_step=max(-st['pitch_rate']*step,min(st['pitch_rate']*step,aim[1]-actual[1]))
        aligned=abs(angle_diff(gy,actual[0]+yaw_step))<tol_y and abs(gp-actual[1]-pitch_step)<tol_p
        for i,w in enumerate(weapons[:2]):
            if w and w['kind']=='gun': fire[i]=fire[i] and aligned
    return {'aim':aim,'fire':fire}

def favorable_fight(state, obs, track, hp):
    """Initiate a visible, isolated fight when a rough exchange looks favorable."""
    me = obs['self']; target = track['actor']; now = obs['t']
    d = math.dist(me['pos'][:2], target['pos'][:2])
    if hp <= .6 or state.retreat or not track['los'] or d >= 130:
        return False
    # Avoid initiating with an empty/reloading gun or an unavailable laser.
    ready = any(w and ((w['kind'] == 'gun' and w.get('ammo', 0) > 0 and w.get('reload', 0) <= 0)
                       or (w['kind'] == 'laser' and w.get('cooldown', 0) <= .25)
                       or (getattr(state, 'pressure_policy', False) and w['kind'] == 'lightning'
                           and me['energy'] >= w['stats']['energy']))
                for w in me.get('weapons', []))
    if not ready:
        return False
    for other in state.tracks.values():
        actor = other['actor']
        if (not getattr(state, 'pressure_policy', False)
                and actor['id'] != target['id'] and actor['kind'] == 'mech'
                and now - other['seen'] < 2.5
                and math.dist(me['pos'][:2], actor['pos'][:2]) < 160):
            return False
    threshold = .7 if getattr(state, 'pressure_policy', False) else 1.3
    return Combat(state.cfg).estimate(me, target, 1) >= threshold


def assess_pressure(state, obs):
    """Build a compact picture of opponents and their immediate pressure."""
    me, now = obs['self'], obs['t']
    known, engaged = [], []
    for track in state.tracks.values():
        actor = track['actor']
        age = now - track['seen']
        if actor['kind'] != 'mech' or age > 8:
            continue
        d = math.dist(me['pos'], actor['pos'])
        ground_distance = math.dist(me['pos'][:2], actor['pos'][:2])
        current = track['seen'] == now
        bearing = math.atan2(me['pos'][1]-actor['pos'][1], me['pos'][0]-actor['pos'][0])
        aim_error = abs(angle_diff(actor.get('aim', [bearing])[0], bearing))
        if current and aim_error < .12+math.atan2(1.5*me['stats']['radius'],max(1,ground_distance)):
            state.pressure_aim_times[actor['id']] = now
        aimed = now-state.pressure_aim_times.get(actor['id'],-100) < .6
        attacking = now - state.hits.get(actor['id'], -100) < 4
        aim_range = 285 if 'laser' in actor.get('weapons',[]) else 200
        vel=actor.get('vel',[0,0,0])
        closing=(vel[0]*(me['pos'][0]-actor['pos'][0])+vel[1]*(me['pos'][1]-actor['pos'][1]))/max(1,ground_distance)
        active = attacking or (current and track['los'] and (d < 40 or (d < aim_range and aimed)
                            or (d < 90 and aim_error < .5 and closing > 4)))
        if active:
            state.pressure_engage_times[actor['id']] = now
        elif current and now-state.pressure_engage_times.get(actor['id'],-100) < .8:
            active = True
        track['engage'] = active
        item = {'actor': actor, 'track': track, 'distance': d, 'current': current, 'active': active}
        known.append(item)
        if active:
            engaged.append(item)
    unseen_at = getattr(state, 'unseen_hit_at', -100)
    unseen_track = state.tracks.get(getattr(state, 'unseen_hit_id', None))
    if now-unseen_at < 4 and (unseen_track is None or now-unseen_track['seen'] > 1):
        bearing = state.unseen_hit_bearing
        pos = getattr(state, 'unseen_hit_position', None) or [me['pos'][0]+math.cos(bearing)*state.unseen_hit_distance,
                                                              me['pos'][1]+math.sin(bearing)*state.unseen_hit_distance, me['pos'][2]]
        distance = math.dist(me['pos'], pos)
        ghost = {'id': -1, 'kind': 'mech', 'pos': pos,
                 'vel': [0, 0, 0], 'hp': 1400, 'weapons': ['gun']}
        item = {'actor': ghost, 'track': {'actor': ghost, 'seen': unseen_at, 'los': False},
                'distance': distance, 'current': False, 'active': True, 'phantom': True}
        known.append(item)
        engaged.append(item)
    visible = [item for item in known if item['current']]
    target = max(visible, key=lambda item: (1.5 if item['track']['los'] else 1)/(1+item['distance']/60), default=None)
    return known, engaged, target


def assess_combat(state, obs, squad, late, hp):
    """Select threats and update the current retreat decision."""
    me=obs['self']; p=me['pos']; t=obs['t']
    seen=[]; choices=[]; hidden=[]; danger=False; crowd=0
    for tr in state.tracks.values():
        a=tr['actor']
        if a['kind']!='mech' or t-tr['seen']>2.5: continue
        seen.append(a)
        tr['engage']=False
        if tr['seen']!=t: continue
        d=math.dist(p[:2],a['pos'][:2]); to_me=math.atan2(p[1]-a['pos'][1],p[0]-a['pos'][0]); aimed=abs(angle_diff(a['aim'][0],to_me))<.22
        recent=t-state.hits.get(a['id'],-100)<(6 if squad else 4)
        closing=((a['vel'][0]-me['vel'][0])*(p[0]-a['pos'][0])+(a['vel'][1]-me['vel'][1])*(p[1]-a['pos'][1]))/max(1,d)
        engage=d<60 or recent or obs['alive']<=2 or (a.get('hp',1400)<350 and d<120) or (aimed and a.get('charging') and d<120)
        if squad: engage=engage or late or (closing>3 and d<180) or (aimed and d<190) or (a.get('hp',1400)<.4*a.get('max_hp',1400) and d<160)
        if squad and not engage and favorable_fight(state, obs, tr, hp): engage=True
        tr['engage']=engage
        if engage or t-state.hits.get(a['id'],-100)<4: danger=True
        if engage or (tr['los'] and d<150): crowd+=1
        if engage and not tr['los'] and d<(240 if squad else 215): hidden.append((d,a['id'],a))
        if not engage or not tr['los'] or d>(240 if squad else 215): continue
        cost=d+(.18 if squad else 60/1400)*a.get('hp',1400)
        if squad and a['id']==state.target_id and t-state.target_at<2: cost-=200
        if squad and a.get('hp',1400)<=.3*a.get('max_hp',1400): cost-=200
        if recent: cost-=40
        if closing>3: cost-=15
        choices.append((cost,a['id'],a))
    target=min(choices,default=(0,0,None))[2]
    foe=target or (min(hidden,default=(0,0,None))[2] if not squad else None)
    if target: state.target_id=target['id']; state.target_at=t
    if danger or t-state.last_hurt<3: state.last_threat=t
    finishing=bool(target and math.dist(p[:2],target['pos'][:2])<120 and (target['hp']<200 or target['hp']<me['hp']*.5))
    near=sum(tr['seen']==t and math.dist(p[:2],tr['actor']['pos'][:2])<160 for tr in state.tracks.values() if tr['actor']['kind']=='mech')
    losing=(near>=2 and hp<.55) or (near>=3 and hp<.8)
    if target and hp<.35 and target['hp']/max(1,target['max_hp'])>hp+.1: losing=True
    if target and target['hp']/max(1,target['max_hp'])<.25 and hp>.2 and near<=2: losing=False
    if losing: state.lose_at=t
    if squad: state.retreat=t-state.lose_at<1.5 and state.lose_at>0
    else:
        outgunned=bool(target and 'laser' in target.get('weapons',[]) and not any(w and w['kind']=='laser' for w in me['weapons']) and math.dist(p[:2],target['pos'][:2])>55 and hp<.8)
        swamped=crowd>=3 or (crowd==2 and hp<.65) or outgunned
        if not state.retreat and ((hp<.38 and t-state.last_threat<2) or swamped): state.retreat=True; state.movement.cover=None
        if state.retreat and not swamped and (hp>.8 or (t-state.last_threat>7 and hp>.55)): state.retreat=False
    return seen, target, foe, danger, finishing

def apply_weapon_control(state, obs, action, target, foe, squad):
    """Choose a defensive target, aim, and update weapon triggers."""
    me=obs['self']; p=me['pos']; t=obs['t']
    pressure = getattr(state, 'decision_policy', '') == 'pressure'
    if pressure:
        for sound in obs.get('sounds', []):
            if sound.get('kind') in ('gun', 'laser', 'lightning', 'mortar', 'laser_charge', 'boost', 'step', 'jet', 'reload') and sound.get('dist') != 'far':
                state.scan_sound_at = t - sound.get('age', 0)
                state.scan_sound_bearing = sound['bearing']
    if not target and t-state.npc_hurt<3:
        candidates=[]
        for track in state.tracks.values():
            actor=track['actor']
            if actor['kind']!='npc' or (track['seen'] != t if pressure else t-track['seen']>.5) or not track['los']: continue
            d=math.dist(p[:2],actor['pos'][:2])
            bearing=math.atan2(actor['pos'][1]-p[1],actor['pos'][0]-p[0])
            error=abs(angle_diff(bearing,state.npc_bearing)) if state.npc_bearing is not None else math.inf
            if d<150 and (actor['id']==state.npc_id or error<.7): candidates.append((error,d,actor['id'],actor))
        if candidates: target=min(candidates)[-1]
    if target:
        try: action.update(aim_and_fire(me,target,state.cfg,squad,state.world,
                                        getattr(state, 'decision_policy', '') == 'pressure'))
        except (KeyError,ValueError,ZeroDivisionError): pass
        if getattr(state, 'decision_policy', '') == 'pressure':
            if any(w and w['kind'] == 'gun' and w.get('ammo', 0) <= 0 and w.get('reload', 0) <= 0 for w in me['weapons']):
                action['reload'] = True
    else:
        watch=[tr['actor'] for tr in state.tracks.values() if tr['actor']['kind']=='mech' and t-tr['seen']<(.11 if pressure else 2.5) and
               (pressure or tr.get('engage',False) or t-state.hits.get(tr['actor']['id'],-100)<6)]
        if watch:
            nearest=min(watch,key=lambda a:math.dist(p[:2],a['pos'][:2]))
            yaw=math.atan2(nearest['pos'][1]-p[1],nearest['pos'][0]-p[0])
        elif pressure and t < 1.75: yaw=me['aim'][0]+.39
        elif t-state.npc_hurt<2.5 and state.npc_bearing is not None: yaw=state.npc_bearing
        elif t-state.last_hurt<2.5: yaw=state.hurt_bearing
        elif pressure and t-getattr(state, 'scan_sound_at', -100) < 1.5: yaw=state.scan_sound_bearing
        elif pressure:
            match=state.cfg.get('match',{})
            state.scan_phase=getattr(state, 'scan_phase', 0.)+match.get('decide_every',2)/match.get('tick_hz',20)
            yaw=(math.atan2(action['move'][1],action['move'][0])+1.9*math.sin(state.scan_phase*1.3)
                 if any(action['move']) else me['aim'][0]+.35)
        elif any(action['move']): yaw=math.atan2(action['move'][1],action['move'][0])+1.15*math.sin(t*1.3)
        else: yaw=me['aim'][0]+.35
        action['aim']=[yaw,0]
        if pressure and watch:
            try:
                watched = aim_and_fire(me, nearest, state.cfg, squad, state.world, True, False)
                action['aim'] = watched['aim']
                for i, w in enumerate(me['weapons'][:2]):
                    if w and w['kind'] == 'laser' and w.get('charge', 0) > 0:
                        action['fire'][i] = watched['fire'][i]
            except (KeyError, ValueError, ZeroDivisionError):
                pass
        if not pressure or not watch:
            for w in me['weapons']:
                if w and w['kind']=='gun' and w.get('reload',0)<=0 and w.get('ammo',0)<w['stats']['mag']*(.67 if pressure else .6): action['reload']=True
        if pressure and not watch and any(tr['actor']['kind']=='mech' and t-tr['seen']<1.5 for tr in state.tracks.values()):
            for i, w in enumerate(me['weapons'][:2]):
                if w and w['kind']=='laser' and w.get('charge',0)>0: action['fire'][i]=True
    if target is None and foe is not None and getattr(state, 'decision_policy', '') != 'pressure':
        distance=math.dist(p[:2],foe['pos'][:2])
        for i,w in enumerate(me['weapons'][:2]):
            if w and w['kind']=='laser' and w.get('cooldown',0)<=.05 and distance<w['stats']['range'] and w['charge']<w['stats']['charge']+w['stats']['hold_s']-.35: action['fire'][i]=True
