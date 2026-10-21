"""Exploratory design primitives and feasible capacity scheduling, not pit optimization."""
import math
from .core import finite
from .geometry import validate_polygon

def pit_benches(center,bottom_radius,bottom_z,bench_height,benches,face_angle,berm,segments=64):
    finite(*center,bottom_radius,bottom_z,bench_height,face_angle,berm)
    if bottom_radius<=0 or bench_height<=0 or berm<0 or not 1<=benches<=100 or not 10<=face_angle<89 or not 8<=segments<=256:raise ValueError('Ил уурхайн bench тохиргоо буруу.')
    batter=bench_height/math.tan(math.radians(face_angle));vertices=[];faces=[];strings=[]
    # Concentric circular prototype: bench face and horizontal berm rings.
    rings=[(bottom_radius,bottom_z)]
    for i in range(benches):
        radius,z=rings[-1];rings.extend([(radius+batter,z+bench_height),(radius+batter+berm,z+bench_height)])
    for radius,z in rings:
        points=[[center[0]+radius*math.cos(2*math.pi*j/segments),center[1]+radius*math.sin(2*math.pi*j/segments),z] for j in range(segments)]
        strings.append({'name':f'Bench {z:.1f}','points':points,'closed':True});vertices.extend(points)
    for ring in range(len(rings)-1):
        for j in range(segments):
            a=ring*segments+j;b=ring*segments+(j+1)%segments;c=(ring+1)*segments+j;d=(ring+1)*segments+(j+1)%segments
            faces.extend([[a,b,d],[a,d,c]])
    return {'name':'Ил уурхай • тойрог bench prototype','vertices':vertices,'faces':faces,'role':'pit'},strings,{'overall_slope_deg':math.degrees(math.atan2(bench_height,batter+berm)),'face_angle_deg':face_angle,'berm_m':berm,'ramp_included':False,'engineering_review':False}

def underground_drive(start,end,width,height):
    finite(*start,*end,width,height)
    if width<=0 or height<=0:raise ValueError('Малталтын өргөн/өндөр эерэг байна.')
    dx,dy=end[0]-start[0],end[1]-start[1];horizontal=math.hypot(dx,dy)
    if horizontal<1e-6:raise ValueError('Босоо shaft энэ prototype-д дэмжихгүй.')
    nx,ny=-dy/horizontal*width/2,dx/horizontal*width/2;vertices=[]
    for p in (start,end):
        vertices.extend([[p[0]+nx,p[1]+ny,p[2]],[p[0]-nx,p[1]-ny,p[2]],[p[0]-nx,p[1]-ny,p[2]+height],[p[0]+nx,p[1]+ny,p[2]+height]])
    quads=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
    faces=[f for a,b,c,d in quads for f in ([a,b,c],[a,c,d])]
    return {'name':'Далд уурхай • шулуун малталт prototype','vertices':vertices,'faces':faces,'role':'drive'}, {'length_m':math.dist(start,end),'gradient_percent':(end[2]-start[2])/horizontal*100,'support_ventilation_geotech_checked':False}

def schedule(tasks,mining_capacity,processing_capacity,periods):
    """Greedy ready-set heuristic with strict previous-period precedence.
    Tasks are indivisible. Capacity violations never become silent partial tasks.
    """
    finite(mining_capacity,processing_capacity)
    if min(mining_capacity,processing_capacity)<=0 or not 1<=periods<=1200:raise ValueError('Capacity/periods буруу.')
    ids={t['id'] for t in tasks}
    if len(ids)!=len(tasks):raise ValueError('Task ID давхардсан.')
    for t in tasks:
        finite(t['tonnes'],t['process_tonnes'],t['value'])
        if t['tonnes']<=0 or not 0<=t['process_tonnes']<=t['tonnes'] or not set(t.get('predecessors',[]))<=ids or t['id'] in t.get('predecessors',[]):raise ValueError('Task тоо/precedence буруу.')
    # Topological cycle check independent from capacity infeasibility.
    checked=set()
    while len(checked)<len(tasks):
        ready=[t['id'] for t in tasks if t['id'] not in checked and set(t.get('predecessors',[]))<=checked]
        if not ready:raise ValueError('Precedence циклтэй байна.')
        checked.update(ready)
    completed=set();rows=[];pending=list(tasks)
    for period in range(1,periods+1):
        available=[t for t in pending if set(t.get('predecessors',[]))<=completed];available.sort(key=lambda t:(-t['value']/t['tonnes'],t['id']))
        mined=processed=0.;chosen=[]
        for t in available:
            if mined+t['tonnes']<=mining_capacity+1e-9 and processed+t['process_tonnes']<=processing_capacity+1e-9:
                mined+=t['tonnes'];processed+=t['process_tonnes'];chosen.append(t);rows.append({'period':period,**t})
        completed.update(t['id'] for t in chosen);pending=[t for t in pending if t['id'] not in completed]
        if not pending:break
    reasons=[]
    for t in pending:
        reason='capacity_per_task' if t['tonnes']>mining_capacity or t['process_tonnes']>processing_capacity else 'horizon_or_precedence'
        reasons.append({'id':t['id'],'reason':reason})
    return {'rows':rows,'unscheduled':reasons,'feasible_complete':not pending,'algorithm':'greedy value-per-tonne heuristic; not global optimization','mining_capacity':mining_capacity,'processing_capacity':processing_capacity,'periods':periods}

def tasks_from_blocks(model,density,cutoff):
    finite(density,cutoff)
    if density<=0 or cutoff<0:raise ValueError('Density/cutoff буруу.')
    from .spatial import model_basis
    import numpy as np
    if not np.allclose(model_basis(model),np.eye(3),atol=1e-10):
        raise ValueError('Эргэлттэй grid-д vertical precedence хараахан дэмжихгүй. World-axis model ашиглана уу.')
    blocks=model['blocks'];lookup={(b['i'],b['j'],b['k']):str(i) for i,b in enumerate(blocks)};result=[]
    for i,b in enumerate(blocks):
        tonnes=b['dx']*b['dy']*b['dz']*density;grade=b.get('grade');ore=grade is not None and grade>=cutoff
        above=lookup.get((b['i'],b['j'],b['k']+1))
        result.append({'id':str(i),'tonnes':tonnes,'process_tonnes':tonnes if ore else 0.,'value':tonnes*grade if ore else 0.,'predecessors':[above] if above else []})
    return result
