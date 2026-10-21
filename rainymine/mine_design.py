"""Reviewable ramp, tunnel-network and ring geometry plus bounded stope selection."""
import math
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from .core import finite
from .spatial import search_basis,model_basis


def spiral_ramp(center,bottom_z,top_z,bottom_radius,width,gradient_percent,radial_growth=0.,step=2.):
    finite(*center,bottom_z,top_z,bottom_radius,width,gradient_percent,radial_growth,step)
    if len(center)!=2 or top_z<=bottom_z or width<=0 or bottom_radius<=width/2 or not 0<gradient_percent<=30 or radial_growth<0 or step<=0:
        raise ValueError('Ramp тохиргоо буруу.')
    target=(top_z-bottom_z)/(gradient_percent/100);points=[[center[0]+bottom_radius,center[1],bottom_z]];theta=0.;distance=0.;angles=[0.]
    while distance<target:
        if len(points)>=100000:raise ValueError('Ramp segment хязгаар хэтэрсэн.')
        radius=bottom_radius+radial_growth*theta/(2*math.pi);dt=min(.05,step/math.hypot(radius,radial_growth/(2*math.pi)))
        next_theta=theta+dt;r=bottom_radius+radial_growth*next_theta/(2*math.pi)
        next_xy=np.array([center[0]+r*math.cos(next_theta),center[1]+r*math.sin(next_theta)])
        previous=np.array(points[-1][:2]);length=float(np.linalg.norm(next_xy-previous))
        if length<=0:raise ValueError('Ramp advance буруу.')
        fraction=min(1.,(target-distance)/length);next_xy=previous+fraction*(next_xy-previous);distance+=fraction*length
        points.append([*next_xy.tolist(),bottom_z+distance*gradient_percent/100]);angles.append(theta+fraction*dt);theta=next_theta
    vertices=[]
    for i,(p,angle) in enumerate(zip(points,angles)):
        a=np.array(points[max(0,i-1)][:2]);b=np.array(points[min(len(points)-1,i+1)][:2]);tangent=b-a;tangent/=np.linalg.norm(tangent)
        normal=np.array([-tangent[1],tangent[0]])*width/2
        vertices.extend([[p[0]+normal[0],p[1]+normal[1],p[2]],[p[0]-normal[0],p[1]-normal[1],p[2]]])
    faces=[]
    for i in range(len(points)-1):faces.extend([[2*i,2*i+1,2*i+3],[2*i,2*i+3,2*i+2]])
    mesh={'name':'Спираль ramp surface','vertices':vertices,'faces':faces,'role':'ramp'}
    line={'name':'Ramp centreline','points':points,'closed':False}
    return mesh,line,{'horizontal_length_m':distance,'length_3d_m':distance*math.sqrt(1+(gradient_percent/100)**2),
                      'gradient_percent':gradient_percent,'width_m':width,'turns':angles[-1]/(2*math.pi),
                      'minimum_plan_radius_m':bottom_radius,'pit_wall_collision_checked':False,'engineering_review':False}


def drill_ring(origin,azimuth,dip,fan_from,fan_to,count,length,roll=0):
    finite(*origin,azimuth,dip,fan_from,fan_to,length,roll)
    if len(origin)!=3 or type(count) is not int or not 2<=count<=256 or length<=0 or not -180<=fan_from<fan_to<=180:
        raise ValueError('Ring тохиргоо буруу.')
    basis=search_basis(azimuth,dip,roll);holes=[]
    for i,angle in enumerate(np.linspace(fan_from,fan_to,count)):
        direction=math.cos(math.radians(angle))*basis[:,0]+math.sin(math.radians(angle))*basis[:,1]
        end=(np.asarray(origin)+length*direction).tolist()
        holes.append({'name':f'Ring hole {i+1}','points':[list(origin),end],'closed':False,'length_m':length,'fan_angle':float(angle)})
    return holes


