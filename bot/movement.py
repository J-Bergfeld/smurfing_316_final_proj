"""Local wall steering and staged recovery for the navigation controller."""
import math
import os
import time
from collections import deque
from .geometry import distance, angle_diff


class MovementSupport:
    def __init__(self):
        self.history=[]
        self.last_move=[0,0]
        self.recovery=None
        self.stalls=0

    def record(self, move):
        self.last_move=list(move)

    def observe(self, me, goal, now):
        p=me['pos']
        self.history.append((now,p[0],p[1],math.hypot(*self.last_move)))
        self.history=[h for h in self.history if now-h[0] <= 1.4]
        if self.recovery or not me['grounded'] or distance(p,goal)<4 or len(self.history)<5:
            return False
        old=self.history[0]; elapsed=now-old[0]
        commanded=sum(h[3]>.5 for h in self.history)
        expected=elapsed*me.get('stats',{}).get('walk_speed',11.7)*.6
        if elapsed>=1 and commanded>=5 and math.hypot(p[0]-old[1],p[1]-old[2])<expected*.2:
            direction=self.last_move; mag=math.hypot(*direction)
            if mag<.1: return False
            dx,dy=direction[0]/mag,direction[1]/mag
            self.stalls+=1; side=1 if self.stalls%2 else -1
            self.recovery={'phase':'back','until':now+.6,'dir':[-.6*dx-.8*side*dy,-.6*dy+.8*side*dx],
                           'forward':[dx,dy],'z':p[2]}
            self.history=[]
            return True
        return False

    def recover(self, me, now):
        rec=self.recovery
        if not rec: return None
        if now>=rec['until']:
            if rec['phase']=='back' and me['energy']>35:
                rec.update(phase='jet',until=now+1.4,z=me['pos'][2],jumped=False)
            else:
                self.recovery=None
                return None
        if rec['phase']=='back': return {'move':rec['dir'][:], 'jump':False,'boost':False}
        jump=me['grounded'] and not rec['jumped']
        if jump: rec['jumped']=True
        if rec['jumped'] and me['grounded'] and not jump:
            self.recovery=None
            return None
        return {'move':rec['forward'][:], 'jump':jump,
                'boost':bool(not me['grounded'] and me['energy']>8 and me['pos'][2]<rec['z']+7)}

    def steer(self, arena, me, move, zone, allow_drop=False):
        mag=math.hypot(*move)
        if mag<.01 or not me['grounded']: return move
        p=me['pos']; stats=me.get('stats',{}); radius=stats.get('radius',2.5); height=stats.get('height',9)
        def safe(x,y):
            if distance((x,y),zone['center'])>max(zone['radius']-2,distance(p,zone['center'])): return False
            supported = arena.supported(x,y,p[2],radius,height) if hasattr(arena,'supported') else arena.walkable(x,y,radius,height)
            if supported: return True
            # Dropping from a roof is intentional when a route descends.
            # Check the body at its current altitude; the engine then handles
            # the fall, rather than requiring roof support beyond the edge.
            if allow_drop and hasattr(arena,'blocked') and hasattr(arena,'height') and arena.height(x,y) < p[2]-2:
                return not any(arena.blocked(x+dx,y+dy,p[2]+.1,height) for dx,dy in ((0,0),(radius,0),(-radius,0),(0,radius),(0,-radius)))
            return False
        # If the current footing is off our coarse model, leave the direction
        # intact so that recovery/jet movement can get back onto the graph.
        if not safe(p[0],p[1]): return move
        heading=math.atan2(move[1],move[0])
        for degrees in (0,20,-20,40,-40,60,-60,80,-80,100,-100):
            a=heading+math.radians(degrees); dx,dy=math.cos(a),math.sin(a)
            if all(safe(p[0]+dx*d,p[1]+dy*d) for d in (2.5,5)):
                return [dx*mag,dy*mag]
        return [0,0]


