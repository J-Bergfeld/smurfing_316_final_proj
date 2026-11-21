"""Coarse layered navigation graph over terrain and walkable prism roofs.

The graph is built once per match from the supplied map. Edges describe walking,
jet-assisted ascent, and drops; they are conservative geometric approximations.
"""
import heapq
import math
from .geometry import distance


class NavigationGraph:
    def __init__(self, arena, config, spacing=24):
        self.arena = arena; self.step = spacing
        mech = config.get('mech', {})
        self.radius = mech.get('radius', 2.5); self.height = mech.get('height', 9)
        self.max_slope = math.tan(math.radians(mech.get('max_slope_deg', 50)))
        self.nodes = []; self.cells = {}; self.edges = []
        bounds = arena.bounds
        for ix in range(math.ceil(bounds['minX']/spacing), math.floor(bounds['maxX']/spacing)+1):
            for iy in range(math.ceil(bounds['minY']/spacing), math.floor(bounds['maxY']/spacing)+1):
                x, y = ix*spacing, iy*spacing
                if arena.walkable(x,y,self.radius,self.height):
                    self._add(ix,iy,[x,y,arena.height(x,y)],'ground')
                levels = sorted({p['top'] for p in arena.solids(x,y)})
                for z in levels:
                    if z <= arena.height(x,y)+1.5: continue
                    if not arena.blocked(x,y,z+.1,self.height):
                        self._add(ix,iy,[x,y,z],'roof')
        self.edges = [[] for _ in self.nodes]
        for i, (pos, layer, ix, iy) in enumerate(self.nodes):
            for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                for j in self.cells.get((ix+dx,iy+dy), ()):
                    if i == j: continue
                    other, other_layer, _, _ = self.nodes[j]
                    rise = other[2]-pos[2]; span = distance(pos,other)
                    if layer == other_layer == 'ground':
                        if dx == dy == 0 or abs(rise) > self.max_slope*span: continue
                        if not self._ground_clear(pos,other): continue
                        kind='walk'
                    elif layer == other_layer == 'roof':
                        if dx == dy == 0 or abs(rise)>1.2 or not self._roof_clear(pos,other): continue
                        kind='walk'
                    elif layer == 'ground' and other_layer == 'roof':
                        if not 1.2 < rise <= 45 or span > spacing*1.5: continue
                        # An overhang above the takeoff cell prevents a vertical ascent.
                        if not arena.clear([pos[0],pos[1],pos[2]+self.height],[pos[0],pos[1],other[2]+self.height]): continue
                        kind='jet'
                    elif layer == 'roof' and other_layer == 'ground':
                        if rise >= -1.2 or span == 0 or span > spacing*1.5: continue
                        kind='drop'
                    else: continue
                    cost = span + abs(rise)*(1.7 if kind=='jet' else .3)
                    self.edges[i].append((j,max(1,cost),kind,max(0,rise)))

    def _add(self, ix, iy, pos, layer):
        idx=len(self.nodes); self.nodes.append((pos,layer,ix,iy))
        self.cells.setdefault((ix,iy),[]).append(idx)

    def _ground_clear(self, a, b):
        for k in (1,2,3):
            t=k/4; x=a[0]+(b[0]-a[0])*t; y=a[1]+(b[1]-a[1])*t
            if not self.arena.walkable(x,y,self.radius,self.height): return False
        return True

    def _roof_clear(self, a, b):
        for k in (1,2,3):
            t=k/4; x=a[0]+(b[0]-a[0])*t; y=a[1]+(b[1]-a[1])*t; z=a[2]+(b[2]-a[2])*t
            if not any(abs(p['top']-z)<1.2 for p in self.arena.solids(x,y)): return False
            if self.arena.blocked(x,y,z+.1,self.height): return False
        return True

    def nearest(self, pos):
        ix,iy=round(pos[0]/self.step),round(pos[1]/self.step)
        options=[]
        for dx in range(-2,3):
            for dy in range(-2,3):
                for i in self.cells.get((ix+dx,iy+dy),()):
                    p=self.nodes[i][0]; options.append((distance(pos,p)+abs(pos[2]-p[2])*2,i))
        return min(options)[1] if options else None

    def route(self, start, goal, energy=100):
        source=self.nearest(start); target=self.nearest(goal)
        if source is None or target is None: return None
        if source==target: return [goal[:]]
        costs={source:0}; parent={}; queue=[(0,0,source)]; expanded=0
        while queue and expanded < 500:
            _,cost,node=heapq.heappop(queue)
            if cost != costs.get(node): continue
            if node==target: break
            expanded += 1
            for nxt,weight,kind,rise in self.edges[node]:
                if kind=='jet' and energy < rise*1.7+10: continue
                new=cost+weight
                if new < costs.get(nxt,math.inf):
                    costs[nxt]=new; parent[nxt]=node
                    heuristic=distance(self.nodes[nxt][0],self.nodes[target][0])
                    heapq.heappush(queue,(new+heuristic,new,nxt))
        if target not in parent: return None
        path=[]; node=target
        while node!=source:
            path.append(self.nodes[node][0][:]); node=parent[node]
        path.reverse(); path.append(goal[:])
        return path
