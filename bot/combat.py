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


def mortar_pitch(origin, target, speed, gravity):
    d = distance(origin,target); dz = target[2]-origin[2]
    if d < 1: return None
    disc = speed**4 - gravity*(gravity*d*d+2*dz*speed*speed)
    if disc < 0: return None
    return math.atan((speed*speed-math.sqrt(disc))/(gravity*d))


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

def mortar_solution(world,tube,foot,velocity,speed,gravity,stats):
    if speed<=0 or gravity<=0: return None
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

def aim_and_fire(me, target, config, squad=False, world=None):
    """Aim at an already selected, shootable target and set weapon triggers.

    The caller chooses targets, verifies visibility, and manages charging
    when a target is hidden.
    """
    p=me['pos']; vel=me['vel']; st=me['stats']; pos=target['pos']; tv=target.get('vel',[0,0,0])
    kind=target['kind']; scale=1+target.get('cubes',0)*config['cubes'].get('size_per_cube',.05)
    if kind=='mech': radius,height=config['mech']['radius']*scale,config['mech']['height']*scale
    elif kind=='npc': radius,height=config['npc']['radius'],config['npc']['height']
    else: radius,height=config['crates']['radius'],config['crates']['height']
    muzzle=(p[0]+vel[0]*.075,p[1]+vel[1]*.075,p[2]+st['muzzle_height'])
    center=(pos[0],pos[1],pos[2]+height*.5); dist=math.hypot(center[0]-p[0],center[1]-p[1])
    weapons=me['weapons']; gun=next((w for w in weapons if w and w['kind']=='gun'),None)
    gy,gp=lead(muzzle,center,tv,gun['stats']['speed'],abs(tv[2])<.5) if gun else (0.,0.)
    dx=center[0]+tv[0]*.125-muzzle[0]; dy=center[1]+tv[1]*.125-muzzle[1]
    hy,hp=math.atan2(dy,dx),math.atan2(center[2]-muzzle[2],math.hypot(dx,dy))
    aim=[gy,gp] if gun else [hy,hp]; fire=[False,False]
    tol_y=math.atan2(radius*.75,max(dist,1)); tol_p=math.atan2(height*.4,max(dist,1))
    actual=me['aim']; ey=lambda y:abs(angle_diff(y,actual[0])); ep=lambda x:abs(x-actual[1])
    for i,w in enumerate(weapons[:2]):
        if not w: continue
        s=w['stats']; wk=w['kind']
        if wk=='gun':
            fire[i]=bool(dist<=s['range']*.96 and w.get('ammo',0)>0 and w.get('reload',0)<=0 and
                         max(0.,ey(gy)-st['turn_rate']*.05)<tol_y and max(0.,ep(gp)-st['pitch_rate']*.05)<tol_p)
        elif wk=='lightning':
            fire[i]=bool(dist<s['range']-1.5 and ey(hy)<math.radians(s['cone_deg'])*.5-.05 and me['energy']>=s['energy'])
        elif wk=='laser' and kind=='mech' and dist<=s['range']*.97:
            charge=w.get('charge',0); full=s['charge']; lethal=False
            # Do not start a new charge over an available gun magazine in the
            # reload-only trial. Finish any charge already started; dropping
            # the trigger would release a weak shot instead of cancelling it.
            if (squad and os.getenv('BOT_LASER_TIMING') == 'reload'
                    and charge <= 0 and gun and gun.get('ammo', 0) > 0
                    and gun.get('reload', 0) <= 0 and dist <= gun['stats']['range'] * .96):
                continue
            if squad and s['min_charge']<=charge<full-.051:
                count=min(me['cubes'],config['cubes']['stat_cap'])
                damage=s['damage']*(s['min_frac']+(1-s['min_frac'])*charge/full)*(1+config['cubes']['damage_per_cube']*count)
                if 'mortar' in target.get('weapons',[]): damage*=1+s['cookoff']
                lethal=damage*.7>=target.get('hp',math.inf) and ey(hy)<tol_y*.9 and ep(hp)<tol_p
            if lethal:
                aim=[hy,hp]
            elif charge<full-.051:
                fire[i]=True
                if charge>full*.45: aim=[hy,hp]
            else:
                aim=[hy,hp]; fire[i]=not (ey(hy)<tol_y*.9 and ep(hp)<tol_p)
        elif wk=='mortar' and world is not None and kind=='mech' and w.get('cooldown',0)<=.25 and 16<=dist<=200:
            tube=(muzzle[0],muzzle[1],p[2]+st['height']+.5)
            solution=mortar_solution(world,tube,pos,tv,s.get('speed',0),s.get('gravity',0),st)
            if solution:
                yaw,pitch=solution
                if not gun or gun.get('reload',0)>0 or gun.get('ammo',0)==0 or dist>gun['stats']['range']*.96: aim=[yaw,pitch]
                fire[i]=max(0.,ey(yaw)-st['turn_rate']*.05)<.04 and max(0.,ep(pitch)-st['pitch_rate']*.05)<.03
    aim[1]=max(st['min_pitch'],min(st['max_pitch'],aim[1]))
    if gun and os.getenv('BOT_GUN_AIM_CHECK', 'actual') == 'actual':
        yaw_step=max(-st['turn_rate']*.05,min(st['turn_rate']*.05,angle_diff(aim[0],actual[0])))
        pitch_step=max(-st['pitch_rate']*.05,min(st['pitch_rate']*.05,aim[1]-actual[1]))
        aligned=abs(angle_diff(gy,actual[0]+yaw_step))<tol_y and abs(gp-actual[1]-pitch_step)<tol_p
        for i,w in enumerate(weapons[:2]):
            if w and w['kind']=='gun': fire[i]=fire[i] and aligned
    return {'aim':aim,'fire':fire}

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
    if not target and t-state.npc_hurt<3:
        candidates=[]
        for track in state.tracks.values():
            actor=track['actor']
            if actor['kind']!='npc' or t-track['seen']>.5 or not track['los']: continue
            d=math.dist(p[:2],actor['pos'][:2])
            bearing=math.atan2(actor['pos'][1]-p[1],actor['pos'][0]-p[0])
            error=abs(angle_diff(bearing,state.npc_bearing)) if state.npc_bearing is not None else math.inf
            if d<150 and (actor['id']==state.npc_id or error<.7): candidates.append((error,d,actor['id'],actor))
        if candidates: target=min(candidates)[-1]
    if target:
        try: action.update(aim_and_fire(me,target,state.cfg,squad,state.world))
        except (KeyError,ValueError,ZeroDivisionError): pass
    else:
        watch=[tr['actor'] for tr in state.tracks.values() if tr['actor']['kind']=='mech' and t-tr['seen']<2.5 and
               (tr.get('engage',False) or t-state.hits.get(tr['actor']['id'],-100)<6)]
        if watch:
            nearest=min(watch,key=lambda a:math.dist(p[:2],a['pos'][:2]))
            yaw=math.atan2(nearest['pos'][1]-p[1],nearest['pos'][0]-p[0])
        elif t-state.npc_hurt<2.5 and state.npc_bearing is not None: yaw=state.npc_bearing
        elif t-state.last_hurt<2.5: yaw=state.hurt_bearing
        elif any(action['move']): yaw=math.atan2(action['move'][1],action['move'][0])+1.15*math.sin(t*1.3)
        else: yaw=me['aim'][0]+.35
        action['aim']=[yaw,0]
        for w in me['weapons']:
            if w and w['kind']=='gun' and w.get('reload',0)<=0 and w.get('ammo',0)<w['stats']['mag']*.6: action['reload']=True
    if target is None and foe is not None:
        distance=math.dist(p[:2],foe['pos'][:2])
        for i,w in enumerate(me['weapons'][:2]):
            if w and w['kind']=='laser' and w.get('cooldown',0)<=.05 and distance<w['stats']['range'] and w['charge']<w['stats']['charge']+w['stats']['hold_s']-.35: action['fire'][i]=True
