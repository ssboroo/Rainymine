"""SRS v2 numeric primitives; world XYZ are float64, render buffers local float32."""
import math
import numpy as np
from .core import finite


def rtc_buffer(world, origin):
    xyz=np.asarray(world,dtype=np.float64);origin=np.asarray(origin,dtype=np.float64)
    if xyz.ndim!=2 or xyz.shape[1]!=3 or origin.shape!=(3,) or not np.isfinite(xyz).all() or not np.isfinite(origin).all():
        raise ValueError('RTC XYZ / origin буруу.')
    local=xyz-origin
    if np.any(np.abs(local)>np.finfo(np.float32).max):raise ValueError('RTC extent хэт их.')
    return np.ascontiguousarray(local,dtype=np.float32)


def morton_codes(indices):
    """63-bit interleave of three unsigned 21-bit grid coordinates (X low bit).

    A spatial sort key, NOT a unique subblock ID: retain block_id/subblock_level.
    """
    a=np.asarray(indices)
    if a.ndim!=2 or a.shape[1]!=3 or a.dtype.kind not in 'iu' or np.any(a<0) or np.any(a>=2**21):
        raise ValueError('Morton индекс бүр 0…2^21−1 бүхэл тоо байна.')
    a=a.astype(np.uint64);out=np.zeros(len(a),dtype=np.uint64)
    for bit in range(21):
        for axis in range(3):out|=((a[:,axis]>>np.uint64(bit))&np.uint64(1))<<np.uint64(3*bit+axis)
    return out


def oriented_core(azimuth,dip,alpha,beta):
    """PDF equation 12: ENU, grid azimuth north clockwise; beta bottom-reference.

    Returns an upward-hemisphere normal. Vertical planes have 180-degree dip-
    direction ambiguity; horizontal planes have no unique dip direction.
    """
    finite(azimuth,dip,alpha,beta)
    if not 0<=azimuth<360 or not -90<=dip<=90 or not 0<=alpha<=90 or not 0<=beta<360:
        raise ValueError('Чөмгийн / цооногийн өнцөг буруу.')
    a,b,h,t=map(math.radians,(alpha,beta,-azimuth,dip+90))
    normal=np.array([math.cos(a)*math.sin(b),math.cos(a)*math.cos(b),-math.sin(a)])
    rx=np.array([[1,0,0],[0,math.cos(t),-math.sin(t)],[0,math.sin(t),math.cos(t)]])
    rz=np.array([[math.cos(h),-math.sin(h),0],[math.sin(h),math.cos(h),0],[0,0,1]])
    normal=rz@rx@normal
    if normal[2]<0:normal=-normal
    true_dip=math.degrees(math.acos(np.clip(abs(normal[2]),0,1)))
    direction=None if math.hypot(*normal[:2])<1e-12 else math.degrees(math.atan2(normal[0],normal[1]))%360
    return {'dip':true_dip,'dip_direction':direction,'normal':normal.tolist(),
            'convention':'ENU; beta from bottom reference; upward normal',
            'direction_ambiguous':true_dip>90-1e-8}


def density_composites(intervals,length):
    """One-hole intervals, equal cross-section: weights=overlap metres*density.

    Density is required per interval, never inferred. Gaps remain missing.
    """
    finite(length)
    if length<=0:raise ValueError('Композитын урт эерэг байна.')
    rows=sorted(intervals,key=lambda r:r['from_m']);end=0.
    for r in rows:
        finite(r['from_m'],r['to_m'],r['grade'],r['density'])
        if r['from_m']<end or r['from_m']<0 or r['to_m']<=r['from_m'] or r['density']<=0:
            raise ValueError('Интервал / density буруу.')
        end=r['to_m']
    if end/length>100000:raise ValueError('Композитын тоо хэт их.')
    result=[];cursor=0
    for i in range(math.ceil(end/length)):
        start=i*length;stop=min(end,start+length);support=mass=metal=0.
        while cursor<len(rows) and rows[cursor]['to_m']<=start:cursor+=1
        j=cursor
        while j<len(rows) and rows[j]['from_m']<stop:
            r=rows[j];overlap=max(0,min(stop,r['to_m'])-max(start,r['from_m']))
            support+=overlap;mass+=overlap*r['density'];metal+=overlap*r['density']*r['grade'];j+=1
        if support:result.append({'from_m':start,'to_m':stop,'grade':metal/mass,'density':mass/support,
                                  'support_m':support,'coverage':support/(stop-start),'weight_t_per_m2':mass})
    return result


def exposed_block_faces(blocks):
    """CPU surface extraction for a regular full-size grid; original IDs retained.

    Does not merge coplanar faces. Adaptive subblocks need a different adjacency
    structure and are rejected rather than incorrectly deleting their interfaces.
    """
    if not blocks:return []
    size=tuple(blocks[0][k] for k in ('dx','dy','dz'));occupied={};seen=set()
    for i,b in enumerate(blocks):
        if b.get('subblock_level',0) or any(b[k]!=v for k,v in zip(('dx','dy','dz'),size)):
            raise ValueError('Exposed faces зөвхөн ижил хэмжээтэй parent grid дэмжинэ.')
        key=tuple(b[k] for k in ('i','j','k'))
        if any(type(v) is not int for v in key) or key in seen:raise ValueError('Grid индекс буруу / давхардсан.')
        seen.add(key)
        if b.get('grade') is not None:occupied[key]=i
    directions=((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))
    result=[[] for _ in blocks]
    for key,i in occupied.items():
        result[i]=[face for face,offset in enumerate(directions) if tuple(a+b for a,b in zip(key,offset)) not in occupied]
    return result
