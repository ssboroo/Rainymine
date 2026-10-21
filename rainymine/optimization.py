"""Undiscounted economic maximum closure with explicit block precedences."""
import math
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from .core import finite


def maximum_closure(values, precedences, time_limit=30):
    """Select block child only if parent selected; exact MILP, no currency rounding."""
    values=np.asarray(values,dtype=float);n=len(values)
    if values.shape!=(n,) or not 1<=n<=5000 or not np.isfinite(values).all():
        raise ValueError('Оновчлолд 1–5000 finite блок шаардлагатай.')
    finite(time_limit)
    if not 0<time_limit<=120:raise ValueError('Solver хугацаа 0–120 секунд байна.')
    edges=sorted(set(tuple(e) for e in precedences))
    if len(edges)>250000:raise ValueError('Precedence 250000-аас их.')
    for child,parent in edges:
        if type(child)!=int or type(parent)!=int or not 0<=child<n or not 0<=parent<n or child==parent:
            raise ValueError('Precedence индекс буруу.')
    rows=[];cols=[];data=[]
    for i,(child,parent) in enumerate(edges):
        rows.extend([i,i]);cols.extend([child,parent]);data.extend([1.,-1.])
    matrix=coo_matrix((data,(rows,cols)),shape=(len(edges),n)).tocsc()
    constraints=LinearConstraint(matrix,-np.inf,0) if edges else None
    # Normalization improves the numerical conditioning without changing the optimum.
    scale=max(1.,float(np.max(np.abs(values))))
    result=milp(-values/scale,integrality=np.ones(n),bounds=Bounds(0,1),constraints=constraints,
                options={'time_limit':float(time_limit),'mip_rel_gap':0.})
    if result.status!=0 or result.x is None:
        raise ValueError('Оновчлол баталгаатай optimum-д хүрсэнгүй. Блокийн тоог багасгана уу.')
    selected=[i for i,x in enumerate(result.x) if x>.5];chosen=set(selected)
    if any(c in chosen and p not in chosen for c,p in edges):raise RuntimeError('Solver precedence зөрчсөн.')
    return {'selected_indices':selected,'net_value':float(values[selected].sum()),
            'algorithm':'binary maximum closure / HiGHS MILP','optimal':True,
            'precedence_count':len(edges),'discounted':False,'scheduling_included':False}


