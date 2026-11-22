"""Local wall steering and staged recovery for the navigation controller."""
import math
import os
import time
from collections import deque
from .geometry import distance, angle_diff


_ROOF_GRAPH_CACHE = {}
_STEER_DIRECTIONS = tuple((math.cos(i*math.pi/4), math.sin(i*math.pi/4)) for i in range(8))


def build_roof_access_graph(world):
    """Build reachable takeoff/landing pairs on the baked two-metre grid."""
    if not world.baked:
        return []
    bounds=world.bounds
    signature=(tuple(bounds[k] for k in ('minX','minY','maxX','maxY')), hash(world.heights),
               tuple((p.get('kind'),p.get('top'),tuple(p.get('ring',()))) for p in world.prisms))
    if signature in _ROOF_GRAPH_CACHE:
        return _ROOF_GRAPH_CACHE[signature]
    grid=world.baked; nx=grid['nx']; ny=grid['ny']; graph=[]
    solid_cells={}
    def solid_cell(cell):
        if cell not in solid_cells:
            x,y=world.cell_pos(cell); ground=world.ground(x,y)
            solid_cells[cell]=any(p['base']<=ground+.3 and p['top']>ground+1.5 for p in world.solids(x,y))
        return solid_cells[cell]
    for ident,prism in enumerate(world.prisms):
        if prism['kind']!='building': continue
        x0,y0,x1,y1=prism['box']
        lo=world.cell(x0,y0); hi=world.cell(x1,y1)
        cells=set()
        for j in range(lo[1],min(ny,hi[1]+1)):
            for i in range(lo[0],min(nx,hi[0]+1)):
                x,y=world.cell_pos((i,j))
                if any(p is prism for p in world.solids(x,y)):
                    cells.add((i,j))
        if len(cells)*4<250: continue
        boundary=[]; depths={}
        for cell in cells:
            i,j=cell
            if any((i+di,j+dj) not in cells for di,dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))):
                boundary.append(cell); depths[cell]=1
        queue=deque(boundary)
        while queue:
            i,j=queue.popleft(); next_depth=depths[(i,j)]+1
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(i+di,j+dj)
                if n in cells and n not in depths:
                    depths[n]=next_depth; queue.append(n)
        if not depths: continue
        inner=max(depths,key=depths.get)
        if (depths[inner]-.5)*2<5: continue
        inner_pos=world.cell_pos(inner); top=prism['top']
        if not world.standable(*inner_pos,top,2.5,9): continue
        access=[]
        for i,j in boundary:
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                outside=(i+di,j+dj); edge=(i-di*2,j-dj*2)
                if outside in cells or edge not in cells: continue
                # A neighbouring solid roof is a wall, not open air from
                # which this roof can be climbed.
                if not (0<=outside[0]<nx and 0<=outside[1]<ny): continue
                if solid_cell(outside): continue
                for step in (2,3):
                    ground=(i+di*step,j+dj*step)
                    if not (0<=ground[0]<nx and 0<=ground[1]<ny): break
                    if solid_cell(ground): break
                    if world.free_cell(ground):
                        gp=world.cell_pos(ground); ep=world.cell_pos(edge)
                        climb=top-world.walk_at(*gp)
                        if 6<=climb<=40: access.append((ground,gp,ep,climb))
                        break
        if access:
            graph.append({'id':ident,'top':top,'inside':inner_pos,'cells':cells,
                          'depths':depths,'access':access})
    _ROOF_GRAPH_CACHE[signature]=graph
    return graph


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
        self.pressure_strafe_enabled=os.getenv('BOT_PRESSURE_STRAFE','1') != '0'
        self.pressure_steer_enabled=os.getenv('BOT_PRESSURE_STEER','0') == '1'
        self.pressure_route_steer=os.getenv('BOT_PRESSURE_ROUTE_STEER','0') == '1'
        self.duel_hunters = frozenset()
        self.duel_until = -1.
        self.cornered_boost = os.getenv('BOT_CORNERED_BOOST') == '1'
        self.path=[]; self.path_goal=None; self.path_at=-100.
        self.strafe=1; self.strafe_until=0
        self.pressure_last_move=(0.,0.)
        self.cover=None; self.cover_at=-100.
        self.home_xy=None; self.home_at=-100.
        self.roof_plan=None; self.roof_bans={}; self.roof_last_search=-100.
        self.roof_graph = (build_roof_access_graph(world)
                           if os.getenv('BOT_PRESSURE_ROOF_GRAPH') == '1' else None)
        self.roof_graph_by_id = {roof['id']:roof for roof in self.roof_graph} if self.roof_graph else {}
        self.stuck_since=0.; self.unstuck_until=0.; self.unstuck_dir=(0.,0.)
        self.action_deadline=0.

    def pressure_roof_step(self, obs, allow_climb=True):
        """Approach, ascend and settle on a nearby roof, or return None.

        A plan is retained between decisions; callers should invoke it only
        when the pressure policy wants to hold a roof. Combat and urgent zone
        travel take precedence, and callers can pass allow_climb=False while
        an opponent watches the approach.
        """
        me=obs['self']; pos=me['pos']; now=obs['t']; zone=obs['zone']
        world=self.world; radius=me['stats'].get('radius',2.5)
        plan=self.roof_plan
        # Accept a roof reached by a detour or a landing even if it is not the
        # one selected before the climb.  The ground approach is no longer a
        # useful goal once our feet are already on a suitable roof.
        if me.get('grounded',True):
            for prism in world.solids(*pos[:2]):
                if prism['kind']!='building' or abs(pos[2]-prism['top'])>=1.6:
                    continue
                ident=next(i for i, candidate in enumerate(world.prisms) if candidate is prism)
                x0,y0,x1,y1=prism['box']; graph_roof=self.roof_graph_by_id.get(ident)
                center=graph_roof['inside'] if graph_roof else ((x0+x1)*.5,(y0+y1)*.5)
                if (prism['top']-world.ground(*center)<4 or
                        math.dist(center,zone['next_center'])>zone['next_radius']-8 or
                        not any(s is prism for s in world.solids(*center)) or
                        not world.standable(*center,prism['top'],radius,me['stats'].get('height',9))):
                    continue
                if plan is None or plan['id']!=ident:
                    self.roof_plan=plan={'id':ident,'inside':center,'top':prism['top'],
                                         'started':now,'last_step':now,'state':'on'}
                break
        if plan and now-plan['last_step']>1.5:
            plan['started']=now
        if plan and (math.dist(plan['inside'],zone['next_center'])>zone['next_radius']-8
                     or now-plan['started']>60):
            self.roof_bans[plan['id']]=now+60; self.roof_plan=plan=None
        previous = None
        if self.roof_graph is not None and plan and plan['state']=='approach' and now-self.roof_last_search>3:
            previous=plan
            plan=None
        if plan is None:
            if now-self.roof_last_search<3: return None
            self.roof_last_search=now
            grid=world.baked
            here=world.nearest_free(world.cell(*pos[:2])) if grid else None
            component=grid['component'][here[1]*grid['nx']+here[0]] if here else None
            best=None; best_distance=math.inf; best_score=math.inf
            if self.roof_graph is not None:
                drain=me['stats'].get('jet_drain',15) or 15
                limit=min(40,(me.get('max_energy',100)-28)/drain*8.9)
                for roof in self.roof_graph:
                    if self.roof_bans.get(roof['id'],0)>now: continue
                    if math.dist(roof['inside'],zone['next_center'])>=zone['next_radius']-8: continue
                    if math.dist(roof['inside'],pos[:2])>260+math.sqrt(len(roof['cells'])*4): continue
                    preference=40 if previous and roof['id']==previous['id'] else 0
                    for cell,ground,edge,climb in roof['access']:
                        if climb>limit or (grid and component is not None and grid['component'][cell[1]*grid['nx']+cell[0]]!=component): continue
                        # Skip points that cannot beat the best even on one axis.
                        if abs(ground[0]-pos[0])>=best_score+preference or abs(ground[1]-pos[1])>=best_score+preference: continue
                        d=math.dist(pos[:2],ground)
                        score=d-preference
                        if score>=best_score: continue
                        if not world.free_cell(cell): continue
                        best_score=score
                        best_distance=d
                        best={'id':roof['id'],'ground':ground,'edge':edge,'inside':roof['inside'],
                              'top':roof['top'],'climb':climb,'started':now,'last_step':now,'state':'approach'}
                if best is None: return None
                self.roof_plan=plan=(previous if previous and previous['id']==best['id'] else best)
            else:
                for ident,prism in enumerate(world.prisms):
                    if prism['kind']!='building' or self.roof_bans.get(ident,0)>now: continue
                    x0,y0,x1,y1=prism['box']; cx=(x0+x1)*.5; cy=(y0+y1)*.5
                    if min(x1-x0,y1-y0)<2*radius+5: continue
                    if math.hypot(cx-pos[0],cy-pos[1])>260: continue
                    if math.dist((cx,cy),zone['next_center'])>zone['next_radius']-8: continue
                    if not any(s is prism for s in world.solids(cx,cy)): continue
                    top=prism['top']; climb=top-world.ground(cx,cy)
                    if not world.standable(cx,cy,top,radius,me['stats'].get('height',9)): continue
                    drain=me['stats'].get('jet_drain',15) or 15
                    if climb<9 or climb>min(40,(me.get('max_energy',100)-28)/drain*8.9): continue
                    # Fall back to four bounding-box probes without the graph.
                    margin=radius+1.3
                    sx=max(x0+margin,min(x1-margin,pos[0])); sy=max(y0+margin,min(y1-margin,pos[1]))
                    pairs=[((x0-margin,sy),(x0+margin,sy)),((x1+margin,sy),(x1-margin,sy)),
                           ((sx,y0-margin),(sx,y0+margin)),((sx,y1+margin),(sx,y1-margin))]
                    for ground,edge in pairs:
                        d=math.dist(pos[:2],ground)
                        if d>=best_distance or not world.inside(*ground): continue
                        if not any(s is prism for s in world.solids(*edge)): continue
                        cell=world.cell(*ground)
                        if not world.free_cell(cell): continue
                        if grid and grid['component'][cell[1]*grid['nx']+cell[0]]!=component: continue
                        best_distance=d
                        best={'id':ident,'ground':ground,'edge':edge,'inside':(cx,cy),
                              'top':top,'climb':climb,'started':now,'last_step':now,'state':'approach'}
                if best is None: return None
                self.roof_plan=plan=best
        plan['last_step']=now
        top=plan['top']; over=any(s is world.prisms[plan['id']] for s in world.solids(*pos[:2]))
        if me.get('grounded',True) and over and abs(pos[2]-top)<1.6:
            plan['state']='on'
        if plan['state']=='on':
            if not over or abs(pos[2]-top)>2:
                self.roof_plan=None; return None
            goal=plan['inside']
            roof=self.roof_graph_by_id.get(plan['id'])
            if roof:
                current=world.cell(*pos[:2]); depths=roof['depths']; dist=math.dist(pos[:2],goal)
                if current in depths:
                    steps=int(dist/2)+1
                    clear=all(depths.get(world.cell(pos[0]+(goal[0]-pos[0])*i/steps,
                                                    pos[1]+(goal[1]-pos[1])*i/steps),0)>=2
                              for i in range(1,steps+1))
                    if not clear:
                        choices=[(depths.get((current[0]+di,current[1]+dj),0),(current[0]+di,current[1]+dj))
                                 for di in range(-3,4) for dj in range(-3,4)]
                        depth,cell=max(choices)
                        goal=world.cell_pos(cell) if depth>depths[current] else tuple(pos[:2])
            return {'move':self.navigate(me,goal,now) if math.dist(pos[:2],goal)>2 else [0.,0.],
                    'jump':False,'boost':False,'mode':'roof'}
        ground=plan['ground']; distance_to_ground=math.dist(pos[:2],ground)
        if plan['state']=='approach':
            if distance_to_ground>=1.6:
                return {'move':self.navigate(me,ground,now),'jump':False,'boost':False,'mode':'roof-approach'}
            need=plan['climb']/8.9*(me['stats'].get('jet_drain',15) or 15)+24
            if not allow_climb:
                plan.setdefault('wait_started',now)
                if now-plan['wait_started']>4:
                    self.roof_bans[plan['id']]=now+20; self.roof_plan=None; return None
                return {'move':[0.,0.],'jump':False,'boost':False,'mode':'roof-wait'}
            plan.pop('wait_started',None)
            if me['energy']<need:
                return {'move':[0.,0.],'jump':False,'boost':False,'mode':'roof-wait'}
            plan['state']='climb'; plan['started']=now
        if now-plan['started']>plan['climb']/8+5 or (me['energy']<2 and pos[2]<top-.5 and not me['grounded']):
            self.roof_bans[plan['id']]=now+90; self.roof_plan=None; return None
        dx,dy=plan['edge'][0]-pos[0],plan['edge'][1]-pos[1]; length=math.hypot(dx,dy)
        move=[dx/length,dy/length] if length>1e-6 else [0.,0.]
        jump=bool(me['grounded'] and pos[2]<top-1)
        boost=bool(not me['grounded'] and (pos[2]<top+.7 or (not over and me['vel'][2]<.5)))
        return {'move':move,'jump':jump,'boost':boost,'mode':'roof-climb'}

    def apply_evasion_and_recovery(self, obs, action, mode):
        """Blend evasive movement and update stuck recovery."""
        me=obs['self']; t=obs['t']
        if self.pressure_route_steer and any(action['move']) and mode in ('roam','loot','zone','zone-walk',
                                                  'roof-approach','retreat','fight-cube','fight-weapon'):
            action['move']=self.pressure_steer(obs, action['move'], action.get('boost',False))
        dodge,laser=self.avoid_projectiles(obs)
        if mode!='unstuck' and any(dodge):
            move=action['move']; mx,my=move[0]*.4+dodge[0]*.9,move[1]*.4+dodge[1]*.9; length=math.hypot(mx,my)
            blended = [mx/max(1,length), my/max(1,length)]
            p = me['pos']
            if not me['grounded'] or self.world.line_walkable(p, (p[0]+4*blended[0], p[1]+4*blended[1])):
                action['move'] = blended
            boost_dodge = laser or (self.cornered_boost and mode == 'cornered' and me['grounded'])
            if boost_dodge and me['energy']>25: action['boost']=True
        # Short strafes and projectile dodges are deliberate combat moves, not
        # evidence that an objective route is blocked.  Only trigger the hop
        # recovery while following a route.
        if mode in ('fight', 'cornered', 'kite', 'dodge', 'heal', 'idle', 'unstuck'):
            self.stuck_since=-1.
            return
        if any(action['move']) and math.hypot(*me['vel'][:2])<1.2 and me['grounded']:
            if self.stuck_since<0: self.stuck_since=t
            elif t-self.stuck_since>.7:
                angle = self.rng.random() * math.tau
                p = me['pos']
                for offset in (0, math.pi/2, -math.pi/2, math.pi):
                    dx, dy = math.cos(angle+offset), math.sin(angle+offset)
                    if self.world.line_walkable(p, (p[0]+6*dx, p[1]+6*dy)):
                        self.unstuck_dir = (dx, dy)
                        self.unstuck_until = t + .5
                        break
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
        # The ground graph does not represent a roof or an airborne position.
        # In those cases head toward the destination instead of routing from an
        # unrelated ground cell, so a bot can leave elevated surfaces.
        if not me.get('grounded', True) or p[2]-self.world.walk_at(p[0],p[1])>3.5:
            return unit(goal)
        if d<45 and self.world.line_walkable(p,goal): return unit(goal)
        if not self.path or self.path_goal is None or math.dist(goal[:2],self.path_goal)>5 or t-self.path_at>2.5:
            remaining=max(0.,min(.025,self.action_deadline-time.perf_counter()))
            self.path,_=self.world.path(p,goal,budget_s=remaining); self.path_goal=goal[:2]; self.path_at=t
        if not self.path: return [0., 0.]
        positions=[self.world.cell_pos(c) for c in self.path[:10]]
        index=min(range(len(positions)),key=lambda i:math.dist(positions[i],p[:2]))
        self.path=self.path[index:]
        for cell in reversed(self.path[:15]):
            point=self.world.cell_pos(cell)
            if self.world.line_walkable(p,point): return unit(point)
        self.path = []
        return [0., 0.]

    def isolate_hunter(self, obs, attackers):
        """Find a short ground step with exactly one incoming firing line."""
        me, zone = obs['self'], obs['zone']
        p, now = me['pos'], obs['t']
        hunters = []
        for actor in obs['mechs']:
            if actor['kind'] != 'mech':
                continue
            pos = actor['pos']
            reach = max((self.cfg['weapons'][w].get('range', 200) for w in actor['weapons']), default=0)
            if math.dist(p[:2], pos[:2]) > reach:
                continue
            bearing = math.atan2(p[1] - pos[1], p[0] - pos[0])
            aimed = abs(angle_diff(bearing, actor['aim'][0])) < .22
            if not aimed and now - attackers.get(actor['id'], -100) > 3:
                continue
            scale = 1 + actor.get('cubes', 0) * self.cfg['cubes']['size_per_cube']
            muzzle = (*pos[:2], pos[2] + self.cfg['mech']['muzzle_height'] * scale)
            center = (*pos[:2], pos[2] + self.cfg['mech']['height'] * scale * .5)
            hunters.append((actor, muzzle, center))
        if len(hunters) < 2:
            return None

        def exposed(x, y, ground):
            chest = (x, y, ground + me['stats']['height'] * .6)
            return [h for h in hunters if self.world.shot_clear(h[1], chest)]

        ids = frozenset(h[0]['id'] for h in hunters)
        current = exposed(*p)
        if len(current) < 2 and (ids != self.duel_hunters or now > self.duel_until):
            return None
        own_range = max((w['stats'].get('range', 200) for w in me['weapons'] if w), default=0)
        best, best_cost = None, math.inf
        deadline = min(self.action_deadline, time.perf_counter() + .005)
        for i in range(-1, 32):
            if time.perf_counter() >= deadline:
                break
            radius = 0 if i < 0 else 6 * (1 + i // 16)
            angle = (i % 16) * math.pi / 8
            dx, dy = math.cos(angle), math.sin(angle)
            x, y = p[0] + radius * dx, p[1] + radius * dy
            if math.dist((x, y), zone['center']) > zone['radius'] - 5:
                continue
            if radius and not (self.world.free_cell(self.world.cell(x, y)) and self.world.line_walkable(p, (x, y))):
                continue
            ground = self.world.walk_at(x, y) if radius else p[2]
            lines = exposed(x, y, ground) if radius else current
            if len(lines) != 1:
                continue
            actor, _, center = lines[0]
            if math.dist((x, y), center[:2]) > own_range * .96:
                continue
            if not self.world.shot_clear((x, y, ground + me['stats']['muzzle_height']), center):
                continue
            cost = actor['hp'] * .18 + math.dist((x, y), center[:2]) + radius * 3
            if cost < best_cost:
                best_cost = cost
                best = ([dx, dy] if radius else [0., 0.], actor)
        if best is not None and len(current) >= 2:
            self.duel_hunters = ids
            self.duel_until = now + 2
        return best

    def combat_move(self,obs,target,seen,squad,want_los=1,items=None,desired_override=None):
        if items is None: items={}
        me=obs['self']; p=me['pos']; pos=target['pos']; d=math.dist(p[:2],pos[:2]); weapons={w['kind'] for w in me['weapons'] if w}
        if self.pressure_strafe_enabled and desired_override is not None and target['kind']=='mech':
            return self.pressure_strafe(obs, target)
        desired=58 if target['kind']=='npc' else (28 if 'lightning' in weapons and me['energy']>12 else (120 if 'laser' in weapons and squad else 85))
        if desired_override is not None:
            desired = desired_override
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

    def pressure_strafe(self, obs, target, min_range=18, max_range=42):
        """Circle in a close range band, steering around immediate obstacles."""
        me=obs['self']; p=me['pos']; pos=target['pos']
        dx,dy=pos[0]-p[0],pos[1]-p[1]; d=math.hypot(dx,dy)
        if d<1e-6: return [0.,0.]
        if obs['t']>=self.strafe_until:
            if self.rng.random()<.75: self.strafe=-self.strafe
            self.strafe_until=obs['t']+.12+self.rng.random()*.16
        ux,uy=dx/d,dy/d
        radial=max(-1.,min(1.,(d-max_range)/15)) if d>max_range else max(-1.,(d-min_range)/15) if d<min_range else 0.
        tangent=1-.6*abs(radial)
        x,y=ux*radial-uy*self.strafe*tangent,uy*radial+ux*self.strafe*tangent
        length=math.hypot(x,y); x,y=x/length,y/length
        if self.pressure_steer_enabled:
            return self.pressure_steer(obs, (x,y))
        if not me.get('grounded',True): return [x,y]
        for angle in (0.,math.pi/4,-math.pi/4,math.pi/2,-math.pi/2):
            vx=x*math.cos(angle)-y*math.sin(angle); vy=x*math.sin(angle)+y*math.cos(angle)
            if self.world.line_walkable(p,(p[0]+4*vx,p[1]+4*vy)):
                return [vx,vy]
        return [0.,0.]

    def pressure_kite(self, obs, target):
        """Keep a wider band around the nearest attacker when outnumbered."""
        return self.pressure_strafe(obs, target, 130, 190)

    def pressure_steer(self, obs, desired, boost=False):
        """Choose a short acceleration-aware step toward the desired heading."""
        me=obs['self']; p=me['pos']; stats=me['stats']; zone=obs['zone']
        grounded=me.get('grounded',True)
        acceleration=stats.get('ground_accel',58.5) if grounded else stats.get('air_accel',12.)
        speed=stats.get('boost_speed',19.5) if boost and grounded else stats.get('walk_speed',11.7)
        if any(w and w['kind']=='laser' and w.get('charge',0)>0 for w in me.get('weapons',[])):
            speed*=stats.get('charge_move_mult',.5)
        choices=((0.,0.),)+_STEER_DIRECTIONS+(desired,)
        best=(float('-inf'),(0.,0.)); previous=self.pressure_last_move
        zone_distance=math.dist(p[:2],zone['center'])
        ground_level=grounded and abs(p[2]-self.world.walk_at(*p[:2]))<3.5
        start_cell=self.world.cell(*p[:2]) if ground_level else None
        start_free=self.world.free_cell(start_cell) if ground_level else False
        shots=[]; radius=stats.get('radius',2.5); height=stats.get('height',9.)
        for shot in obs.get('projectiles',[]):
            if shot['kind']=='mortar': continue
            s=shot['pos']; v=shot['vel']; speed2=math.hypot(v[0],v[1])
            if speed2<1: continue
            rx,ry=p[0]-s[0],p[1]-s[1]
            if math.hypot(rx,ry)>95 or (rx*v[0]+ry*v[1])/speed2 < -3: continue
            if abs(rx*v[1]-ry*v[0])/speed2>4.5+radius: continue
            shots.append((s,v,25 if shot['kind']=='npc' else 45))
        for dx,dy in choices:
            vx,vy=me['vel'][:2]; x,y=p[:2]; blocked=False; penalty=0.; progress=None
            for step in range(14 if shots else 8):
                tx,ty=dx*speed-vx,dy*speed-vy
                delta=math.hypot(tx,ty); factor=min(1.,acceleration*.05/max(delta,1e-9))
                vx+=tx*factor; vy+=ty*factor
                nx,ny=x+vx*.05,y+vy*.05
                cell=self.world.cell(nx,ny) if ground_level else None
                if ground_level and cell!=start_cell and start_free and not self.world.free_cell(cell):
                    blocked=True; vx=vy=0.; nx,ny=x,y
                x,y=nx,ny
                if step==5: progress=(x,y)
                for origin,vel,damage in shots:
                    t0=step*.05; t1=t0+.05
                    ax,ay=origin[0]+vel[0]*t0,origin[1]+vel[1]*t0
                    bx,by=origin[0]+vel[0]*t1,origin[1]+vel[1]*t1
                    sx,sy=bx-ax,by-ay; denom=sx*sx+sy*sy
                    part=max(0.,min(1.,((x-ax)*sx+(y-ay)*sy)/denom)) if denom else 0.
                    if math.hypot(x-ax-part*sx,y-ay-part*sy)<radius+.85:
                        z=origin[2]+vel[2]*(t0+.05*part)
                        if p[2]-.6<z<p[2]+height+.6: penalty+=damage*.3
            px,py=progress or (x,y)
            score=((px-p[0])*desired[0]+(py-p[1])*desired[1])*1.6-penalty
            if blocked: score-=3
            end=math.dist((px,py),zone['center'])
            if zone_distance < zone['radius']-.5 and end>zone['radius']-4 and end>zone_distance:
                score-=8*(end-zone_distance)
            if dx or dy: score+=.25*(dx*previous[0]+dy*previous[1])
            if score>best[0]: best=(score,(dx,dy))
        self.pressure_last_move=best[1]
        return list(best[1])

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

    def seek_cover(self,obs,seen,deeper=False):
        me=obs['self']; p=me['pos']; now=obs['t']; zone=obs['zone']
        threats=sorted((a for a in seen if math.dist(p[:2],a['pos'][:2])<230),key=lambda a:math.dist(p[:2],a['pos'][:2]))[:4]
        if not threats: return None
        if self.cover is not None and now-self.cover_at<.4:
            return self.navigate(me,self.cover,now) if math.dist(self.cover,p[:2])>=1.5 else [0.,0.]
        self.cover_at=now
        eyes=[]
        for actor in threats:
            ap=actor['pos']; scale=1+actor.get('cubes',0)*self.cfg['cubes'].get('size_per_cube',.05)
            eyes.append((ap[0],ap[1],ap[2]+self.cfg['mech']['eye_height']*scale))
        def penalty(x,y):
            cur=math.hypot(x-zone['center'][0],y-zone['center'][1])-zone['radius']
            nxt=math.hypot(x-zone['next_center'][0],y-zone['next_center'][1])-zone['next_radius']
            value=150+5*(cur+5) if cur>-5 else 0
            if nxt>-5: value+=max(.1,min(1,1-(zone['shrink_start']-now)/25))*(25+.8*(nxt+5))
            return value
        def hidden(x,y):
            ground=self.world.walk_at(x,y); height=me['stats']['height']
            for eye in eyes:
                if self.world.shot_clear(eye,(x,y,ground+height)) or self.world.shot_clear(eye,(x,y,ground+height*.5)): return False
            return True
        current_hidden=hidden(*p[:2]) and penalty(*p[:2])==0
        nearest_now=min(math.dist(p[:2],a['pos'][:2]) for a in threats)
        run_on=deeper and current_hidden and nearest_now<80
        if current_hidden and not run_on:
            self.cover=tuple(p[:2]); return [0.,0.]
        start=self.world.nearest_free(self.world.cell(*p[:2]))
        if start is None: self.cover=None; return None
        queue=deque([(start,0)]); visited={start}; best=None; best_score=math.inf; checked=0
        # Leave time for route selection and the rest of the action after this
        # search; a single ray test can also run beyond the loop's deadline.
        deadline=min(self.action_deadline-.006,time.perf_counter()+.020)
        while queue and checked<350 and time.perf_counter()<deadline:
            cell,steps=queue.popleft()
            if steps>50 or (best is not None and steps*2>best_score+30): break
            if sum(cell)%2==0 and steps>0:
                x,y=self.world.cell_pos(cell); checked+=1
                if hidden(x,y):
                    nearest=min(math.hypot(a['pos'][0]-x,a['pos'][1]-y) for a in threats)
                    if not run_on or nearest>=nearest_now+18:
                        value=steps*2+penalty(x,y)-min(nearest,80)*.25
                        if value<best_score: best,best_score=(x,y),value
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=(cell[0]+dx,cell[1]+dy)
                if nxt in visited or not self.world.free_cell(nxt): continue
                if self.world._surface[nxt]-self.world._surface[cell]>(3.1 if dx and dy else 2.2): continue
                if dx and dy and (not self.world.free_cell((cell[0]+dx,cell[1])) or not self.world.free_cell((cell[0],cell[1]+dy))): continue
                visited.add(nxt); queue.append((nxt,steps+1))
        self.cover=best
        return self.navigate(me,best,now) if best is not None else ([0.,0.] if current_hidden else None)
