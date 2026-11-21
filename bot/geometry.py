"""Static map queries and bounded local routing in world coordinates."""
import heapq
import json
import math
import os
import struct


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

    def route(self, start, goal, radius=2.5, height=9):
        """Bounded coarse A*: return first waypoint, or None when no route is found."""
        step = 12.0
        origin = (round(start[0]/step), round(start[1]/step))
        target = (round(goal[0]/step), round(goal[1]/step))
        q = [(0, 0, origin)]; cost = {origin: 0}; parent = {}; count = 0
        best = origin; best_h = math.dist(origin, target)
        while q and count < 50:
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
