"""Planar fault barriers and centre-sampled adaptive cells, without fault throw."""
from copy import deepcopy
import math
import numpy as np
from .core import finite
from .spatial import search_basis
from .geometry import inside_polygon,validate_polygon


def validate_faults(faults):
    if not isinstance(faults,list) or len(faults)>8:
        raise ValueError('8 хүртэл planar fault дэмжинэ.')
    names=set()
    for fault in faults:
        name=fault.get('name')
        if not isinstance(name,str) or not name.strip() or name in names:raise ValueError('Fault нэр хоосон/давхардсан.')
        names.add(name)
        for key in ('point','normal'):
            a=np.asarray(fault[key],dtype=float)
            if a.shape!=(3,) or not np.isfinite(a).all():raise ValueError('Fault point/normal XYZ шаардлагатай.')
        if np.linalg.norm(fault['normal'])<1e-12:raise ValueError('Fault normal тэг байж болохгүй.')
    return faults


def fault_zone(point,faults):
    """Each infinite plane is a hard barrier. Points on a plane use its + side."""
    code=0
    for i,fault in enumerate(faults):
        normal=np.asarray(fault['normal'],dtype=float);normal=normal/np.linalg.norm(normal)
        if np.dot(np.asarray(point)-fault['point'],normal)>=-1e-9:code|=1<<i
    return code


def fault_patch(fault,extent):
    finite(extent)
    if extent<=0:raise ValueError('Fault patch хэмжээ эерэг байна.')
    validate_faults([fault]);n=np.array(fault['normal'],dtype=float);n/=np.linalg.norm(n)
    axis=np.eye(3)[np.argmin(abs(n))];u=np.cross(n,axis);u/=np.linalg.norm(u);v=np.cross(n,u)
    points=[(np.array(fault['point'])+extent*(a*u+b*v)).tolist() for a,b in ((-1,-1),(1,-1),(1,1),(-1,1))]
    return {'name':'Fault • '+fault['name'],'vertices':points,'faces':[[0,1,2],[0,2,3]],'role':'fault_guide'}


def adaptive_blocks(parents,bounds,angles,domain,faults,levels,cancel=None):
    """Octree sibling coalescing based on finest-centre polygon/fault labels.
    Boundary geometry is approximate at the selected resolution, never exact clipping.
    """
    if type(levels) is not int or not 0<=levels<=3:raise ValueError('Sub-block levels 0…3 байна.')
    validate_faults(faults)
    if domain:validate_polygon(domain['points'])
    if len(parents)*8**levels>200000:raise ValueError('Sub-block sampling 200000-аас их. Grid/level-ийг багасгана уу.')
    basis=search_basis(*angles);pivot=np.array(bounds[:3]);out=[]
    def classify(center):
        world=pivot+(center-pivot)@basis.T
        if domain and not inside_polygon(world[0],world[1],domain['points']):return None
        return fault_zone(world,faults)
    def node(center,dims,level,parent,path):
        if cancel and cancel():raise RuntimeError('Sub-block тооцоо цуцлагдлаа.')
        if level==levels:
            zone=classify(center)
            return [(center,dims,zone,level,path)]
        children=[]
        for child,(x,y,z) in enumerate(( (x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1))):
            children.extend(node(center+np.array([x,y,z])*dims/4,dims/2,level+1,parent,path+str(child)))
        if len(children)==8 and len({c[2] for c in children})==1:
            return [(center,dims,children[0][2],level,path)]
        return children
    for parent_index,parent in enumerate(parents):
        world=np.array([parent[a] for a in ('x','y','z')]);center=pivot+(world-pivot)@basis
        dims=np.array([parent[a] for a in ('dx','dy','dz')])
        for c,d,zone,level,path in node(center,dims,0,parent,''):
            if zone is None:continue
            block=deepcopy(parent);position=pivot+(c-pivot)@basis.T
            block.update(dict(zip(('x','y','z','dx','dy','dz'),position.tolist()+d.tolist())))
            block.update(block_id=f'{parent_index}:{path or "P"}',parent_id=parent_index,subblock_level=level,fault_zone=zone)
            out.append(block)
            if len(out)>50000:raise ValueError('50000-аас их sub-block үүссэн.')
    if not out:raise ValueError('Домэйн дотор sub-block алга.')
    return out
