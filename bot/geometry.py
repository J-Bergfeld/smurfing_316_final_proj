"""Static map queries and bounded local routing in world coordinates."""
import heapq
import gzip
import hashlib
import json
import math
import os
import struct
import time
from array import array
from pathlib import Path


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


def inside(x, y, ring):
    hit = False
    j = len(ring) - 2
    for i in range(0, len(ring), 2):
        xi, yi, xj, yj = ring[i], ring[i + 1], ring[j], ring[j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


class Map:
    def __init__(self, directory):
        with open(os.path.join(directory, 'v2', 'world.json')) as f:
            data = json.load(f)
        self.terrain = data['terrain']
        with open(os.path.join(directory, 'v2', 'terrain.i16'), 'rb') as f:
            raw = f.read()
        self.heights = struct.unpack('<%dh' % (len(raw) // 2), raw)
        self.bounds = data['bounds']
        self.grid = {}
        self.prisms = []
        for p in data['prisms']:
            ring = p['ring']
            xs, ys = ring[::2], ring[1::2]
            p['bbox'] = (min(xs), min(ys), max(xs), max(ys))
            idx = len(self.prisms)
            self.prisms.append(p)
            a, b, c, d = p['bbox']
            for x in range(math.floor(a / 40), math.floor(c / 40) + 1):
                for y in range(math.floor(b / 40), math.floor(d / 40) + 1):
                    self.grid.setdefault((x, y), []).append(idx)

    def height(self, x, y):
        t = self.terrain
        fx, fy = (x-t['minX'])/t['step'], (y-t['minY'])/t['step']
        ix = max(0, min(t['nx']-2, math.floor(fx)))
        iy = max(0, min(t['ny']-2, math.floor(fy)))
        dx, dy = max(0, min(1, fx-ix)), max(0, min(1, fy-iy))
        n = t['nx']; h = self.heights; i = iy*n+ix
        return t['scale'] * ((h[i]*(1-dx)+h[i+1]*dx)*(1-dy)+(h[i+n]*(1-dx)+h[i+n+1]*dx)*dy)

    def solids(self, x, y):
        for idx in self.grid.get((math.floor(x/40), math.floor(y/40)), ()):
            p = self.prisms[idx]; a, b, c, d = p['bbox']
            if a <= x <= c and b <= y <= d and inside(x, y, p['ring']) and not any(inside(x, y, hole) for hole in p.get('holes', [])):
                yield p

    def blocked(self, x, y, z, height=0):
        if not (self.bounds['minX'] <= x <= self.bounds['maxX'] and self.bounds['minY'] <= y <= self.bounds['maxY']):
            return True
        return any(p['base'] < z + height and p['top'] > z for p in self.solids(x, y))

    def clear(self, a, b):
        # Sampling is deliberately conservative; geometry is approximate, especially at thin walls.
        n = max(1, math.ceil(math.dist(a, b)/3))
        for i in range(1, n):
            t = i/n; x = a[0]+t*(b[0]-a[0]); y = a[1]+t*(b[1]-a[1]); z = a[2]+t*(b[2]-a[2])
            if self.blocked(x, y, z) or self.height(x, y) > z:
                return False
        return True

    def walkable(self, x, y, radius=2.5, height=9):
        z = self.height(x, y) + .1
        return not any(self.blocked(x+dx, y+dy, z, height) for dx,dy in ((0,0),(radius,0),(-radius,0),(0,radius),(0,-radius)))

    def supported(self, x, y, z, radius=2.5, height=9):
        """Conservative footing check for ground or a roof at the current height."""
        if abs(z-self.height(x,y)) < 2:
            return self.walkable(x,y,radius,height)
        for dx,dy in ((0,0),(radius,0),(-radius,0),(0,radius),(0,-radius)):
            sx,sy=x+dx,y+dy
            if not any(abs(solid['top']-z)<2 for solid in self.solids(sx,sy)):
                return False
            if self.blocked(sx,sy,z+.1,height): return False
        return True

    def roof_candidates(self, pos, radius=110):
        """Find nearby solid roofs; returned points are geometric candidates, not guaranteed landings."""
        result = []
        seen = set()
        for gx in range(math.floor((pos[0]-radius)/40), math.floor((pos[0]+radius)/40)+1):
            for gy in range(math.floor((pos[1]-radius)/40), math.floor((pos[1]+radius)/40)+1):
                for idx in self.grid.get((gx,gy), ()):
                    if idx in seen: continue
                    seen.add(idx); p = self.prisms[idx]
                    a,b,c,d = p['bbox']; x=(a+c)/2; y=(b+d)/2
                    if distance(pos,(x,y)) > radius or not inside(x,y,p['ring']) or any(inside(x,y,h) for h in p.get('holes', [])): continue
                    if p['top'] <= pos[2]+2 or p['top'] > pos[2]+60: continue
                    if not self.blocked(x,y,p['top']+.2,9): result.append([x,y,p['top']+.2])
        return sorted(result, key=lambda point:distance(pos,point))[:5]

    def route(self, start, goal, radius=2.5, height=9, budget_s=.005):
        """Bounded coarse A*: return first waypoint, or None when no route is found."""
        step = 12.0
        origin = (round(start[0]/step), round(start[1]/step))
        target = (round(goal[0]/step), round(goal[1]/step))
        q = [(0, 0, origin)]; cost = {origin: 0}; parent = {}; count = 0
        best = origin; best_h = math.dist(origin, target); deadline = time.perf_counter()+budget_s
        while q and count < 50:
            if time.perf_counter() >= deadline: break
            _, g, node = heapq.heappop(q)
            if g != cost.get(node): continue
            count += 1
            h = math.dist(node, target)
            if h < best_h: best, best_h = node, h
            if h <= 1: best = node; break
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nxt = node[0]+dx, node[1]+dy
                x, y = nxt[0]*step, nxt[1]*step
                if not self.walkable(x,y,radius,height): continue
                if abs(self.height(x,y)-self.height(node[0]*step,node[1]*step)) > step*1.0: continue
                if dx and dy and (not self.walkable(node[0]*step+dx*step,node[1]*step,radius,height) or not self.walkable(node[0]*step,node[1]*step+dy*step,radius,height)): continue
                ng = g + math.hypot(dx,dy)
                if ng < cost.get(nxt, float('inf')):
                    cost[nxt] = ng; parent[nxt] = node
                    heapq.heappush(q,(ng+math.dist(nxt,target),ng,nxt))
        if best == origin: return None
        while parent.get(best) != origin and best in parent: best = parent[best]
        return [best[0]*step, best[1]*step, self.height(best[0]*step,best[1]*step)]


def _inside(ring, x, y):
    hit=False; j=len(ring)-2
    for i in range(0,len(ring),2):
        xi,yi=ring[i:i+2]; xj,yj=ring[j:j+2]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: hit=not hit
        j=i
    return hit

def zone_at(hold, zone, when):
    start, end = zone['shrink_start'], zone['shrink_end']
    if when <= start or end <= start:
        return hold
    fraction = max(0.,min(1.,(when-start)/(end-start)))
    return tuple(hold[i]+(zone['next_center'][i]-hold[i])*fraction for i in range(2)) + (hold[2]+(zone['next_radius']-hold[2])*fraction,)

def zone_deadline(hold, zone, x, y, pad):
    if math.hypot(x-zone['next_center'][0],y-zone['next_center'][1]) <= zone['next_radius']-pad:
        return math.inf
    for k in range(25):
        t=zone['shrink_start']+(zone['shrink_end']-zone['shrink_start'])*k/24
        cx,cy,radius=zone_at(hold,zone,t)
        if math.hypot(x-cx,y-cy)>radius-pad:
            return t
    return zone['shrink_end']

def zone_goal(zone, x, y):
    radius=zone['next_radius']; center=zone['next_center']
    if radius <= 30: return tuple(center)
    dx,dy=x-center[0],y-center[1]; d=math.hypot(dx,dy)
    margin=max(3,min(30,.3*radius)); r=max(0,radius-margin-5)
    if d < 1 or d <= r: return x,y
    return center[0]+dx/d*r,center[1]+dy/d*r

# Compact ground-grid fit table: each level is 5% of a standard 2.5 x 9 m mech.
FIT_RADIUS = 2.5
FIT_HEIGHT = 9.
FIT_LEVELS = 20


class Arena:
    def __init__(self, directory, use_cache=True):
        path=Path(directory)/'v2'
        world_raw=(path/'world.json').read_bytes(); data=json.loads(world_raw); self.terrain=data['terrain']; self.bounds=data['bounds']
        raw=(path/'terrain.i16').read_bytes(); n=self.terrain['nx']*self.terrain['ny']
        if len(raw)!=n*2: raise ValueError('terrain size mismatch')
        self.heights=struct.unpack('<%dh'%n,raw); self.prisms=data['prisms']; self.grid={}; self._free={}; self._surface={}; self._block_max={}
        self.body_size = (FIT_RADIUS, FIT_HEIGHT)
        self.fit_level = 0
        self.swept_fit_level = 12
        self.baked=None
        cache=Path(__file__).with_name('terrain_grid.bin.gz')
        manifest=cache.with_name(cache.name+'.meta.json')
        try:
            identity=json.loads(manifest.read_text()) if use_cache else {}
        except (OSError,ValueError):
            identity={}
        if (use_cache and cache.exists() and identity.get('world_sha256')==hashlib.sha256(world_raw).hexdigest()
                and identity.get('terrain_sha256')==hashlib.sha256(raw).hexdigest()):
            with gzip.open(cache,'rb') as f: baked=f.read()
            nx,ny,main=struct.unpack_from('<iii',baked); count=nx*ny; offset=12
            blocked=baked[offset:offset+count]; offset+=count
            def unpack_array(kind,size):
                nonlocal offset
                result=array(kind); result.frombytes(baked[offset:offset+size*4]); offset+=size*4
                if struct.pack('=I',1)!=struct.pack('<I',1): result.byteswap()
                return result
            surf=unpack_array('f',count); clearance=unpack_array('f',count); comp=unpack_array('i',count); top=unpack_array('f',n)
            slab_count=struct.unpack_from('<i',baked,offset)[0]; offset+=4; slabs={}
            for _ in range(slab_count):
                index,size=struct.unpack_from('<ii',baked,offset); offset+=8
                slabs[index]=[struct.unpack_from('<ff',baked,offset+j*8) for j in range(size)]; offset+=size*8
            fits = baked[offset:]
            if fits and len(fits) != count:
                raise ValueError('invalid body fit table')
            self.baked={'fits':fits,'nx':nx,'ny':ny,'main':main,'blocked':blocked,'surface':surf,'clearance':clearance,'component':comp,'top':top,'slabs':slabs}
        for i,prism in enumerate(self.prisms):
            xs=prism['ring'][::2]; ys=prism['ring'][1::2]
            prism['box']=(min(xs),min(ys),max(xs),max(ys))
            for gx in range(math.floor(min(xs)/16),math.floor(max(xs)/16)+1):
                for gy in range(math.floor(min(ys)/16),math.floor(max(ys)/16)+1):
                    self.grid.setdefault((gx,gy),[]).append(i)

    def ground(self,x,y):
        t=self.terrain; fx=(x-t['minX'])/t['step']; fy=(y-t['minY'])/t['step']
        ix=max(0,min(t['nx']-2,math.floor(fx))); iy=max(0,min(t['ny']-2,math.floor(fy)))
        dx=max(0,min(1,fx-ix)); dy=max(0,min(1,fy-iy)); i=iy*t['nx']+ix; h=self.heights; n=t['nx']
        return t['scale']*((h[i]*(1-dx)+h[i+1]*dx)*(1-dy)+(h[i+n]*(1-dx)+h[i+n+1]*dx)*dy)

    def inside(self,x,y):
        bounds=self.bounds
        return bounds['minX']<=x<=bounds['maxX'] and bounds['minY']<=y<=bounds['maxY']

    def solids(self,x,y):
        for index in self.grid.get((math.floor(x/16),math.floor(y/16)),()):
            prism=self.prisms[index]; a,b,c,d=prism['box']
            if a<=x<=c and b<=y<=d and _inside(prism['ring'],x,y) and not any(_inside(hole,x,y) for hole in prism.get('holes',())):
                yield prism

    def solid(self,x,y,z):
        if z<self.ground(x,y): return True
        return any(prism['base']<z<prism['top'] for prism in self.solids(x,y))

    def walk_at(self,x,y):
        ground=self.ground(x,y); level=ground
        candidates=list(self.solids(x,y))
        for _ in range(8):
            old=level
            for p in candidates:
                if p['top']>level and (p['base']<=level+1.5 or (p['kind']=='bridge' and p['top']-ground<6.5)):
                    level=p['top']
            if level==old: break
        return level

    def _ray_prism(self,p,a,b):
        x,y,z=a; dx,dy,dz=(b[i]-a[i] for i in range(3)); lo,hi=0.,1.
        bounds=((p['box'][0],p['box'][2]),(p['box'][1],p['box'][3]),(p['base'],p['top']))
        for origin,direction,(lower,upper) in zip(a,(dx,dy,dz),bounds):
            if abs(direction)<1e-9:
                if origin<lower or origin>upper: return False
            else:
                u,v=(lower-origin)/direction,(upper-origin)/direction
                lo=max(lo,min(u,v)); hi=min(hi,max(u,v))
                if lo>hi: return False
        def inside(px,py):
            return _inside(p['ring'],px,py) and not any(_inside(h,px,py) for h in p.get('holes',()))
        if p['base']<=z<=p['top'] and inside(x,y): return True
        for ring in [p['ring'],*p.get('holes',())]:
            for i in range(0,len(ring),2):
                j=(i+2)%len(ring); ex,ey=ring[j]-ring[i],ring[j+1]-ring[i+1]
                den=dx*ey-dy*ex
                if abs(den)<1e-9: continue
                px,py=ring[i]-x,ring[i+1]-y
                t=(px*ey-py*ex)/den; s=(px*dy-py*dx)/den
                if 0<=t<1 and 0<=s<=1 and p['base']<=z+dz*t<=p['top']: return True
        if abs(dz)>1e-9:
            for level,direction in ((p['top'],1),(p['base'],-1)):
                t=(level-z)/dz
                if 0<=t<1 and direction*dz<=0 and inside(x+dx*t,y+dy*t): return True
        return False

    def shot_clear(self,a,b):
        x0,x1=sorted((a[0],b[0])); y0,y1=sorted((a[1],b[1])); candidates=set()
        for gx in range(math.floor(x0/16),math.floor(x1/16)+1):
            for gy in range(math.floor(y0/16),math.floor(y1/16)+1): candidates.update(self.grid.get((gx,gy),()))
        if any(self._ray_prism(self.prisms[i],a,b) for i in candidates): return False
        if a[2]<self.ground(a[0],a[1]): return False
        dx,dy,dz=(b[i]-a[i] for i in range(3)); length=math.hypot(dx,dy); t=0.
        if length<1e-9:
            return min(a[2],b[2])>=self.ground(a[0],a[1])
        origin_x=self.terrain['minX']; origin_y=self.terrain['minY']; nx=self.terrain['nx']; ny=self.terrain['ny']
        while t<1:
            x,y=a[0]+dx*t,a[1]+dy*t; bx=math.floor((x-origin_x)/8); by=math.floor((y-origin_y)/8)
            def crossing(pos,direction,origin,cell):
                if abs(direction)<1e-9: return math.inf
                edge=origin+(cell+(1 if direction>0 else 0))*8
                return (edge-pos)/direction
            end=min(1.,t+max(0.,min(crossing(x,dx,origin_x,bx),crossing(y,dy,origin_y,by)))+1e-6)
            key=(bx,by)
            if key not in self._block_max:
                ix=max(0,min(nx-1,bx*8)); iy=max(0,min(ny-1,by*8)); jx=min(nx,ix+9); jy=min(ny,iy+9)
                self._block_max[key]=max(self.heights[j*nx+i] for j in range(iy,jy) for i in range(ix,jx))*self.terrain['scale']
            if min(a[2]+dz*t,a[2]+dz*end)<=self._block_max[key]:
                steps=max(1,math.ceil((end-t)*length/.5))
                for i in range(1,steps+1):
                    q=t+(end-t)*i/steps
                    if a[2]+dz*q<self.ground(a[0]+dx*q,a[1]+dy*q): return False
            t=end
        return True

    def standable(self,x,y,z,radius=2.6,height=9):
        b=self.bounds
        if x<b['minX']+radius or x>b['maxX']-radius or y<b['minY']+radius or y>b['maxY']-radius: return False
        indices=set()
        for gx in range(math.floor((x-radius)/16),math.floor((x+radius)/16)+1):
            for gy in range(math.floor((y-radius)/16),math.floor((y+radius)/16)+1): indices.update(self.grid.get((gx,gy),()))
        for i in indices:
            p=self.prisms[i]
            if p['top']<=z+1.2 or p['base']>=z+height: continue
            if i in self.grid.get((math.floor(x/16),math.floor(y/16)),()) and any(q is p for q in self.solids(x,y)): return False
            for ring in [p['ring'],*p.get('holes',())]:
                for j in range(0,len(ring),2):
                    k=(j+2)%len(ring); x0,y0=ring[j],ring[j+1]; dx,dy=ring[k]-x0,ring[k+1]-y0; length=dx*dx+dy*dy
                    t=max(0,min(1,((x-x0)*dx+(y-y0)*dy)/length)) if length>1e-9 else 0
                    if (x0+dx*t-x)**2+(y0+dy*t-y)**2<radius*radius: return False
        return True

    def cell(self,x,y):
        i=math.floor((x-self.terrain['minX'])/2+.5); j=math.floor((y-self.terrain['minY'])/2+.5)
        nx=self.baked['nx'] if self.baked else (self.terrain['nx']+1)//2; ny=self.baked['ny'] if self.baked else (self.terrain['ny']+1)//2
        return max(0,min(nx-1,i)),max(0,min(ny-1,j))

    def cell_pos(self,cell):
        return self.terrain['minX']+cell[0]*2,self.terrain['minY']+cell[1]*2

    def reachable(self,x,y):
        cell=self.cell(x,y)
        if not self.free_cell(cell): return False
        if not self.baked: return True
        index=cell[1]*self.baked['nx']+cell[0]
        return self.baked['component'][index]==self.baked['main']

    def exposure(self,x,y):
        """Estimate exposure using 24 raster rays."""
        if not self.baked: return 1.
        z=self.walk_at(x,y)+7; terrain=self.terrain; nx=terrain['nx']; ny=terrain['ny']; top=self.baked['top']; slabs=self.baked['slabs']; bounds=self.bounds
        minx,miny=terrain['minX'],terrain['minY']; minbx,maxbx,minby,maxby=bounds['minX'],bounds['maxX'],bounds['minY'],bounds['maxY']
        total=0.
        for k in range(24):
            angle=k*math.pi/12; ux,uy=math.cos(angle),math.sin(angle); d=2.5
            while d<200:
                px,py=x+ux*d,y+uy*d
                if not (minbx<=px<=maxbx and minby<=py<=maxby): break
                i=int(px-minx+.5); j=int(py-miny+.5)
                if i<0 or i>=nx or j<0 or j>=ny: break
                idx=j*nx+i
                if z<top[idx]-.05: break
                layers=slabs.get(idx)
                if layers and any(base<z<upper for base,upper in layers): break
                d+=2.5
            total+=d
        return total/(24*200)

    def set_body_size(self, radius, height):
        if self.body_size == (radius, height):
            return
        self.body_size = (radius, height)
        self.fit_level = max(0, math.ceil((max(radius / FIT_RADIUS, height / FIT_HEIGHT) - 1) * 20 - 1e-9))
        # A grid sample can be sqrt(2) metres from its 2 m cell center.
        self.swept_fit_level = max(self.fit_level, math.ceil(((radius + math.sqrt(2)) / FIT_RADIUS - 1) * 20))
        self._free.clear()

    def free_cell(self,cell):
        if self.baked:
            i,j=cell
            if not (0<=i<self.baked['nx'] and 0<=j<self.baked['ny']): return False
            idx=j*self.baked['nx']+i
            self._surface[cell]=self.baked['surface'][idx]
            if self.baked['blocked'][idx]:
                return False
            fits = self.baked['fits']
            if self.fit_level == 0 or (fits and self.fit_level <= fits[idx]):
                return True
            if cell not in self._free:
                self._free[cell] = self.standable(*self.cell_pos(cell), self._surface[cell], *self.body_size)
            return self._free[cell]
        if cell in self._free: return self._free[cell]
        x,y=self.cell_pos(cell)
        if not self.inside(x,y): self._free[cell]=False; return False
        z=self.walk_at(x,y); self._surface[cell]=z
        self._free[cell]=z-self.ground(x,y)<=1.5 and self.standable(x,y,z,*self.body_size)
        return self._free[cell]

    def nearest_free(self,cell):
        if self.free_cell(cell): return cell
        cx,cy=cell
        for radius in range(1,21):
            options=[]
            for dy in range(-radius,radius+1):
                for dx in range(-radius,radius+1):
                    if max(abs(dx),abs(dy))==radius and self.free_cell((cx+dx,cy+dy)):
                        options.append((dx*dx+dy*dy,(cx+dx,cy+dy)))
            if options: return min(options)[1]
        return None

    def path(self,start,goal,max_expand=22000,budget_s=.025):
        source=self.nearest_free(self.cell(*start[:2])); target=self.nearest_free(self.cell(*goal[:2]))
        if source is None or target is None: return [],False
        def heuristic(c):
            x,y=abs(c[0]-target[0]),abs(c[1]-target[1])
            return (max(x,y)+.4142*min(x,y))*2*1.15
        costs={source:0}; parents={source:None}; frontier=[(heuristic(source),source)]; closed=set(); best=source; best_h=heuristic(source)
        directions=((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
        deadline=time.perf_counter()+budget_s
        for _ in range(max_expand):
            if not frontier or time.perf_counter()>=deadline: break
            _,cell=heapq.heappop(frontier)
            if cell in closed: continue
            closed.add(cell)
            if cell==target: best=cell; break
            h=heuristic(cell)
            if h<best_h: best,best_h=cell,h
            for dx,dy in directions:
                nxt=(cell[0]+dx,cell[1]+dy); diagonal=bool(dx and dy)
                if nxt in closed or not self.free_cell(nxt): continue
                if self._surface[nxt]-self._surface[cell]>(3.1 if diagonal else 2.2): continue
                if diagonal and (not self.free_cell((cell[0]+dx,cell[1])) or not self.free_cell((cell[0],cell[1]+dy))): continue
                step=2*(1.4142 if diagonal else 1)
                if self.baked:
                    clear=self.baked['clearance'][nxt[1]*self.baked['nx']+nxt[0]]
                    if clear<4: step*=1+(4-clear)*.15
                new=costs[cell]+step
                if new<costs.get(nxt,math.inf):
                    costs[nxt]=new; parents[nxt]=cell; heapq.heappush(frontier,(new+heuristic(nxt),nxt))
        route=[]; node=best
        while node is not None:
            route.append(node); node=parents[node]
        return list(reversed(route)),best==target

    def line_walkable(self,a,b):
        if not self.standable(*b[:2], self.walk_at(*b[:2]), *self.body_size):
            return False
        dist=math.dist(a[:2],b[:2]); steps=int(dist)+1; last=self.cell(*a[:2]); previous=self.walk_at(*self.cell_pos(last))
        for i in range(1,steps+1):
            t = i / steps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            cell = self.cell(x, y)
            if self.fit_level:
                fits = self.baked['fits'] if self.baked else None
                if not fits or fits[cell[1]*self.baked['nx'] + cell[0]] < self.swept_fit_level:
                    if not self.standable(x, y, self.walk_at(x, y), *self.body_size):
                        return False
            if cell==last: continue
            diagonal = cell[0] != last[0] and cell[1] != last[1]
            if diagonal and (not self.free_cell((cell[0], last[1])) or not self.free_cell((last[0], cell[1]))):
                return False
            if not self.free_cell(cell): return False
            surface = self._surface[cell]
            if surface - previous > (3.1 if diagonal else 2.2): return False
            last,previous=cell,surface
        return True