def economic_pit(model,density,price_per_grade_tonne,recovery,mining_cost,processing_cost,slope=45):
    """Uniform complete rectangular parent blocks; conservative square slope stencil.

    Price is currency per (one project grade-unit * tonne). No inferred %/g/t conversion.
    Unknown grades are rejected; the grid extent is a hard external boundary.
    """
    finite(density,price_per_grade_tonne,recovery,mining_cost,processing_cost,slope)
    if density<=0 or price_per_grade_tonne<0 or not 0<=recovery<=1 or min(mining_cost,processing_cost)<0 or not 15<=slope<=80:
        raise ValueError('Эдийн засаг / налуугийн тохиргоо буруу.')
    from .spatial import model_basis
    if model.get('subblock_levels',0) or not np.allclose(model_basis(model),np.eye(3),atol=1e-10):
        raise ValueError('Pit optimizer нь world-axis parent grid шаарддаг; rotated/sub-block дэмжихгүй.')
    blocks=model['blocks']
    if not 1<=len(blocks)<=5000:raise ValueError('Pit optimizer 5000 хүртэл блок дэмжинэ.')
    size=np.asarray([blocks[0][a] for a in ('dx','dy','dz')],dtype=float)
    if not np.isfinite(size).all() or (size<=0).any():raise ValueError('Блокийн хэмжээ буруу.')
    lookup={};origin=None
    for index,b in enumerate(blocks):
        key=tuple(b[a] for a in ('i','j','k'))
        if any(type(v)!=int or v<0 for v in key) or key in lookup:raise ValueError('Grid индекс буруу / давхардсан.')
        if not np.allclose([b[a] for a in ('dx','dy','dz')],size,rtol=0,atol=1e-7):raise ValueError('Ижил хэмжээтэй бүтэн parent блок шаардлагатай; sub-block дэмжихгүй.')
        xyz=np.array([b[a] for a in ('x','y','z')],dtype=float)
        if not np.isfinite(xyz).all():raise ValueError('Grid координат буруу.')
        base=xyz-np.array(key)*size
        if origin is None:origin=base
        if not np.allclose(base,origin,rtol=0,atol=1e-6):raise ValueError('Grid геометр индексийн байрлалтай тохирохгүй.')
        if b.get('grade') is None:raise ValueError('Тооцоогүй агуулгыг хаягдал гэж үзэхгүй. Бүх блокийн агуулга шаардлагатай.')
        finite(b['grade'])
        if b['grade']<0:raise ValueError('Сөрөг grade-ийг эх модель дээр шийднэ үү.')
        lookup[key]=index
    counts=[max(k[a] for k in lookup)+1 for a in range(3)]
    if math.prod(counts)!=len(blocks):raise ValueError('Pit optimizer бүтэн тэгш өнцөгт grid шаарддаг.')
    radius=size[2]/math.tan(math.radians(slope));nx=math.ceil(radius/size[0]-1e-10);ny=math.ceil(radius/size[1]-1e-10)
    if len(blocks)*(2*nx+1)*(2*ny+1)>250000:raise ValueError('Налуугийн precedence хэт олон; grid-ийг өөрчилнө үү.')
    edges=[]
    for (i,j,k),index in lookup.items():
        if k==counts[2]-1:continue
        for di in range(-nx,nx+1):
            for dj in range(-ny,ny+1):
                parent=lookup.get((i+di,j+dj,k+1))
                if parent is not None:edges.append((index,parent))
    tonnes=float(np.prod(size)*density);values=[];ore=[]
    for b in blocks:
        margin=b['grade']*price_per_grade_tonne*recovery-processing_cost
        ore.append(margin>0);values.append(tonnes*(max(0.,margin)-mining_cost))
    result=maximum_closure(values,edges)
    selected=result['selected_indices']
    result.update({'density_t_m3':density,'price_per_grade_tonne':price_per_grade_tonne,'recovery':recovery,
                   'mining_cost_per_tonne':mining_cost,'processing_cost_per_tonne':processing_cost,
                   'slope_degrees':slope,'slope_rule':'conservative square next-level stencil',
                   'stencil_half_width_cells':[nx,ny],'boundary':'hard model extent; external stripping excluded',
                   'mined_tonnes':tonnes*len(selected),'processed_tonnes':tonnes*sum(ore[i] for i in selected),
                   'selected_blocks':len(selected),'engineering_review':False})
    return result


def pit_mesh(model,indices):
    """Exposed voxel faces only; retained as an independent scenario mesh."""
    blocks=model['blocks'];selected={tuple(blocks[i][a] for a in ('i','j','k')) for i in indices}
    vertices=[];faces=[];ids={}
    quads=[(-1,0,0,[0,4,6,2]),(1,0,0,[1,3,7,5]),(0,-1,0,[0,1,5,4]),
           (0,1,0,[2,6,7,3]),(0,0,-1,[0,2,3,1]),(0,0,1,[4,5,7,6])]
    for index in indices:
        b=blocks[index];key=tuple(b[a] for a in ('i','j','k'))
        corners=[(b['x']+(x-.5)*b['dx'],b['y']+(y-.5)*b['dy'],b['z']+(z-.5)*b['dz'])
                 for z in (0,1) for y in (0,1) for x in (0,1)]
        for di,dj,dk,q in quads:
            if (key[0]+di,key[1]+dj,key[2]+dk) in selected:continue
            face=[]
            for c in q:
                point=corners[c]
                if point not in ids:ids[point]=len(vertices);vertices.append(list(point))
                face.append(ids[point])
            a,b1,c,d=face;faces.extend([[a,b1,c],[a,c,d]])
    if not faces:raise ValueError('Эдийн засгийн ашигтай pit сонгогдоогүй.')
    return {'name':'Economic pit • voxel envelope','role':'optimized_pit','vertices':vertices,'faces':faces}