def tunnel_network(points,width,height):
    from .planning import underground_drive
    from .cad import boolean_mesh
    if not 2<=len(points)<=50:raise ValueError('Drive polyline 2…50 points байна.')
    result=None
    for a,b in zip(points,points[1:]):
        segment,report=underground_drive(a,b,width,height)
        result=segment if result is None else boolean_mesh(result,segment,'union')[0]
    result['name']='Далд малталтын сүлжээ';result['role']='drive'
    return result


def stope_boxes(model,cells,density,unit_value,mining_cost,seconds=20):
    """MILP maximum-value non-overlapping FULL regular-grid boxes.

    A finite candidate-shape optimisation, not commercial MSO wall-angle/dilution
    equivalence. Units: unit_value per project grade-unit*tonne; cost per tonne.
    """
    finite(density,unit_value,mining_cost,seconds)
    if min(density,seconds)<=0 or min(unit_value,mining_cost)<0 or len(cells)!=3 or any(type(v) is not int or v<1 for v in cells):raise ValueError('Stope тохиргоо буруу.')
    if not np.allclose(model_basis(model),np.eye(3),atol=1e-10) or model.get('subblock_levels',0):raise ValueError('Stope box зөвхөн world-axis parent grid дэмжинэ.')
    blocks=model['blocks']
    if not 1<=len(blocks)<=5000:raise ValueError('Stope 1…5000 блок байна.')
    if math.prod(cells)>len(blocks):raise ValueError('Stope хайрцаг нийт блокоос олон нүдтэй байна.')
    size=tuple(blocks[0][k] for k in ('dx','dy','dz'));lookup={}
    for i,b in enumerate(blocks):
        if b.get('grade') is None or b.get('subblock_level',0) or tuple(b[k] for k in ('dx','dy','dz'))!=size:raise ValueError('Ижил хэмжээтэй, үнэлсэн parent blocks шаардлагатай.')
        finite(b['grade'],b['dx'],b['dy'],b['dz'])
        key=tuple(b[k] for k in ('i','j','k'))
        if key in lookup:raise ValueError('Grid индекс давхардсан.')
        lookup[key]=i
    candidates=[];values=[]
    for low in sorted(lookup):
        ids=[lookup.get((low[0]+i,low[1]+j,low[2]+k)) for i in range(cells[0]) for j in range(cells[1]) for k in range(cells[2])]
        if any(i is None for i in ids):continue
        value=sum(blocks[i]['dx']*blocks[i]['dy']*blocks[i]['dz']*density*(blocks[i]['grade']*unit_value-mining_cost) for i in ids)
        if value>0:candidates.append(ids);values.append(value)
        if len(candidates)>3000:raise ValueError('Stope candidates >3000; grid / dimensions-ийг өөрчилнө үү.')
    if not candidates:return {'selected':[],'objective':0.,'optimal':True,'candidate_count':0,'algorithm':'non-overlapping regular boxes MILP'}
    matrix=lil_matrix((len(blocks),len(candidates)),dtype=float)
    for j,ids in enumerate(candidates):matrix[ids,j]=1.
    solution=milp(-np.asarray(values),integrality=np.ones(len(candidates)),bounds=Bounds(0,1),constraints=LinearConstraint(matrix.tocsr(),-np.inf,1.),options={'time_limit':seconds,'mip_rel_gap':.001})
    if solution.x is None:raise ValueError('Stope solver incumbent алга: '+solution.message)
    chosen=[i for i,x in enumerate(solution.x) if x>.5];used=[b for i in chosen for b in candidates[i]]
    if len(used)!=len(set(used)):raise ValueError('Stope overlap residual илэрлээ.')
    return {'selected':[{'candidate':i,'block_indices':candidates[i],'value':values[i]} for i in chosen],
            'objective':sum(values[i] for i in chosen),'optimal':solution.status==0,'mip_gap':float(solution.mip_gap),
            'candidate_count':len(candidates),'algorithm':'non-overlapping regular boxes MILP','engineering_review':False}