class Movement:
    def __init__(self, world, config, rng):
        self.world=world; self.cfg=config; self.rng=rng
        self.nav_method=os.getenv('BOT_NAV_METHOD','spacing')
        self.path=[]; self.path_goal=None; self.path_at=-100.
        self.strafe=1; self.strafe_until=0
        self.cover=None; self.cover_at=-100.
        self.home_xy=None; self.home_at=-100.
        self.stuck_since=0.; self.unstuck_until=0.; self.unstuck_dir=(0.,0.)
        self.action_deadline=0.

    def apply_evasion_and_recovery(self, obs, action, mode):
        """Blend evasive movement and update stuck recovery."""
        me=obs['self']; t=obs['t']
        dodge,laser=self.avoid_projectiles(obs)
        if mode!='unstuck' and any(dodge):
            move=action['move']; mx,my=move[0]*.4+dodge[0]*.9,move[1]*.4+dodge[1]*.9; length=math.hypot(mx,my)
            action['move']=[mx/max(1,length),my/max(1,length)]
            if laser and me['energy']>25: action['boost']=True
        if any(action['move']) and math.hypot(*me['vel'][:2])<1.2 and me['grounded']:
            if self.stuck_since<0: self.stuck_since=t
            elif t-self.stuck_since>.7:
                angle=self.rng.random()*math.tau; self.unstuck_dir=(math.cos(angle),math.sin(angle)); self.unstuck_until=t+.5
                self.stuck_since=-1.; self.path=[]; action['jump']=True
        else: self.stuck_since=-1.

    def select_shelter(self, obs, tracks):
        z=obs['zone']; t=obs['t']; p=obs['self']['pos']; center=z['next_center']; radius=z['next_radius']
        outside=self.home_xy is None or math.dist(self.home_xy,center)>radius*.8
        def cost(x,y):
            crowd=sum(max(0,80-math.dist(tr['actor']['pos'][:2],(x,y)))/80
                      for tr in tracks.values() if t-tr['seen']<20)
            crowd+=sum(max(0,60-math.dist(drop['pos'][:2],(x,y)))/60 for drop in obs.get('drops',[]))
            return 120*self.world.exposure(x,y)+.25*math.hypot(x-p[0],y-p[1])+40*crowd+10*math.dist((x,y),center)/max(30,radius)
        if outside or t-self.home_at>12:
            self.home_at=t; best=None; best_cost=math.inf
            for _ in range(40):
                a=self.rng.random()*math.tau; r=math.sqrt(self.rng.random())*radius*.7
                x=center[0]+math.cos(a)*r; y=center[1]+math.sin(a)*r
                if not self.world.inside(x,y) or not self.world.reachable(x,y): continue
                if time.perf_counter()>=self.action_deadline: continue
                value=cost(x,y)
                if value<best_cost: best=(x,y); best_cost=value
            if best is not None and (outside or best_cost<cost(*self.home_xy)-15): self.home_xy=best
        return self.home_xy

    def navigate(self,me,goal,t):
        p=me['pos']; dx,dy=goal[0]-p[0],goal[1]-p[1]; d=math.hypot(dx,dy)
        if d<.8: return [0.,0.]
        unit=lambda point:[(point[0]-p[0])/max(1e-9,math.dist(p[:2],point[:2])),(point[1]-p[1])/max(1e-9,math.dist(p[:2],point[:2]))]
        if d<45 and self.world.line_walkable(p,goal): return unit(goal)
        if not self.path or self.path_goal is None or math.dist(goal[:2],self.path_goal)>5 or t-self.path_at>2.5:
            remaining=max(0.,min(.025,self.action_deadline-time.perf_counter()))
            self.path,_=self.world.path(p,goal,budget_s=remaining); self.path_goal=goal[:2]; self.path_at=t
        if not self.path: return unit(goal)
        positions=[self.world.cell_pos(c) for c in self.path[:10]]
        index=min(range(len(positions)),key=lambda i:math.dist(positions[i],p[:2]))
        self.path=self.path[index:]
        for cell in reversed(self.path[:15]):
            point=self.world.cell_pos(cell)
            if self.world.line_walkable(p,point): return unit(point)
        return unit(self.world.cell_pos(self.path[min(1,len(self.path)-1)]))

    def combat_move(self,obs,target,seen,squad,want_los=1,items=None):
        if items is None: items={}
        me=obs['self']; p=me['pos']; pos=target['pos']; d=math.dist(p[:2],pos[:2]); weapons={w['kind'] for w in me['weapons'] if w}
        desired=58 if target['kind']=='npc' else (28 if 'lightning' in weapons and me['energy']>12 else (120 if 'laser' in weapons and squad else 85))
        if 'lightning' not in weapons:
            if 'lightning' in target.get('weapons',[]): desired=max(desired,64)
            if 'mortar' in target.get('weapons',[]): desired=max(desired,80)
        if obs['t']>=self.strafe_until:
            if self.rng.random()<.6: self.strafe=-self.strafe
            self.strafe_until=obs['t']+.3+self.rng.random()*.7
        sx,sy=-(pos[1]-p[1])/max(d,1e-9)*self.strafe,(pos[0]-p[0])/max(d,1e-9)*self.strafe
        height=self.cfg['npc']['height'] if target['kind']=='npc' else self.cfg['mech']['height']*(1+target.get('cubes',0)*self.cfg['cubes'].get('size_per_cube',.05))
        center=(pos[0],pos[1],pos[2]+height*.5); z=obs['zone']; best=(-math.inf,[0.,0.])
        cubes=[item for kind,item,_ in items.values() if kind=='cubes' and math.dist(p[:2],item['pos'][:2])<40 and abs(item['pos'][2]-p[2])<4]
        cube=min(cubes,key=lambda item:math.dist(p[:2],item['pos'][:2])) if cubes else None
        blocked_side=False; deadline=min(self.action_deadline,time.perf_counter()+.015)
        for i in range(-1,32 if not squad else 16):
            if time.perf_counter()>=deadline: break
            a=(i%16)*math.pi/8; dx,dy=(math.cos(a),math.sin(a)) if i>=0 else (0.,0.); r=6*(1+i//16) if i>=0 else 0; x,y=p[0]+r*dx,p[1]+r*dy
            if i>=0 and (not self.world.line_walkable(p,(x,y)) or not self.world.free_cell(self.world.cell(x,y))):
                if i<16 and dx*sx+dy*sy>.9: blocked_side=True
                continue
            ground=self.world.walk_at(x,y); score=-1.1*abs(math.hypot(pos[0]-x,pos[1]-y)-desired)-r*.4
            los=self.world.shot_clear((x,y,ground+me['stats']['muzzle_height']),center)
            if los: score+=45*want_los
            if want_los>0: score+=9*(dx*sx+dy*sy)
            if i<0: score+=-8+(14 if want_los<0 and not los else 0)
            if not squad and 0<=i<16 and los==(want_los>0):
                for q in range(0,16,2):
                    qx,qy=x+math.cos(q*math.pi/8)*7,y+math.sin(q*math.pi/8)*7
                    if self.world.free_cell(self.world.cell(qx,qy)) and self.world.shot_clear((qx,qy,self.world.walk_at(qx,qy)+me['stats']['muzzle_height']),center)!=los:
                        score+=8; break
            cur=math.hypot(x-z['center'][0],y-z['center'][1])-z['radius']; nxt=math.hypot(x-z['next_center'][0],y-z['next_center'][1])-z['next_radius']
            if cur>-5: score-=150+5*(cur+5)
            if nxt>-5: score-=max(.1,min(1,1-(z['shrink_start']-obs['t'])/25))*(25+.8*(nxt+5))
            if cube: score+=1.5*(math.dist(p[:2],cube['pos'][:2])-math.hypot(cube['pos'][0]-x,cube['pos'][1]-y))
            if self.world.baked:
                cell=self.world.cell(x,y); clearance=self.world.baked['clearance'][cell[1]*self.world.baked['nx']+cell[0]]
                if clearance<4: score-=(4-clearance)*2.5
            for actor in seen:
                enemy_distance=math.hypot(actor['pos'][0]-x,actor['pos'][1]-y)
                if squad and self.nav_method=='spacing':
                    safe=70 if 'lightning' in actor.get('weapons',[]) else 55
                    score-=max(0,safe-enemy_distance)*2
                if actor['id']==target['id'] or enemy_distance>170: continue
                if self.world.shot_clear((*actor['pos'][:2],actor['pos'][2]+8),(x,y,ground+me['stats']['height']*.6)):
                    score-=75 if squad and self.nav_method=='cover' else 30
            if score>best[0]: best=(score,[dx,dy])
        if blocked_side: self.strafe=-self.strafe; self.strafe_until=obs['t']+.5
        return best[1]

    def avoid_projectiles(self,obs):
        me=obs['self']; p=me['pos']; cx,cy,cz=p[0],p[1],p[2]+me['stats']['height']*.56
        reach=me['stats']['radius']+1.1; dx=dy=0.; laser=False
        for shot in obs.get('projectiles',[]):
            if shot['kind']=='mortar': continue
            v=shot['vel']; v2=sum(x*x for x in v)
            if v2<1: continue
            t=((cx-shot['pos'][0])*v[0]+(cy-shot['pos'][1])*v[1]+(cz-shot['pos'][2])*v[2])/v2
            if not 0<t<=.7: continue
            mx,my=shot['pos'][0]+v[0]*t-cx,shot['pos'][1]+v[1]*t-cy
            if math.hypot(mx,my)>=reach: continue
            vh=math.hypot(v[0],v[1])
            if vh<1: continue
            px,py=-v[1]/vh,v[0]/vh
            if px*mx+py*my>0: px,py=-px,-py
            dx+=px; dy+=py
        for actor in obs.get('mechs',[]):
            if actor['kind']!='mech' or not actor.get('charging'): continue
            bearing=math.atan2(cy-actor['pos'][1],cx-actor['pos'][0])
            if abs(angle_diff(actor['aim'][0],bearing))>.15: continue
            dx+=math.cos(bearing+math.pi/2*self.strafe)*1.5; dy+=math.sin(bearing+math.pi/2*self.strafe)*1.5; laser=True
        length=math.hypot(dx,dy)
        return ([dx/length,dy/length],laser) if length>.01 else ([0.,0.],False)

    def avoid_shells(self,obs):
        me=obs['self']; p=me['pos']; cfg=self.cfg['weapons']['mortar']; radius=cfg['splash_radius']+me['stats']['radius']+2
        for shot in obs.get('projectiles',[]):
            if shot['kind']!='mortar': continue
            x,y,z=shot['pos']; vx,vy,vz=shot['vel']
            for step in range(80):
                x+=vx*.05; y+=vy*.05; z+=vz*.05; vz-=cfg.get('gravity',22)*.05
                if not self.world.solid(x,y,z): continue
                d=math.hypot(x-p[0],y-p[1])
                if d<radius and step*.05<2.5:
                    dx,dy=(p[0]-x,p[1]-y) if d>=.5 else (-vy,vx); length=math.hypot(dx,dy)
                    if length<1e-9: break
                    dx,dy=dx/length,dy/length
                    for rot in (0,.7,-.7,1.4,-1.4):
                        xdir=dx*math.cos(rot)-dy*math.sin(rot); ydir=dx*math.sin(rot)+dy*math.cos(rot)
                        if self.world.line_walkable(p,(p[0]+xdir*6,p[1]+ydir*6)): return [xdir,ydir]
                break
        return None

    def seek_cover(self,obs,seen):
        me=obs['self']; p=me['pos']; now=obs['t']; zone=obs['zone']
        threats=sorted((a for a in seen if math.dist(p[:2],a['pos'][:2])<230),key=lambda a:math.dist(p[:2],a['pos'][:2]))[:4]
        if not threats: return None
        if self.cover is not None and now-self.cover_at<.4:
            return self.navigate(me,self.cover,now) if math.dist(self.cover,p[:2])>=1.5 else [0.,0.]
        self.cover_at=now
        def penalty(x,y):
            cur=math.hypot(x-zone['center'][0],y-zone['center'][1])-zone['radius']
            nxt=math.hypot(x-zone['next_center'][0],y-zone['next_center'][1])-zone['next_radius']
            value=150+5*(cur+5) if cur>-5 else 0
            if nxt>-5: value+=max(.1,min(1,1-(zone['shrink_start']-now)/25))*(25+.8*(nxt+5))
            return value
        def hidden(x,y):
            ground=self.world.walk_at(x,y); height=me['stats']['height']
            for actor in threats:
                ap=actor['pos']; scale=1+actor.get('cubes',0)*self.cfg['cubes'].get('size_per_cube',.05)
                eye=(ap[0],ap[1],ap[2]+self.cfg['mech']['eye_height']*scale)
                if self.world.shot_clear(eye,(x,y,ground+height)) or self.world.shot_clear(eye,(x,y,ground+height*.5)): return False
            return True
        if hidden(*p[:2]) and penalty(*p[:2])==0:
            self.cover=tuple(p[:2]); return [0.,0.]
        start=self.world.nearest_free(self.world.cell(*p[:2]))
        if start is None: self.cover=None; return None
        queue=deque([(start,0)]); visited={start}; best=None; best_score=math.inf; checked=0
        deadline=min(self.action_deadline,time.perf_counter()+.030)
        while queue and checked<350 and time.perf_counter()<deadline:
            cell,steps=queue.popleft()
            if steps>50 or (best is not None and steps*2>best_score+30): break
            if sum(cell)%2==0 and steps>0:
                x,y=self.world.cell_pos(cell); checked+=1
                if hidden(x,y):
                    nearest=min(math.hypot(a['pos'][0]-x,a['pos'][1]-y) for a in threats)
                    value=steps*2+penalty(x,y)-min(nearest,80)*.25
                    if value<best_score: best,best_score=(x,y),value
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=(cell[0]+dx,cell[1]+dy)
                if nxt in visited or not self.world.free_cell(nxt): continue
                if self.world._surface[nxt]-self.world._surface[cell]>(3.1 if dx and dy else 2.2): continue
                if dx and dy and (not self.world.free_cell((cell[0]+dx,cell[1])) or not self.world.free_cell((cell[0],cell[1]+dy))): continue
                visited.add(nxt); queue.append((nxt,steps+1))
        self.cover=best
        return self.navigate(me,best,now) if best is not None else None
