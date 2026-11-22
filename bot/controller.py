"""Coordinate the match policy across perception, movement, and combat."""
import math
import os
import random
import time

from .geometry import Arena, angle_diff, zone_goal, zone_deadline
from .combat import Combat, assess_combat, assess_pressure, apply_weapon_control, pressure_advantage, pressure_dps
from .loadout import choose_loadout, choose_objective, pressure_pickup
from .movement import Movement
from .positional_field import PositionalField
from .corridor import FightCorridor
from .tactical_planner import TacticalPlanner
from .world import update_perception
class Controller:
    def __init__(self,hello):
        self.cfg=hello['config']; self.world=Arena(hello['map']['dir']); self.rng=random.Random(hello.get('seed') or hello.get('slot',0)+1)
        self.body_size = (self.cfg['mech']['radius'], self.cfg['mech']['height'])
        self.world.set_body_size(*self.body_size)
        self.tracks={}; self.items={}; self.hits={}; self.attacker_memory={}; self.kills=set(); self.initial=None; self.unexplained=0; self.ffa=False
        self.last_hurt=-100.; self.last_threat=-100.; self.lose_at=-100.; self.retreat=False; self.hold=None; self.phase=None
        self.target_id=None; self.target_at=-100.; self.loot_id=None; self.loot_since=0; self.bad={}
        self.movement=Movement(self.world,self.cfg,self.rng)
        self.field = PositionalField(self.world) if os.getenv('BOT_POSITIONAL_FIELD') == '1' else None
        self.corridor = FightCorridor(self.field) if self.field and os.getenv('BOT_FIGHT_CORRIDOR') == '1' else None
        self.tactical = TacticalPlanner(self.world) if os.getenv('BOT_TACTICAL_PLANNER') == '1' else None
        self.npc_hurt=-100.; self.npc_bearing=None; self.npc_id=None
        self.hurt_bearing=0.
        self.last_aim=[0.,0.]
        self.corner_duel = os.getenv('BOT_CORNER_DUEL') == '1'
        self.supply_drops = os.getenv('BOT_SUPPLY_DROPS', '1') == '1'
        self.slot = hello['slot']
        self.laser_rush = os.getenv('BOT_LASER_RUSH') == '1'
        self.lightning_close = os.getenv('BOT_LIGHTNING_CLOSE') == '1'
        self.pressure_policy = os.getenv('BOT_PRESSURE_POLICY') == '1'
        self.decision_policy = os.getenv('BOT_DECISION_POLICY', 'classic')
        self.exchange_model = os.getenv('BOT_PRESSURE_EXCHANGE') == '1'
        self.recent_damage = []
        self.unseen_hit_at = -100.
        self.unseen_hit_bearing = 0.
        self.unseen_hit_distance = 115.
        self.unseen_hit_id = None
        self.unseen_hit_position = None
        self.pressure_aim_times = {}
        self.pressure_engage_times = {}
        self.retreat_started = -100.
        self.lobby_alive = None
        self.lobby_kills = 0
        self.lobby_unknown_deaths = 0
        self.credit_hit_at = -100.
        self.credit_target = None
        self.credit_absorbed_at = -100.
        self.late_hide = os.getenv('BOT_LATE_HIDE') == '1'
        self.recovery_enabled=os.getenv('BOT_SQUAD_RECOVERY','legacy')=='cover'
        self.farming_policy=os.getenv('BOT_SQUAD_FARMING','legacy')
        self.squad_cover=os.getenv('BOT_SQUAD_POSITION','legacy')=='cover'
        self.nav_method=os.getenv('BOT_NAV_METHOD','spacing')
        self.recovery_since=None; self.recovery_cooldown=-100.
        self.seen_cells={}; self.roam_cell=None; self.roam_at=-100.
        self.pressure_zone_key=None; self.pressure_zone_goal=None; self.pressure_zone_at=-100.

    def mark_exploration(self, obs):
        """Remember recently visible 32 m exploration cells."""
        if obs['tick'] % 6: return
        world=self.world; p=obs['self']['pos']; t=obs['t']; aim=obs['self']['aim'][0]
        bounds=world.bounds; xmin=bounds['minX']; ymin=bounds['minY']
        nx=math.ceil((bounds['maxX']-xmin)/32)+1; ny=math.ceil((bounds['maxY']-ymin)/32)+1
        i0=max(0, int((p[0]-150-xmin)/32)); i1=min(nx-1,int((p[0]+150-xmin)/32))
        j0=max(0, int((p[1]-150-ymin)/32)); j1=min(ny-1,int((p[1]+150-ymin)/32))
        eye=[p[0],p[1],p[2]+obs['self']['stats'].get('eye_height',8)]
        half=math.radians(self.cfg['vision'].get('fov_deg',120))*.5
        deadline=getattr(self,'action_deadline',time.perf_counter()+.02)-.006
        for j in range(j0,j1+1):
            for i in range(i0,i1+1):
                if time.perf_counter()>=deadline: return
                key=(i,j)
                if self.seen_cells.get(key,-1e6)>t-2: continue
                x=xmin+(i+.5)*32; y=ymin+(j+.5)*32
                d=math.hypot(x-p[0],y-p[1])
                if d>150 or (d>40 and abs(angle_diff(math.atan2(y-p[1],x-p[0]),aim))>half): continue
                if d<20 or world.shot_clear(eye,[x,y,world.ground(x,y)+2]): self.seen_cells[key]=t

    def pressure_roam(self, obs, hp):
        """Look for unseen ground while healthy and still gathering cubes."""
        me=obs['self']; p=me['pos']; t=obs['t']; z=obs['zone']; brawl=self.ffa or t<6
        want=40 if obs['alive']<=2 else 10 if brawl else 26
        if hp<.7 or me['cubes']>=want: return None
        world=self.world; bounds=world.bounds; xmin=bounds['minX']; ymin=bounds['minY']
        grid=world.baked
        if not grid: return None
        here=world.nearest_free(world.cell(*p[:2]))
        if here is None: return None
        comp=grid['component'][here[1]*grid['nx']+here[0]]
        if self.roam_cell and t-self.roam_at<12 and self.seen_cells.get(self.roam_cell,-1e6)<t-20:
            i,j=self.roam_cell; return (xmin+(i+.5)*32,ymin+(j+.5)*32)
        nx=math.ceil((bounds['maxX']-xmin)/32)+1; ny=math.ceil((bounds['maxY']-ymin)/32)+1
        choices=[]
        for j in range(ny):
            y=ymin+(j+.5)*32
            for i in range(nx):
                age=t-self.seen_cells.get((i,j),-1e6)
                if age<45: continue
                x=xmin+(i+.5)*32
                dn=math.dist((x,y),z['next_center'])
                if dn>z['next_radius']-15 or not world.inside(x,y): continue
                cell=world.cell(x,y); idx=cell[1]*grid['nx']+cell[0]
                if grid['component'][idx]!=comp or not world.free_cell(cell): continue
                score=math.hypot(x-p[0],y-p[1])-min(age,300)*.15+dn*.15
                choices.append((score,i,j,cell))
        if not choices: return None
        _,i,j,cell=min(choices); self.roam_cell=(i,j); self.roam_at=t
        return world.cell_pos(cell)

    def pressure_zone(self, obs):
        """Estimate the shrinking edge and a reachable point in the next circle."""
        z=obs['zone']; me=obs['self']; x,y=me['pos'][:2]; t=obs['t']
        center=z['center']; nxt=z['next_center']; radius=z['next_radius']
        out_cur=math.hypot(x-center[0],y-center[1])-z['radius']
        out_next=math.hypot(x-nxt[0],y-nxt[1])-radius
        start=max(t,z['shrink_start']); passing=math.inf
        if out_cur>0: passing=0.
        elif out_next>0 and z['shrink_end']<=start: passing=0.
        elif out_next>0:
            for i in range(1,51):
                f=i/50
                cx=center[0]+(nxt[0]-center[0])*f; cy=center[1]+(nxt[1]-center[1])*f
                r=z['radius']+(radius-z['radius'])*f
                if math.hypot(x-cx,y-cy)>r:
                    passing=start-t+f*(z['shrink_end']-start); break
        need=(out_next+8)/max(1,me['stats']['walk_speed'])*1.35+4 if out_next>0 else 0.
        urgent=(out_cur>-2 or passing<9 or
                (out_next>0 and (z['shrink_end']-t<need or passing-need<3)))
        if not urgent: return zone_goal(z,x,y),False
        grid=self.world.baked; current=self.world.nearest_free(self.world.cell(x,y)) if grid else None
        comp=grid['component'][current[1]*grid['nx']+current[0]] if current else None
        key=(nxt[0],nxt[1],radius,comp)
        if self.pressure_zone_goal is not None and key==self.pressure_zone_key and t-self.pressure_zone_at<1:
            return self.pressure_zone_goal,True
        angle=math.atan2(y-nxt[1],x-nxt[0]); margin=min(5,radius*.3)
        best=None; fallback=None
        for frac in (.6,.45,.75,.3,.15,.9,0.):
            rr=max(0.,min(radius*frac,radius-10))
            for offset in (0.,.4,-.4,.8,-.8,1.4,-1.4,2.2,-2.2,math.pi):
                if time.perf_counter()>=self.action_deadline-.005: break
                px=nxt[0]+math.cos(angle+offset)*rr; py=nxt[1]+math.sin(angle+offset)*rr
                if not self.world.inside(px,py): continue
                cell=self.world.cell(px,py)
                if not self.world.free_cell(cell): continue
                px,py=self.world.cell_pos(cell)
                if radius>12 and math.hypot(px-nxt[0],py-nxt[1])>radius-margin: continue
                if grid and comp is not None and grid['component'][cell[1]*grid['nx']+cell[0]]!=comp:
                    if fallback is None: fallback=(px,py)
                    continue
                best=(px,py); break
            if best is not None or time.perf_counter()>=self.action_deadline-.005: break
        self.pressure_zone_key=key; self.pressure_zone_at=t
        self.pressure_zone_goal=best or fallback or tuple(nxt)
        return self.pressure_zone_goal,True

    def pressure_fight_cube(self, obs, hp):
        """Pick up nearby cube piles while continuing to engage a target."""
        me=obs['self']; pos=me['pos']; now=obs['t']; brawl=self.ffa or now<6
        limit=40 if obs['alive']<=2 else 10 if brawl else 26
        if me['cubes']>=limit+6: return None
        cubes=[item for kind,item,seen in self.items.values() if kind=='cubes' and now-seen<20]
        held_lightning=any(w and w['kind']=='lightning' for w in me['weapons'])
        best=None; best_value=0.
        grid=self.world.baked
        here=self.world.nearest_free(self.world.cell(*pos[:2])) if grid else None
        component=grid['component'][here[1]*grid['nx']+here[0]] if here is not None else None
        for cube in cubes:
            d=math.dist(pos[:2],cube['pos'][:2])
            count=sum(math.dist(other['pos'][:2],cube['pos'][:2])<7 for other in cubes)
            if d>(110 if count>=2 else 40) or (d>30 and hp<.3): continue
            if not held_lightning and any(tr['actor']['kind']=='mech' and 'lightning' in tr['actor'].get('weapons',[])
                                          and now-tr['seen']<4 and math.dist(cube['pos'][:2],tr['actor']['pos'][:2])<53
                                          for tr in self.tracks.values()): continue
            if now+d/max(1,me['stats']['walk_speed'])+1>zone_deadline(self.hold,obs['zone'],*cube['pos'][:2],3): continue
            cell=self.world.nearest_free(self.world.cell(*cube['pos'][:2])) if grid else None
            if grid and (cell is None or component is None or grid['component'][cell[1]*grid['nx']+cell[0]]!=component): continue
            value=count/(d+12)
            if value>best_value: best,best_value=cube,value
        return best

    def pressure_fight_weapon(self, obs):
        me=obs['self']; pos=me['pos']; now=obs['t']
        values={'gun':2.,'lightning':2.1,'laser':2.4,'mortar':2.6}
        best=None; best_value=0.
        for ident,(kind,item,seen) in self.items.items():
            if kind!='pickups' or now-seen>20 or self.bad.get(ident,0)>now: continue
            d=math.dist(pos[:2],item['pos'][:2])
            wanted,slot=pressure_pickup(item['kind'],me['weapons'])
            if not wanted or d>32: continue
            value=values[item['kind']]
            if slot is not None:
                value-=values.get(me['weapons'][slot]['kind'],0)
                if value<1: continue
            if any(tr['actor']['kind']=='mech' and now-tr['seen']<5 and
                   math.dist(tr['actor']['pos'][:2],item['pos'][:2])<max(30,d*.8)
                   for tr in self.tracks.values()): continue
            if now+d/max(1,me['stats']['walk_speed'])+2>zone_deadline(self.hold,obs['zone'],*item['pos'][:2],5): continue
            score=value/(d+15)
            if score>best_value: best,best_value=item,score
        return best

    def act(self,obs):
        self.action_deadline=time.perf_counter()+.027
        self.movement.action_deadline=self.action_deadline
        stats = obs['self']['stats']
        size = (stats['radius'], stats['height'])
        if size != self.body_size:
            self.world.set_body_size(*size)
            self.body_size = size
            self.movement.path = []
            self.movement.unstuck_until = 0.
            self.movement.cover = None
            self.movement.home_xy = None
        self.update_world(obs); me=obs['self']; p=me['pos']; t=obs['t']; z=obs['zone']; hp=me['hp']/max(1,me['max_hp'])
        if self.decision_policy == 'pressure':
            return self.act_pressure(obs)
        # This submission is explicitly for the cooperative practice field.
        practice = True
        hide = practice and self.late_hide and z['next_radius'] <= 140 and obs['alive'] > 3
        squad = practice and not hide
        late = (z['next_radius'] <= 70 and not hide) or obs['alive'] <= 3
        seen,target,foe,danger,finishing=self.assess_combat(obs,squad,late,hp)
        goal=zone_goal(z,*p[:2]); deadline=zone_deadline(self.hold,z,*p[:2],8); need=math.dist(p[:2],goal)*1.45/me['stats']['walk_speed']+4
        zone_margin=14 if squad and self.nav_method=='early_zone' else 3
        urgent=not me['in_zone'] or t+need+zone_margin>=deadline
        action={'tick':obs['tick'],'move':[0.,0.],'fire':[False,False],'boost':False,'jump':False}; mode='idle'
        shell=self.movement.avoid_shells(obs)
        field_eligible = self.field is not None and squad and not urgent and me['grounded']
        if self.field is not None:
            self.field.hear(obs)
            if not field_eligible or shell or t < self.movement.unstuck_until:
                self.field.key = None
        if self.corridor is not None and (not field_eligible or shell or t < self.movement.unstuck_until):
            self.corridor.clear()
        recovery_move=None
        if self.recovery_enabled and squad:
            if self.recovery_since is not None and (hp>=.8 or urgent or t-self.recovery_since>=10):
                self.recovery_since=None; self.recovery_cooldown=t+5
            close_threat=any(math.dist(p[:2],a['pos'][:2])<35 for a in seen)
            wants_recovery=(self.recovery_since is not None or
                            (self.retreat and hp<.65 and t>=self.recovery_cooldown))
            if wants_recovery and not urgent and not finishing and not close_threat:
                recovery_move=self.movement.seek_cover(obs,seen)
                if recovery_move is None and self.recovery_since is not None and not seen and self.movement.cover is not None:
                    recovery_move=self.movement.navigate(me,self.movement.cover,t)
                if recovery_move is not None and self.recovery_since is None: self.recovery_since=t
            if wants_recovery and recovery_move is None and self.recovery_since is not None:
                self.recovery_since=None; self.recovery_cooldown=t+5
        elif self.recovery_since is not None:
            self.recovery_since=None
        if t<self.movement.unstuck_until:
            action['move']=list(self.movement.unstuck_dir); mode='unstuck'
        elif shell:
            action['move']=shell; action['boost']=me['energy']>15; mode='dodge'
        elif urgent and math.dist(p[:2],goal)>2:
            action['move']=self.movement.navigate(me,goal,t); action['boost']=me['energy']>5; mode='zone'
        elif recovery_move is not None:
            action['move']=recovery_move; action['boost']=me['energy']>10 and any(recovery_move); mode='recover'
        elif (self.tactical is not None and me['grounded'] and target is not None
              and (step := self.tactical.choose(self, obs, target)) is not None):
            action['move'] = step; mode = 'tactical'
        elif field_eligible and (step := self.field.choose(self, obs, target)) is not None:
            action['move'] = step
            mode = 'positional-field'
        elif (self.corner_duel and squad and not urgent and me['grounded']
              and (duel := self.movement.isolate_hunter(obs, self.attacker_memory)) is not None):
            action['move'], target = duel
            foe = target
            mode = 'corner-duel'
        elif foe and not (self.retreat and not finishing and not late):
            distance=math.dist(p[:2],foe['pos'][:2]); gun=next((w for w in me['weapons'] if w and w['kind']=='gun'),None); laser_weapon=next((w for w in me['weapons'] if w and w['kind']=='laser'),None)
            ready=bool(gun and gun['ammo']>0 and gun['reload']<=.25 and distance<=gun['stats']['range']-10)
            hot=bool(laser_weapon and laser_weapon['charge']>=laser_weapon['stats']['charge']-.3 and distance<=laser_weapon['stats']['range']-5)
            if hot or (squad and not self.squad_cover and any(w and w['kind'] in ('laser','lightning') for w in me['weapons'])): ready=True
            if squad and self.squad_cover:
                lightning=next((w for w in me['weapons'] if w and w['kind']=='lightning'),None)
                if lightning and me['energy']>=lightning['stats']['energy'] and distance<lightning['stats']['range']-1.5: ready=True
            want_los=1 if ready else -1
            if (not squad or self.squad_cover) and not hot and any(a.get('charging') and abs(angle_diff(a['aim'][0],math.atan2(p[1]-a['pos'][1],p[0]-a['pos'][0])))<.3 for a in seen): want_los=-1.6
            action['move']=self.movement.combat_move(obs,foe,seen,squad,want_los,self.items); mode='fight'
            if squad and not (self.farming_policy in ('selective','cubes') and danger):
                radius=70 if hp>.5 else 70*.57
                cubes=[item for kind,item,_ in self.items.values() if kind=='cubes' and math.dist(p[:2],item['pos'][:2])<radius]
                if cubes:
                    cube=min(cubes,key=lambda item:math.dist(p[:2],item['pos'][:2])); action['move']=self.movement.navigate(me,cube['pos'],t); mode='fight:cube'
        elif self.retreat:
            covered=self.movement.seek_cover(obs,seen)
            if covered is not None:
                action['move']=covered; action['boost']=me['energy']>10 and any(covered); mode='cover'
            elif target:
                action['move']=self.movement.combat_move(obs,target,seen,squad,1,self.items); mode='cornered'
            else:
                action['move']=self.movement.navigate(me,goal,t); mode='flee'
        elif not target and t-self.last_hurt<2.5 and not late and not squad:
            ghost={'id':-1,'pos':[p[0]+math.cos(self.hurt_bearing)*80,p[1]+math.sin(self.hurt_bearing)*80,p[2]],'cubes':0}
            covered=self.movement.seek_cover(obs,[ghost,*seen])
            if covered is not None:
                action['move']=covered; action['boost']=me['energy']>30 and any(covered); mode='cover'
        elif t+need+(28 if squad and self.nav_method=='early_zone' else 14)>=deadline and math.dist(p[:2],goal)>2:
            action['move']=self.movement.navigate(me,goal,t); mode='zone'
        else:
            best=self.choose_objective(obs,hp,danger,squad)
            if best:
                mode='loot'
                ident,kind,item,d,when=best
                if ident!=self.loot_id: self.loot_id=ident; self.loot_since=t
                elif t-self.loot_since>30: self.bad[ident]=t+60; self.loot_id=None
                if kind == 'drops':
                    mode = 'capture'
                    if d > item['radius'] * .65:
                        action['move'] = self.movement.navigate(me, item['pos'], t)
                elif kind=='npc' and t-when<1 and self.tracks[ident]['los'] and d<75:
                    target=item; action['move']=self.movement.combat_move(obs,item,seen,squad,1,self.items)
                elif kind=='crates' and d<50: target=dict(item,kind='crate',vel=[0,0,0])
                else:
                    action['move'] = self.movement.navigate(me, item['pos'], t)
                    if self.laser_rush and kind == 'pickups' and item['kind'] == 'laser' and not self.ffa:
                        action['boost'] = not danger and d > 12 and me['energy'] > 60
            else:
                self.loot_id=None
            if not best and math.dist(p[:2],goal)>3 and (squad or z['next_radius']<=30):
                action['move']=self.movement.navigate(me,goal,t); mode='zone-walk'
            elif not best and not squad and (home:=self.movement.select_shelter(obs,self.tracks)) is not None and math.dist(p[:2],home)>3:
                action['move']=self.movement.navigate(me,home,t); mode='home'
                if not danger and t-self.last_hurt>6:
                    factor=min(1.,4.6/me['stats']['walk_speed'])
                    action['move']=[v*factor for v in action['move']]
        if (field_eligible and self.corridor is not None and not shell and not self.retreat
                and not finishing and mode in ('fight', 'positional-field', 'corner-duel')):
            step = self.corridor.choose(self, obs, target, action['move'])
            if step is not None:
                action['move'] = step
                mode = 'fight-corridor'
        if (self.pressure_policy and target and target.get('kind') == 'mech'
                and not urgent and not shell and not self.retreat and hp > .6
                and mode in ('fight', 'positional-field', 'corner-duel')):
            # Keep a favorable isolated fight active instead of holding position.
            nearby = sum(math.dist(p[:2], actor['pos'][:2]) < 120 for actor in seen)
            distance = math.dist(p[:2], target['pos'][:2])
            if nearby <= 1 and distance > 35:
                action['move'] = self.movement.navigate(me, target['pos'], t)
        self.movement.apply_evasion_and_recovery(obs,action,mode)
        if (self.pressure_policy and mode in ('cover', 'flee') and me['grounded']
                and me['energy'] > 45 and any(action['move'])):
            action['boost'] = True
        if (self.lightning_close and mode == 'fight' and target and not self.retreat
                and me['grounded'] and me['energy'] > 55):
            lightning = next((w for w in me['weapons'] if w and w['kind'] == 'lightning'), None)
            dx, dy = target['pos'][0]-p[0], target['pos'][1]-p[1]
            distance = math.hypot(dx, dy)
            # Spend energy only when the chosen movement actually closes the gap.
            if (lightning and distance > lightning['stats']['range'] + 10
                    and action['move'][0]*dx + action['move'][1]*dy > .4*distance):
                action['boost'] = True
        apply_weapon_control(self,obs,action,target,foe,squad)
        if (self.laser_rush and not self.ffa and mode in ('idle', 'loot', 'home') and target is None
                and t - self.last_threat > 3 and t - self.npc_hurt > 3
                and not any(w and w['kind'] == 'laser' for w in me['weapons'])
                and t % 8 < 2.5):
            action['aim'] = [angle_diff(me['aim'][0] + 1.3, 0), 0.]
        if mode=='recover': action['fire']=[False,False]
        action.update(choose_loadout(obs,self.cfg))
        self.mode=mode
        return action

    def update_world(self, obs):
        return update_perception(self, obs)

    def act_pressure(self, obs):
        """Coordinate combat, recovery and objectives using persistent threat state."""
        self.mark_exploration(obs)
        me, now, zone = obs['self'], obs['t'], obs['zone']
        pos = me['pos']
        hp = me['hp'] / max(1, me['max_hp'])
        for event in obs.get('events', []):
            if event['type'] == 'hit' and isinstance(event.get('target'), int) and event['target'] < 100:
                self.credit_hit_at, self.credit_target = now, event['target']
        if self.lobby_alive is None:
            self.lobby_alive = obs['alive']
        deaths = max(0, self.lobby_alive - obs['alive'])
        credited = max(0, len(self.kills) - self.lobby_kills)
        if deaths and not credited and now-self.credit_hit_at < 6:
            recent = self.tracks.get(self.credit_target)
            still_alive = bool(recent and now-recent['seen'] < .11 and recent['actor'].get('hp', 1) > 0)
            if not still_alive:
                credited = 1
                self.credit_absorbed_at = now
        self.lobby_unknown_deaths += max(0, deaths - credited)
        self.lobby_alive = min(self.lobby_alive, obs['alive'])
        self.lobby_kills = len(self.kills)
        if ((self.lobby_unknown_deaths >= 1 and now < 35)
                or (self.lobby_unknown_deaths >= 2 and now < 110)
                or self.lobby_unknown_deaths >= 3):
            self.ffa = True
        self.recent_damage.extend((now, e.get('amount', 0)) for e in obs.get('events', [])
                                  if e['type'] == 'damaged' and e.get('weapon') not in ('npc', 'zone'))
        for event in obs.get('events', []):
            attacker=event.get('by'); bearing=event.get('bearing')
            if (event['type']!='damaged' or event.get('weapon') in ('npc','zone') or
                    not isinstance(attacker,int) or attacker>=100 or bearing is None): continue
            track=self.tracks.get(attacker)
            if track is None or now-track['seen']>2:
                self.unseen_hit_at=now; self.unseen_hit_bearing=bearing
                self.unseen_hit_distance={'laser':150.,'lightning':35.}.get(event.get('weapon'),115.)
                self.unseen_hit_id=attacker
                self.unseen_hit_position=[pos[0]+math.cos(bearing)*self.unseen_hit_distance,
                                          pos[1]+math.sin(bearing)*self.unseen_hit_distance,pos[2]]
        self.recent_damage = [(t, amount) for t, amount in self.recent_damage if now-t < 3]
        damage_rate = sum(amount for _, amount in self.recent_damage) / 3
        survival = me['hp'] / max(1, damage_rate)
        known, engaged, selected = assess_pressure(self, obs)
        actors = [item['actor'] for item in known]
        threat = selected['actor'] if selected else None
        # Fight and pursuit ranges measure the actual separation, including
        # elevation. A mech above or below us may be outside pursuit range
        # even when its ground projection is close enough.
        distance = math.dist(pos, threat['pos']) if threat else math.inf
        # Listed mechs are visible to the game engine. Trust that observation
        # for a close attacker when our approximate map reports an obstruction;
        # weapon line-of-fire checks still apply before releasing a shot.
        can_see = bool(selected and (selected['track']['los'] or
                       (selected['current'] and selected['active'] and distance < 40)))
        danger = bool(engaged or damage_rate > 0)
        cautious = self.ffa or now < 6 or now-self.credit_absorbed_at < 25
        advantage = (pressure_advantage(self.cfg, me, threat, cautious) if self.exchange_model
                     else Combat(self.cfg).estimate(me, threat, max(1, len(engaged)), True)) if threat else 0
        overall = (advantage if engaged else 10.) if self.exchange_model else advantage
        if self.exchange_model and len(engaged) >= 2 and threat:
            own_kinds={w['kind'] for w in me['weapons'] if w}
            own_dps=max(1.,pressure_dps(self.cfg,own_kinds,me.get('cubes',0),distance,True,cautious,me['energy']>15))
            incoming=sum(pressure_dps(self.cfg,set(item['actor'].get('weapons',[])) or {'gun'},
                                     item['actor'].get('cubes',0),item['distance'],False,cautious)
                         for item in engaged)
            needed=sum(max(20,item['actor'].get('hp',1400))/own_dps for item in engaged)
            armor=max(0.,min(.95,me['stats'].get('armor',0)))
            overall=(me['hp']/max(1.,incoming*(1-armor)))/max(.1,needed)
        recent_hit = threat is not None and now-self.hits.get(threat['id'], -100) < 4
        provoked = bool(threat and (recent_hit or distance < 85
                         or ('laser' in threat.get('weapons', []) and threat.get('charging'))))
        have_laser = any(w and w['kind'] == 'laser' for w in me['weapons'])
        laser_edge = bool(threat and have_laser and 'laser' not in threat.get('weapons', []))
        attack = bool(threat and can_see and (
            obs['alive'] <= 2 or
            (selected['active'] and (not cautious or provoked)) or
            (hp > .6 and distance < 130 and advantage >= (1.3 if cautious else .7)
             and (not cautious or laser_edge or advantage >= 3))))
        if self.retreat:
            if self.exchange_model:
                safe_to_fight = threat and selected['current'] and selected['active'] and len(engaged) <= 1 and hp > .3 and overall > .95
                trapped = threat and can_see and selected['active'] and distance < 45 and len(engaged) <= 1 and now-self.retreat_started > 2 and overall > .35
                recovered = (hp >= .65 and (not danger or overall > .95)) or (hp >= .55 and not danger)
            else:
                safe_to_fight = threat and can_see and len(engaged) <= 1 and hp > .3 and overall > .95
                trapped = threat and can_see and distance < 45 and len(engaged) <= 1 and now-self.retreat_started > 2
                recovered = hp >= .55 and not danger
            if recovered or safe_to_fight or trapped:
                self.retreat = False
        elif danger:
            single_lost = len(engaged) <= 1 and threat and overall < .5 and distance > 30 and survival < 25
            overwhelmed = len(engaged) >= 2 and ((hp < .8 and survival < 10) or (hp < .2 and survival < 20))
            unknown_hit = any(item.get('phantom') for item in engaged) and damage_rate > 0 and (hp < .6 or survival < 15)
            if single_lost or overwhelmed or unknown_hit:
                self.retreat = True
                self.retreat_started = now
                self.movement.cover = None
        if threat and can_see and threat.get('hp', 1400) < 180 and hp > .12:
            self.retreat = False

        goal, urgent = self.pressure_zone(obs)
        action = {'tick': obs['tick'], 'move': [0., 0.], 'fire': [False, False], 'boost': False, 'jump': False}
        shell = self.movement.avoid_shells(obs)
        target = None
        mode = 'idle'
        slip = None
        if (cautious and attack and not self.retreat and not urgent and not shell and now>=self.movement.unstuck_until and threat and
                selected['active'] and distance >= 85 and advantage < .65 and
                threat.get('hp', 1400) >= 180 and
                ('laser' in threat.get('weapons', []) or damage_rate > 60 or hp < .5 or len(engaged) >= 2)):
            slip = self.movement.seek_cover(obs, actors)
        if now < self.movement.unstuck_until:
            action['move'] = list(self.movement.unstuck_dir); mode = 'unstuck'
        elif shell:
            action['move'] = shell; action['boost'] = me['energy'] > 15; mode = 'dodge'
        elif urgent and math.dist(pos[:2], goal) > 2:
            action['move'] = self.movement.navigate(me, goal, now)
            action['boost'] = me['energy'] > 20; mode = 'zone'
        elif self.retreat:
            covered = self.movement.seek_cover(obs, actors)
            if covered is not None:
                action['move'] = covered
                action['boost'] = any(covered) and damage_rate > 0 and me['energy'] > 20
                mode = 'retreat' if any(covered) else 'heal'
            elif threat:
                dx, dy = pos[0]-threat['pos'][0], pos[1]-threat['pos'][1]
                length = max(1, math.hypot(dx, dy))
                action['move'] = self.movement.navigate(me, (pos[0]+30*dx/length, pos[1]+30*dy/length), now)
                action['boost'] = me['energy'] > 30; mode = 'retreat'
            else:
                mode = 'heal'
            if can_see:
                target = threat
        elif slip is not None:
            action['move'] = slip
            mode = 'slip'
        elif attack:
            target = threat
            weapon = self.pressure_fight_weapon(obs)
            cube = self.pressure_fight_cube(obs, hp)
            lightning = next((w for w in me['weapons'] if w and w['kind'] == 'lightning'), None)
            nearest = min((item for item in engaged if item['current']), key=lambda item:item['distance'], default=None)
            kite = bool(len(engaged)>=2 and nearest and nearest['distance']<=210
                        and (not cautious or have_laser) and (have_laser or not lightning or me['energy']<=40))
            if weapon:
                action['move'] = self.movement.navigate(me, weapon['pos'], now); mode = 'fight-weapon'
            elif cube:
                action['move'] = self.movement.navigate(me, cube['pos'], now); mode = 'fight-cube'
            elif kite:
                action['move'] = self.movement.pressure_kite(obs, nearest['actor'])
                action['boost'] = nearest['distance'] < 70 and me['energy'] > 45; mode = 'kite'
            else:
                action['move'] = self.movement.combat_move(obs, threat, actors, True, 1, self.items, desired_override=30)
                if lightning and distance > lightning['stats']['range']+10 and me['energy'] > 55:
                    action['boost'] = True
                mode = 'fight'
        else:
            objective = self.choose_objective(obs, hp, danger, True)
            if objective:
                ident, kind, item, dist, seen_at = objective
                if ident != self.loot_id:
                    self.loot_id, self.loot_since = ident, now
                elif now-self.loot_since > 30:
                    self.bad[ident] = now+60; self.loot_id = None
                if kind == 'drops':
                    if dist > 3:
                        action['move'] = self.movement.navigate(me, item['pos'], now)
                elif kind == 'npc':
                    visible = now == seen_at and self.tracks[ident]['los']
                    if visible and dist < 110:
                        target = item
                    if dist > 60 or not visible:
                        action['move'] = self.movement.navigate(me, item['pos'], now)
                    else:
                        action['move'] = self.movement.combat_move(obs, item, actors, True, 1, self.items, desired_override=60)
                elif kind == 'crates' and dist < 70:
                    target = dict(item, kind='crate', vel=[0, 0, 0])
                    if dist > 9:
                        action['move'] = self.movement.navigate(me, item['pos'], now)
                else:
                    action['move'] = self.movement.navigate(me, item['pos'], now)
                    if (kind == 'pickups' and item['kind'] == 'laser' and not have_laser
                            and dist > 25 and me['energy'] > 40):
                        action['boost'] = True
                mode = 'loot'
            else:
                roof_wanted = (self.ffa and obs['alive']>2 and zone['next_radius']>=60
                               and (have_laser or me['cubes']>=6 or now>=60))
                nearby = any(item['current'] and item['track']['los'] and item['distance']<150 for item in known)
                roof = self.movement.pressure_roof_step(obs, not nearby and now-self.last_hurt>=3) if roof_wanted else None
                if roof is not None:
                    mode = roof.pop('mode')
                    action.update(roof)
                elif (roam := self.pressure_roam(obs,hp)) is not None:
                    action['move'] = self.movement.navigate(me, roam, now); mode = 'roam'
                elif math.dist(pos[:2], goal) > 3:
                    action['move'] = self.movement.navigate(me, goal, now); mode = 'zone-walk'
        # The movement objective and the firing target are independent: keep
        # shooting an active attacker while moving to safety or another goal.
        if threat and selected['active'] and can_see and (not cautious or provoked):
            target = threat
        if mode != 'roof-climb':
            self.movement.apply_evasion_and_recovery(obs, action, mode)
        apply_weapon_control(self, obs, action, target, threat if can_see else None, True)
        if any(item.get('phantom') for item in engaged) and now-self.unseen_hit_at<1.5 and (not selected or not selected['active'] or not can_see):
            action['aim']=[self.unseen_hit_bearing,0.]
            action['fire']=[bool(w and w['kind']=='laser' and w.get('charge',0)>0) for w in me['weapons'][:2]]
        action.update(choose_loadout(obs, self.cfg, pressure=True, state=self))
        self.mode = mode
        return action

    def assess_combat(self, obs, squad, late, hp):
        return assess_combat(self, obs, squad, late, hp)

    def choose_objective(self, obs, hp, danger, squad):
        return choose_objective(self, obs, hp, danger, squad)
