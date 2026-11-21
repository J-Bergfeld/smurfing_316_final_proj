"""Mode selection, positioning and inventory decisions."""
import math
from .geometry import distance, angle_diff
from .positioning import Positioner
from .loadout import pickup_slot
from .movement import MovementSupport


class Strategy:
    def __init__(self, arena, combat, config, profile='practice', navigation=None):
        self.arena, self.combat, self.config, self.profile = arena, combat, config, profile
        self.navigation = navigation
        self.mode = 'hold'; self.until = None; self.positioner = Positioner(arena)
        self.route_until = 0; self.route_goal = None; self.path = []
        self.projectile_replan_at = 0
        self.zone_urgent = False
        self.target_id = None
        self.motion = MovementSupport()
        self.hop = None
        self.strafe_sign = 1
        self.strafe_until = 0
        self.retreat_until = 0

    def choose(self, world):
        obs = world.obs; me = obs['self']; now = obs['t']; enemies = world.enemies()
        first_decision = self.until is None
        if first_decision: self.until = now + 2.5
        def target_cost(track):
            actor = track['actor']
            return (distance(me['pos'],actor['pos'])*.5 + actor.get('hp',1400)*.09
                    + (0 if track['visible'] else 60) - (15 if actor['id']==self.target_id else 0))
        previous_target = self.target_id
        closest = min(enemies,key=target_cost,default=None)
        close_visible = [e for e in enemies if e['visible'] and distance(me['pos'],e['actor']['pos']) < 45]
        if close_visible:
            closest = min(close_visible,key=lambda e:distance(me['pos'],e['actor']['pos']))
        self.target_id = closest['actor']['id'] if closest else None
        d = distance(me['pos'],closest['actor']['pos']) if closest else 9999
        recent = now-world.last_damage < 2
        zone = obs['zone']; next_d = distance(me['pos'],zone['next_center'])
        urgency = not me.get('in_zone',True) or (next_d > zone['next_radius']-20 and now + max(0,next_d-zone['next_radius']+25)/max(1,me['stats'].get('walk_speed',11.7)) > zone['shrink_end']-4)
        edge_gap = zone['radius'] - distance(me['pos'],zone['center'])
        remaining = max(1,zone['shrink_end']-max(now,zone['shrink_start']))
        edge_speed = max(0,zone['radius']-zone['next_radius']+distance(zone['center'],zone['next_center']))/remaining
        if now >= zone['shrink_start']-14 and next_d > zone['next_radius']-20:
            urgency = urgency or edge_gap < 22 + min(14,max(0,now+14-zone['shrink_start']))*edge_speed
        if urgency and not self.zone_urgent: self.positioner.goal_until = 0
        self.zone_urgent = urgency
        # Target preference may favor a weak enemy farther away; do not let it
        # hide a different opponent who is an immediate danger.
        visible_threat = any(e['visible'] and distance(me['pos'],e['actor']['pos']) < 160 for e in enemies)
        nearby_count = sum(distance(me['pos'],e['actor']['pos'])<220 and e['confidence']>.3 for e in enemies)
        engaged = bool(closest and ((self.mode=='attack' and previous_target==closest['actor']['id']) or (recent and world.last_damage_by==closest['actor']['id'])))
        ratio = self.combat.estimate(me,closest['actor'],nearby_count,engaged=engaged) if closest else 0
        nearby = [e['actor'] for e in enemies if e['visible'] and distance(me['pos'],e['actor']['pos']) < 180]
        projectile_threat = world.projectile_risk(me['pos']) > .15
        # A second nearby combatant is enough to disengage an existing fight;
        # before engaging, require evidence that two enemies face each other.
        fighting = any(abs(angle_diff(a.get('aim',[0])[0], math.atan2(b['pos'][1]-a['pos'][1], b['pos'][0]-a['pos'][0]))) < .35 for a in nearby for b in nearby if a['id'] != b['id'] and distance(a['pos'],b['pos'])<200)
        ffa = self.profile == 'final' or (self.profile != 'practice' and world.field == 'ffa')
        third_party = ffa and (fighting or (self.mode == 'attack' and len(nearby)>=2))
        hp = me['hp']/max(1,me['max_hp'])
        incoming = sum(amount for _,amount in world.damage_log)/2.5
        close_count = sum(distance(me['pos'],e['pos']) < 160 for e in nearby)
        finish = bool(closest and closest['visible'] and d < 120 and closest['actor']['hp'] < .3*closest['actor'].get('max_hp',1400) and hp > .3 and close_count <= 2)
        losing = (close_count >= 3 and hp < .8) or (close_count >= 2 and hp < .55) or (hp < .35 and recent) or incoming > 110
        if losing and not finish: self.retreat_until = now + 1.5
        if urgency or third_party: proposed = 'flee'
        elif now < self.retreat_until and not finish: proposed = 'flee'
        elif recent or visible_threat:
            # Later circles require more willingness to commit than the opening.
            threshold = 1.35 if now < 100 and obs['alive'] > 9 else (1.0 if obs['alive'] > 4 else .7)
            if not ffa and closest and closest['visible'] and d < 175 and hp > .4 and close_count <= 1:
                threshold *= .65
            proposed = 'attack' if (finish or ratio > threshold) and not third_party else 'flee'
        elif me['hp'] < me['max_hp']*.9 and me.get('in_zone',True) and not projectile_threat: proposed = 'recover'
        elif world.loot or obs.get('drops') or any(t['visible'] and t['actor']['kind']=='npc' and distance(me['pos'],t['actor']['pos'])<110 for t in world.tracks.values()): proposed = 'loot'
        else: proposed = 'hold'
        if projectile_threat and proposed != 'attack': proposed = 'flee'
        emergency = urgency or recent or projectile_threat or losing or bool(visible_threat and self.mode not in ('attack','flee')) or third_party
        if proposed != self.mode and (first_decision or now >= self.until or emergency):
            self.mode = proposed; self.until = now + (1.5 if proposed in ('attack','flee') else 2.5); self.positioner.goal_until = 0
        elif projectile_threat and now >= self.projectile_replan_at:
            self.positioner.goal_until = 0
            self.projectile_replan_at = now + .3
        return self.mode, closest, urgency

    def goal_for(self, world, mode, enemy, urgent):
        return self.positioner.goal_for(world, mode, enemy, urgent)

    def movement(self, world, goal, urgent, mode=None, enemy=None):
        obs=world.obs; me=obs['self']; p=me['pos']; now=obs['t']; arena=self.arena
        stuck = self.motion.observe(me,goal,now)
        recovery = self.motion.recover(me,now)
        if recovery is not None:
            if self.motion.recovery['phase']=='back':
                recovery['move']=self.motion.steer(arena,me,recovery['move'],obs['zone'])
            self.motion.record(recovery['move'])
            self.path=[]
            return recovery
        while self.path and distance(p,self.path[0])<6 and abs(p[2]-self.path[0][2])<3:
            self.path.pop(0)
        changed = self.route_goal is None or distance(goal,self.route_goal)>12 or abs(goal[2]-self.route_goal[2])>3
        # Hold the active climb path while airborne; a partial replan can
        # otherwise redirect the bot halfway through a roof transition.
        climbing = self.hop is not None and not me['grounded'] and not changed and bool(self.path)
        if not climbing and (changed or stuck or not self.path or now >= self.route_until):
            path = self.navigation.route(p,goal,me['energy']) if self.navigation else None
            if not path:
                # Keep the fallback search bounded near complex polygons.
                fallback = arena.route(p,goal,me.get('stats',{}).get('radius',2.5),me.get('stats',{}).get('height',9),.005)
                path = [fallback or goal]
            self.path=path; self.route_until=now+1.5
            self.route_goal=goal[:]
        waypoint=self.path[0]
        elevated = waypoint[2]-p[2]>3 and distance(p,waypoint)<40
        dx,dy=waypoint[0]-p[0],waypoint[1]-p[1]; d=math.hypot(dx,dy)
        move=[dx/d,dy/d] if d>2 else [0,0]
        guns=[w for w in me.get('weapons',[]) if w and w['kind']=='gun']
        reloading=any(w.get('reload',0)>0 or w.get('ammo',1)<=w.get('stats',{}).get('mag',12)*.25 for w in guns)
        if mode == 'attack' and enemy and enemy['visible'] and me['grounded'] and not reloading and now-world.laser_shot_at>1.65:
            target=enemy['actor']['pos']; ex,ey=target[0]-p[0],target[1]-p[1]; ed=math.hypot(ex,ey)
            if ed>1:
                if now>=self.strafe_until:
                    self.strafe_sign *= -1
                    self.strafe_until=now+1.2+((obs['tick']*7919+me['id'])%13)/10
                sx,sy=-ey/ed*self.strafe_sign,ex/ed*self.strafe_sign
                weight=1 if distance(p,goal)<8 else .4
                mx,my=move[0]+sx*weight,move[1]+sy*weight; length=math.hypot(mx,my)
                if length>.01: move=[mx/length,my/length]
        jump=False; boost=False
        if self.hop and (now-self.hop['t']>6 or (me['grounded'] and now-self.hop['t']>.4)):
            self.hop=None
        if elevated and me['grounded'] and self.hop is None:
            required=2.4*max(0,waypoint[2]-p[2]-2)+8
            if me['energy']>=required:
                self.hop={'t':now,'height':waypoint[2]}; jump=True
            elif not urgent and not (enemy and enemy['visible']):
                move=[0,0]  # let energy recover at the base of a planned hop
        if self.hop and not me['grounded']:
            boost=me['energy']>8 and p[2]<self.hop['height']+1
        elif me['grounded']:
            threatened = world.obs['t']-world.last_damage<3 or bool(enemy and enemy['visible'] and distance(p,enemy['actor']['pos'])<140)
            boost=bool(d>12 and ((urgent and me['energy']>20) or (mode=='flee' and threatened and me['energy']>45)))
            if not jump:
                move=self.motion.steer(arena,me,move,obs['zone'])
        self.motion.record(move)
        return {'move':move,'jump':jump,'boost':boost}

    def inventory(self, world):
        obs=world.obs; me=obs['self']; out={}; offer=obs.get('offer')
        priorities={'plating':100,'armor':95,'nanites':84,'laser_damage':90,'laser_charge':88,'gun_damage':78,'gun_rate':70,'lightning_efficiency':66,'lightning_range':65,'servos':60,'gun_mag':50,'gun_velocity':48,'gyros':45,'reactor':38,'capacitor':36,'sensors':20,'jets':15}
        if offer: out['pick']=max(range(len(offer['choices'])),key=lambda i:priorities.get(offer['choices'][i]['id'],3))
        for item in sorted(obs.get('pickups',[]),key=lambda i: distance(me['pos'],i['pos'])):
            if distance(me['pos'],item['pos']) > self.config.get('loot',{}).get('pickup_radius',4) or abs(me['pos'][2]-item['pos'][2])>4: continue
            want, slot = pickup_slot(item,world)
            if want:
                out['take']=item['id']
                if slot is not None: out['drop']=slot
                break
        return out
