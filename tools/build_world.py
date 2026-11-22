"""Build the offline terrain and navigation cache from a supplied arena."""
import argparse
from array import array
from collections import deque
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.geometry import Arena, FIT_HEIGHT, FIT_LEVELS, FIT_RADIUS


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def rasterize(arena):
    """Rasterize solid intervals and suspended slabs on terrain vertices."""
    t=arena.terrain; nx=t['nx']; ny=t['ny']; minx=t['minX']; miny=t['minY']
    if t['step'] != 1 or t['scale'] != .01:
        raise ValueError('world builder currently requires one-meter, centimeter terrain')
    # The source format was multiplied and stored as float32 before interpolation.
    ground=array('f',(h*f32(.01) for h in arena.heights))
    cells={}
    for prism in arena.prisms:
        rings=[prism['ring'],*prism.get('holes',())]
        ys=prism['ring'][1::2]; j0=max(0,math.ceil(min(ys)-miny)); j1=min(ny-1,math.floor(max(ys)-miny))
        interval=(f32(prism['base']),f32(prism['top']),prism['kind']=='bridge')
        for j in range(j0,j1+1):
            y=miny+j+.0001; intersections=[]
            for ring in rings:
                for k in range(0,len(ring),2):
                    nxt=(k+2)%len(ring); x0,y0=ring[k:k+2]; x1,y1=ring[nxt:nxt+2]
                    if (y0<=y)!=(y1<=y): intersections.append(x0+(y-y0)/(y1-y0)*(x1-x0))
            intersections.sort()
            for k in range(0,len(intersections)-1,2):
                i0=max(0,math.ceil(intersections[k]-minx)); i1=min(nx-1,math.floor(intersections[k+1]-minx))
                for i in range(i0,i1+1): cells.setdefault(j*nx+i,[]).append(interval)
    top=array('f',ground); slabs={}
    for idx, intervals in cells.items():
        intervals.sort(key=lambda item:item[0]); base_ground=ground[idx]; level=base_ground; suspended=[]
        for base,upper,_ in intervals:
            if upper<=level: continue
            if base<=level+1.5: level=upper
            else: suspended.append((base,upper))
        top[idx]=level
        if suspended: slabs[idx]=suspended
    return ground,top,slabs


def navigation(arena,ground):
    """Build walkability, obstacle clearance and connected components."""
    t=arena.terrain; nx=t['nx']; ny=t['ny']; nnx=(nx+1)//2; nny=(ny+1)//2; n=nnx*nny
    blocked=bytearray(n); surface=array('f',[0])*n
    bounds=arena.bounds
    for j in range(nny):
        y=t['minY']+2*j
        for i in range(nnx):
            x=t['minX']+2*i; index=j*nnx+i; g=ground[(2*j)*nx+2*i]; z=g; roof=False
            solids=list(arena.solids(x,y))
            for _ in range(8):
                old=z
                for p in solids:
                    if p['top']>z and (p['base']<=z+1.5 or (p['kind']=='bridge' and p['top']-g<6.5)):
                        z=p['top']; roof=p['kind']!='bridge' and z-g>1.5
                if old==z: break
            surface[index]=z
            blocked[index]=roof or not arena.standable(x,y,z)
    clearance=array('f',[20])*n; queue=deque()
    for i,is_blocked in enumerate(blocked):
        if is_blocked: clearance[i]=0; queue.append(i)
    while queue:
        c=queue.popleft(); d=clearance[c]+2
        if d>20: continue
        i,j=c%nnx,c//nnx
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            x,y=i+dx,j+dy
            if 0<=x<nnx and 0<=y<nny:
                nb=y*nnx+x
                if clearance[nb]>d: clearance[nb]=d; queue.append(nb)
    component=array('i',[0])*n; label=0; main=0; largest=0; step_limit=f32(2.2)
    for start in range(n):
        if blocked[start] or component[start]: continue
        label+=1; component[start]=label; queue=deque([start]); count=0
        while queue:
            c=queue.popleft(); count+=1; i,j=c%nnx,c//nnx
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                x,y=i+dx,j+dy
                if not (0<=x<nnx and 0<=y<nny): continue
                nb=y*nnx+x
                # Both directions must meet the step limit.
                if not blocked[nb] and not component[nb] and abs(f32(surface[nb]-surface[c]))<=step_limit:
                    component[nb]=label; queue.append(nb)
        if count>largest: largest=count; main=label
    return nnx,nny,main,blocked,surface,clearance,component


def body_fit_table(arena, nav):
    """Largest standard footprint that clears both the walls and overhead prisms."""
    nx, ny, _, blocked, surface, _, _ = nav
    levels = bytearray(nx * ny)
    for i, occupied in enumerate(blocked):
        if occupied:
            continue
        x, y = arena.cell_pos((i % nx, i // nx))
        low, high = 0, FIT_LEVELS
        while low < high:
            level = (low + high + 1) // 2
            scale = 1 + level / 20
            if arena.standable(x, y, surface[i], FIT_RADIUS * scale, FIT_HEIGHT * scale):
                low = level
            else:
                high = level - 1
        levels[i] = low
    return levels


def write_grid(path,nav,top,slabs,fits):
    nx,ny,main,blocked,surface,clearance,component=nav
    def binary(values):
        values=array(values.typecode,values)
        if sys.byteorder!='little': values.byteswap()
        return values.tobytes()
    with open(path,'wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as out:
            out.write(struct.pack('<iii',nx,ny,main)); out.write(blocked)
            for values in (surface,clearance,component,top): out.write(binary(values))
            out.write(struct.pack('<i',len(slabs)))
            for index,intervals in sorted(slabs.items()):
                out.write(struct.pack('<ii',index,len(intervals)))
                for base,upper in intervals: out.write(struct.pack('<ff',base,upper))
            out.write(fits)


def build(directory,output):
    arena=Arena(directory,use_cache=False)
    ground,top,slabs=rasterize(arena)
    nav=navigation(arena,ground)
    write_grid(output,nav,top,slabs,body_fit_table(arena,nav))
    source=Path(directory)/'v2'
    identity={'world_sha256':hashlib.sha256((source/'world.json').read_bytes()).hexdigest(),
              'terrain_sha256':hashlib.sha256((source/'terrain.i16').read_bytes()).hexdigest()}
    Path(output).with_name(Path(output).name+'.meta.json').write_text(json.dumps(identity,indent=2)+'\n')
    return {'nx':nav[0],'ny':nav[1],'main_component':nav[2],
            'blocked':sum(nav[3]),'slab_cells':len(slabs)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arena',type=Path,default=ROOT/'arena')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(build(args.arena,args.out))


if __name__=='__main__': main()
