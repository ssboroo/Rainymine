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
    if model.get('subblock_levels',0):raise ValueError('Sub-block precedence хараахан дэмжихгүй. Parent grid ашиглана уу.')
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


def haul_route(points,width,max_gradient_percent=10.):
    """Validate a straight-segment centreline, not a road alignment design."""
    from .geometry import points_valid
    points_valid(points,2);finite(width,max_gradient_percent)
    if width<=0 or max_gradient_percent<=0:raise ValueError('Road width / maximum gradient эерэг байна.')
    segments=[]
    for i,(a,b) in enumerate(zip(points,points[1:])):
        horizontal=math.hypot(b[0]-a[0],b[1]-a[1])
        if horizontal<1e-9:raise ValueError('Road segment босоо/тэг урттай байна.')
        gradient=100*(b[2]-a[2])/horizontal
        segments.append({'segment':i+1,'length_m':math.dist(a,b),'gradient_percent':gradient,
                         'within_gradient_limit':abs(gradient)<=max_gradient_percent+1e-9})
    return {'length_m':sum(s['length_m'] for s in segments),'width_m':width,'max_gradient_percent':max_gradient_percent,
            'within_gradient_limit':all(s['within_gradient_limit'] for s in segments),'segments':segments,
            'curvature_superelevation_geotechnics_checked':False}


def haul_capacity(route,payload_t,trucks,loaded_kmh,empty_kmh,load_min,dump_min,queue_min,shift_hours,utilization):
    finite(payload_t,loaded_kmh,empty_kmh,load_min,dump_min,queue_min,shift_hours,utilization)
    if (payload_t<=0 or type(trucks) is not int or not 1<=trucks<=10000 or min(loaded_kmh,empty_kmh,shift_hours)<=0
            or min(load_min,dump_min,queue_min)<0 or not 0<utilization<=1):raise ValueError('Haul fleet тохиргоо буруу.')
    if not route['within_gradient_limit']:raise ValueError('Замын gradient limit зөрчсөн. Fleet тооцоог зогсоолоо.')
    length=route['length_m'];finite(length)
    if length<=0:raise ValueError('Замын урт эерэг байна.')
    cycle=length/1000/loaded_kmh*60+length/1000/empty_kmh*60+load_min+dump_min+queue_min
    cycles=shift_hours*60*utilization/cycle
    return {'route_length_m':length,'cycle_minutes':cycle,'cycles_per_truck':cycles,
            'payload_t':payload_t,'trucks':trucks,'shift_hours':shift_hours,'utilization':utilization,
            'loaded_kmh':loaded_kmh,'empty_kmh':empty_kmh,'load_min':load_min,'dump_min':dump_min,'queue_min':queue_min,
            'fleet_tonnes_per_shift':cycles*payload_t*trucks,'capacity_model':'continuous average cycles; constant speeds; no dispatch simulation'}


def optimize_schedule(tasks,mining_capacity,processing_capacity,periods,discount_rate=.1,time_limit=10.):
    """Optional-task discounted-value MILP with indivisible tasks and precedence.
    Optimality is claimed only within the solver's reported gap/tolerances.
    """
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    finite(discount_rate,time_limit)
    if discount_rate<0 or not 0<time_limit<=60 or not tasks:raise ValueError('Discount/time limit/tasks буруу.')
    if type(periods) is not int or len(tasks)*periods>12000:raise ValueError('MILP 12000 хүртэл binary variable дэмжинэ.')
    schedule(tasks,mining_capacity,processing_capacity,periods) # shared validation, including cycles
    if sum(len(t.get('predecessors',[])) for t in tasks)*periods*(periods+1)//2>1000000:
        raise ValueError('MILP precedence matrix хэт том. Horizon/tasks-ийг багасгана уу.')
    n=len(tasks);ids={t['id']:i for i,t in enumerate(tasks)};row_ids=[];columns=[];data=[];low=[];high=[]
    def constraint(entries,lo,hi):
        row=len(low)
        for col,value in entries:row_ids.append(row);columns.append(col);data.append(value)
        low.append(lo);high.append(hi)
    for i in range(n):constraint([(i*periods+p,1.) for p in range(periods)],0.,1.)
    for p in range(periods):
        constraint([(i*periods+p,t['tonnes']) for i,t in enumerate(tasks)],0.,mining_capacity)
        constraint([(i*periods+p,t['process_tonnes']) for i,t in enumerate(tasks)],0.,processing_capacity)
    for i,t in enumerate(tasks):
        for predecessor in t.get('predecessors',[]):
            j=ids[predecessor]
            for p in range(periods):
                constraint([(i*periods+p,1.)]+[(j*periods+q,-1.) for q in range(p)],-np.inf,0.)
    matrix=coo_matrix((data,(row_ids,columns)),shape=(len(low),n*periods)).tocsc()
    objective=np.array([-t['value']*np.exp(-p*np.log1p(discount_rate)) for t in tasks for p in range(periods)])
    solution=milp(objective,integrality=np.ones(n*periods),bounds=Bounds(0,1),
                  constraints=LinearConstraint(matrix,low,high),options={'time_limit':time_limit,'mip_rel_gap':1e-6})
    if solution.x is None:
        return {'rows':[],'unscheduled':[{'id':t['id'],'reason':'no_solver_incumbent'} for t in tasks],
                'solution_status':'no_incumbent','solver_message':solution.message,'optimal':False}
    rounded=np.rint(solution.x)
    if not np.allclose(rounded,solution.x,atol=1e-5):raise ValueError('MILP incumbent бүхэл биш.')
    activities=matrix@rounded
    if np.any(activities<np.asarray(low)-1e-5) or np.any(activities>np.asarray(high)+1e-5):raise ValueError('MILP incumbent capacity/precedence шалгалт унав.')
    rows=[{'period':p+1,**t} for i,t in enumerate(tasks) for p in range(periods) if rounded[i*periods+p]>.5]
    rows.sort(key=lambda r:(r['period'],r['id']));selected={r['id'] for r in rows}
    return {'rows':rows,'unscheduled':[{'id':t['id'],'reason':'not_selected_by_objective_or_constraints'} for t in tasks if t['id'] not in selected],
            'discounted_objective':float(-objective@rounded),'discount_rate':discount_rate,
            'optimal':solution.status==0,'solution_status':'optimal_within_solver_tolerance' if solution.status==0 else 'feasible_incumbent',
            'mip_gap':float(solution.mip_gap),'solver_message':solution.message,'algorithm':'SciPy HiGHS MILP; optional tasks; strict previous-period precedence',
            'mining_capacity':mining_capacity,'processing_capacity':processing_capacity,'periods':periods}


def economic_tasks(model,density,cutoff,grade_unit,metal_price_per_t,mining_cost_per_t,processing_cost_per_t,recovery,haul_cost_per_t=0.):
    finite(metal_price_per_t,mining_cost_per_t,processing_cost_per_t,recovery,haul_cost_per_t)
    if grade_unit not in ('%','g/t','ppm') or metal_price_per_t<=0 or min(mining_cost_per_t,processing_cost_per_t,haul_cost_per_t)<0 or not 0<recovery<=1:
        raise ValueError('Economic units / costs / recovery буруу.')
    tasks=tasks_from_blocks(model,density,cutoff);factor=.01 if grade_unit=='%' else 1e-6
    for task,block in zip(tasks,model['blocks']):
        revenue=task['process_tonnes']*(block.get('grade') or 0)*factor*metal_price_per_t*recovery
        task['value']=revenue-task['tonnes']*(mining_cost_per_t+haul_cost_per_t)-task['process_tonnes']*processing_cost_per_t
    return tasks
