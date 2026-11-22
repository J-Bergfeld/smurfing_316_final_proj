"""Bounded routing across ground and solid top surfaces."""
import heapq
import math
import time


class SurfaceNavigator:
    def __init__(self, world, spacing=4.):
        self.world=world; self.spacing=spacing; self.heights={}
        self.path=[]; self.goal=None; self.planned=-100.
        self.watch_time=-100.; self.watch_pos=None; self.banned={}
        self.pushing=False

    def cell(self, pos):
        return (round(pos[0]/self.spacing),round(pos[1]/self.spacing))

    def point(self, cell):
        return (cell[0]*self.spacing,cell[1]*self.spacing)

    def top(self, cell):
        if cell not in self.heights:
            x,y=self.point(cell)
            self.heights[cell]=max([self.world.ground(x,y)]+[p['top'] for p in self.world.solids(x,y)])
        return self.heights[cell]

    def plan(self, start, goal, max_climb, now, deadline, radius=2.5, height=9):
        source=self.cell(start); target=self.cell(goal)
        if source==target: return [source]
        queue=[(0.,0.,source)]; costs={source:0.}; parent={}; best=source
        best_dist=math.dist(source,target); expanded=0
        while queue and expanded<1000 and time.perf_counter()<deadline:
            _,cost,cell=heapq.heappop(queue)
            if cost!=costs.get(cell): continue
            if cell==target: best=cell; break
            expanded+=1
            current=start[2] if cell==source else self.top(cell)
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt=(cell[0]+dx,cell[1]+dy); x,y=self.point(nxt)
                if not self.world.inside(x,y) or self.banned.get(nxt,0)>now: continue
                rise=self.top(nxt)-current
                if rise>max_climb: continue
                if rise>1.2 and not self.world.standable(x,y,self.top(nxt),radius,height): continue
                length=self.spacing*math.hypot(dx,dy)
                new=cost+length+(10+2.2*rise if rise>1.2 else 1.5 if rise< -1.2 else 0)
                if new>=costs.get(nxt,math.inf): continue
                costs[nxt]=new; parent[nxt]=cell
                remaining=math.dist(nxt,target)
                heapq.heappush(queue,(new+remaining*self.spacing,new,nxt))
                if remaining<best_dist: best,best_dist=nxt,remaining
        if best==source: return []
        path=[best]
        while path[-1]!=source: path.append(parent[path[-1]])
        return list(reversed(path))

    def step(self, obs, goal, deadline):
        me=obs['self']; p=me['pos']; now=obs['t']; stats=me['stats']
        drain=stats.get('jet_drain',15) or 15
        max_climb=max(0.,min(40.,(me.get('max_energy',100)-28)/drain*8.9))
        if self.watch_pos is None or now-self.watch_time>=1.5:
            if self.watch_pos is not None and self.pushing and self.path and math.dist(p,self.watch_pos)<1.2:
                for cell in self.path[1:4]: self.banned[cell]=now+25
                self.path=[]
            self.watch_pos=p[:]; self.watch_time=now
        if (not self.path or self.goal is None or math.dist(goal[:2],self.goal)>6
                or now-self.planned>1.2):
            self.path=self.plan(p,goal,max_climb,now,deadline,stats.get('radius',2.5),stats.get('height',9))
            self.goal=tuple(goal[:2]); self.planned=now
        if len(self.path)<2:
            self.pushing=False
            return None
        nearest=min(range(min(8,len(self.path))),key=lambda i:math.dist(p[:2],self.point(self.path[i])))
        self.path=self.path[nearest:]
        if len(self.path)<2:
            self.pushing=False
            return None
        nxt=self.path[1]; point=self.point(nxt); rise=self.top(nxt)-p[2]
        dx,dy=point[0]-p[0],point[1]-p[1]; dist=math.hypot(dx,dy)
        move=[dx/dist,dy/dist] if dist>1e-6 else [0.,0.]
        jump=boost=False
        if rise>=1.0:
            need=min(rise/8.9*drain+16,me.get('max_energy',100)-3)
            if me.get('grounded',True):
                if me['energy']>=need: jump=True
                else: move=[0.,0.]
            else: boost=me['energy']>1
        elif me.get('grounded',True) and not me.get('in_zone',True): boost=me['energy']>70
        self.pushing=bool(any(move))
        return {'move':move,'jump':jump,'boost':boost}
