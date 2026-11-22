"""Coordinate the match policy across perception, movement, and combat."""
import math
import os
import random
import time

from .geometry import Arena, angle_diff, zone_goal, zone_deadline
from .combat import assess_combat, apply_weapon_control
from .loadout import choose_loadout, choose_objective, cube_upgrade_multiplier
from .movement import Movement
from .positional_field import PositionalField
from .corridor import FightCorridor
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
        self.npc_hurt=-100.; self.npc_bearing=None; self.npc_id=None
        self.hurt_bearing=0.
        self.last_aim=[0.,0.]
        self.corner_duel = os.getenv('BOT_CORNER_DUEL') == '1'
        self.supply_drops = os.getenv('BOT_SUPPLY_DROPS', '1') == '1'
        self.slot = hello['slot']
        self.laser_rush = os.getenv('BOT_LASER_RUSH') == '1'
        self.late_hide = os.getenv('BOT_LATE_HIDE') == '1'
        self.recovery_enabled=os.getenv('BOT_SQUAD_RECOVERY','legacy')=='cover'
        self.farming_policy=os.getenv('BOT_SQUAD_FARMING','legacy')
        self.squad_cover=os.getenv('BOT_SQUAD_POSITION','legacy')=='cover'
        self.nav_method=os.getenv('BOT_NAV_METHOD','spacing')
        self.safe_combat_cubes = os.getenv('BOT_SAFE_COMBAT_CUBES', '1') == '1'
        self.cube_upgrade_value = os.getenv('BOT_CUBE_UPGRADE_VALUE', '1') == '1'
        self.opening_scan = os.getenv('BOT_OPENING_SCAN') == '1'
        self.abandon_stalled_loot = os.getenv('BOT_ABANDON_STALLED_LOOT') == '1'
        self.loot_stall = None
        self.route_zone = os.getenv('BOT_ROUTE_ZONE') == '1'
        self.zone_estimate = None
        self.recovery_since=None; self.recovery_cooldown=-100.

    def act(self,obs):
        self.action_deadline=time.perf_counter()+.027
        self.cube_deadline=None
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
            self.zone_estimate = None
        self.update_world(obs); me=obs['self']; p=me['pos']; t=obs['t']; z=obs['zone']; hp=me['hp']/max(1,me['max_hp'])
        # This submission is explicitly for the cooperative practice field.
        practice = True
        hide = practice and self.late_hide and z['next_radius'] <= 140 and obs['alive'] > 3
        squad = practice and not hide
        late = (z['next_radius'] <= 70 and not hide) or obs['alive'] <= 3
        seen,target,foe,danger,finishing=self.assess_combat(obs,squad,late,hp)
        goal=zone_goal(z,*p[:2]); deadline=zone_deadline(self.hold,z,*p[:2],8); need=math.dist(p[:2],goal)*1.45/me['stats']['walk_speed']+4
        if self.route_zone and t+need+40 >= deadline:
            need=max(need,self.zone_route_time(p,goal,t,me['stats']['walk_speed']))
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
                    if self.safe_combat_cubes:
                        cubes = self.safe_cubes(obs, seen, cubes)
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
                    self.loot_stall = None
                    target=item; action['move']=self.movement.combat_move(obs,item,seen,squad,1,self.items)
                elif kind=='crates' and d<50:
                    self.loot_stall = None
                    target=dict(item,kind='crate',vel=[0,0,0])
                else:
                    action['move'] = self.movement.navigate(me, item['pos'], t)
                    if self.abandon_stalled_loot:
                        if d > 5 and not any(action['move']):
                            if self.loot_stall is None or self.loot_stall[0] != ident:
                                self.loot_stall = (ident, t)
                            elif t-self.loot_stall[1] >= 2:
                                self.bad[ident] = t+15
                                self.loot_id = None
                                self.loot_stall = None
                        else:
                            self.loot_stall = None
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
        self.movement.apply_evasion_and_recovery(obs,action,mode)
        apply_weapon_control(self,obs,action,target,foe,squad)
        if (self.opening_scan and t < 60 and target is None and foe is None
                and not danger and t-self.last_threat > 3
                and t-self.last_hurt > 3 and t-self.npc_hurt > 3):
            # One complete sweep approximately every eight seconds. Keep the
            # weapon controller in charge whenever a threat is actionable.
            action['aim'] = [angle_diff(t * math.tau / 8, 0), 0.]
        if (self.laser_rush and not self.ffa and mode in ('idle', 'loot', 'home') and target is None
                and t - self.last_threat > 3 and t - self.npc_hurt > 3
                and not any(w and w['kind'] == 'laser' for w in me['weapons'])
                and t % 8 < 2.5):
            action['aim'] = [angle_diff(me['aim'][0] + 1.3, 0), 0.]
        if mode=='recover': action['fire']=[False,False]
        if mode != 'loot': self.loot_stall = None
        action.update(choose_loadout(obs,self.cfg))
        self.mode=mode
        return action

    def update_world(self, obs):
        return update_perception(self, obs)

    def assess_combat(self, obs, squad, late, hp):
        return assess_combat(self, obs, squad, late, hp)

    def choose_objective(self, obs, hp, danger, squad):
        return choose_objective(self, obs, hp, danger, squad)

    def safe_cubes(self, obs, enemies, cubes):
        """Short, visible cube detours that do not add enemy firing lines."""
        me=obs['self']; p=me['pos']; now=obs['t']; result=[]
        if not cubes: return result
        if getattr(self, 'cube_deadline', None) is None:
            self.cube_deadline=min(self.action_deadline,time.perf_counter()+.005)
        deadline=self.cube_deadline
        # Above the stat cap, a single cube only warrants a combat detour if
        # it immediately yields an upgrade; size keeps increasing regardless.
        if (me['cubes'] >= self.cfg['cubes']['stat_cap'] and
                (not self.cube_upgrade_value or cube_upgrade_multiplier(self.cfg, me['cubes']) == 1)):
            return result
        threats=[]
        for enemy in enemies:
            if time.perf_counter() >= deadline: return []
            if enemy['kind'] != 'mech': continue
            tr=self.tracks.get(enemy['id'])
            if not tr or now-tr['seen'] > 1: continue
            scale=1+enemy.get('cubes',0)*self.cfg['cubes'].get('size_per_cube',.05)
            muzzle=(*enemy['pos'][:2],enemy['pos'][2]+self.cfg['mech']['muzzle_height']*scale)
            reach=max((self.cfg['weapons'][w].get('range',200) for w in enemy.get('weapons',[]) if w in self.cfg['weapons']),default=0)
            threats.append((muzzle,reach))
        def exposure(point):
            if time.perf_counter() >= deadline: return None
            chest=(*point,self.world.walk_at(*point)+me['stats']['height']*.6)
            count=0
            for muzzle,reach in threats:
                if time.perf_counter() >= deadline: return None
                if math.dist(point,muzzle[:2]) <= reach and self.world.shot_clear(muzzle,chest): count+=1
            return count if time.perf_counter() < deadline else None
        current=exposure(p[:2])
        if current is None: return result
        for cube in sorted(cubes,key=lambda item:math.dist(p[:2],item['pos'][:2]))[:6]:
            if time.perf_counter() >= deadline: break
            pos=cube['pos']; remembered=self.items.get(cube['id'])
            if not remembered or now-remembered[2] > 1 or abs(pos[2]-p[2]) > 3.6: continue
            if math.dist(p[:2],pos[:2]) > 25 or not self.world.line_walkable(p,pos): continue
            midpoint=((p[0]+pos[0])/2,(p[1]+pos[1])/2)
            middle=exposure(midpoint)
            if middle is None: break
            end=exposure(pos[:2])
            if end is None: break
            if max(middle,end) <= min(1,current): result.append(cube)
        return result

    def zone_route_time(self, pos, goal, now, speed):
        """Use completed ground routes only; fall back to the baseline estimate."""
        cached=self.zone_estimate
        if (cached is None or now-cached[0] >= 1 or math.dist(pos[:2],cached[1]) > 10
                or math.dist(goal[:2],cached[2]) > 5):
            remaining=max(0., min(.003, self.action_deadline-time.perf_counter()))
            if remaining <= 0: return 0.
            cells, complete=self.world.path(pos,goal,budget_s=remaining)
            length=0.
            if complete and cells:
                points=[pos[:2],*(self.world.cell_pos(c) for c in cells),goal[:2]]
                length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
            self.zone_estimate=(now,tuple(pos[:2]),tuple(goal[:2]),length)
        return self.zone_estimate[3]/max(1,speed)+4 if self.zone_estimate[3] else 0.
