"""Compare two generated terrain caches, ignoring gzip and slab ordering."""
import argparse
from array import array
import gzip
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]


def read_grid(path,terrain_count):
    with gzip.open(path,'rb') as f: data=f.read()
    nx,ny,main=struct.unpack_from('<iii',data); count=nx*ny; offset=12
    blocked=data[offset:offset+count]; offset+=count
    def values(kind,size):
        nonlocal offset
        result=array(kind); result.frombytes(data[offset:offset+4*size]); offset+=4*size
        if sys.byteorder!='little': result.byteswap()
        return result
    surface=values('f',count); clearance=values('f',count); component=values('i',count); top=values('f',terrain_count)
    slab_count=struct.unpack_from('<i',data,offset)[0]; offset+=4; slabs={}
    for _ in range(slab_count):
        index,size=struct.unpack_from('<ii',data,offset); offset+=8
        slabs[index]=[struct.unpack_from('<ff',data,offset+i*8) for i in range(size)]; offset+=size*8
    if offset!=len(data): raise ValueError('unexpected cache length')
    return {'header':(nx,ny,main),'blocked':blocked,'surface':surface,'clearance':clearance,'component':component,'top':top,'slabs':slabs}


def compare(a,b):
    out={'header_equal':a['header']==b['header']}
    for key in ('blocked','surface','clearance','component','top'):
        x,y=a[key],b[key]
        differences=[abs(left-right) for left,right in zip(x,y) if left!=right]
        out[key]={'length_equal':len(x)==len(y),'different':len(differences),'max_difference':max(differences,default=0)}
    left,right=a['slabs'],b['slabs']; common=left.keys()&right.keys()
    out['slabs']={'missing_keys':len(left.keys()^right.keys()),'different':sum(left[k]!=right[k] for k in common)}
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first',type=Path); parser.add_argument('second',type=Path)
    parser.add_argument('--arena',type=Path,default=ROOT/'arena')
    args=parser.parse_args()
    data=json.loads((args.arena/'v2/world.json').read_text()); count=data['terrain']['nx']*data['terrain']['ny']
    result=compare(read_grid(args.first,count),read_grid(args.second,count)); print(json.dumps(result,indent=2))
    if not result['header_equal'] or any(not v['length_equal'] or v['different'] for k,v in result.items() if k not in ('header_equal','slabs')) or any(result['slabs'].values()):
        raise SystemExit(1)


if __name__=='__main__': main()
