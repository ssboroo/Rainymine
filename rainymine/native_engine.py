"""Checked native kernels. Every result records backend and numerical limits."""
import math
import numpy as np


def engine():
    try:import rainymine_core
    except ImportError as error:raise ValueError('Rust/C++ engine unavailable. Install a native-enabled RAINYMINE build.') from error
    return rainymine_core


def pseudoflow(values,precedences=(),grid=None,value_scale=1_000_000.,cancel=None):
    v=np.asarray(values,dtype=float)
    if v.ndim!=1 or not 1<=len(v)<=10_000_000 or not np.isfinite(v).all() or not math.isfinite(value_scale) or value_scale<=0:raise ValueError('Invalid pseudoflow values / scale')
    if np.abs(v).sum()*value_scale>=2**61:raise ValueError('int64 economic sum overflow; reduce explicit value scale')
    if cancel and cancel():raise RuntimeError('Pseudoflow cancelled')
    raw_edges=np.asarray(precedences)
    if raw_edges.size and raw_edges.dtype.kind not in 'iu':raise ValueError('Precedence indices must be integers')
    edges=raw_edges.astype(np.int64).reshape(-1,2)
    if len(edges)>20_000_000:raise ValueError('Explicit graph arc budget exceeded')
    if len(edges) and (np.any(edges<0) or np.any(edges>=len(v)) or np.any(edges[:,0]==edges[:,1])):raise ValueError('Invalid precedence indices')
    rounded=np.rint(v*value_scale).astype(np.int64)
    selected=np.asarray(engine().closure(rounded,edges,grid),dtype=bool)
    if cancel and cancel():raise RuntimeError('Pseudoflow cancelled')
    if len(edges) and np.any(selected[edges[:,0]]&~selected[edges[:,1]]):raise RuntimeError('Pseudoflow precedence violation')
    return selected,{'algorithm':'MineFlow pseudoflow / native C++ via Rust PyO3','engine_version':engine().ENGINE_VERSION,
        'mineflow_commit':engine().MINEFLOW_COMMIT,'selected_blocks':int(selected.sum()),'net_value':float(v[selected].sum()),
        'integer_optimum':True,'value_scale':value_scale,'objective_loss_bound':len(v)/value_scale,
        'total_rounding_absolute_error':float(np.abs(v-rounded/value_scale).sum()),
        'rounding':'nearest integer; loss bound relative to unrounded optimum',
        'engineering_review':False,'discounted':False}


def grid_pseudoflow(values,counts,size,slope=45,value_scale=1_000_000.,cancel=None):
    if len(counts)!=3 or any(type(n)!=int or n<=0 for n in counts) or math.prod(counts)!=len(values):raise ValueError('Incomplete regular grid')
    size=np.asarray(size,dtype=float)
    if size.shape!=(3,) or not np.isfinite(size).all() or min(size)<=0 or not math.isfinite(slope) or not 15<=slope<=80:raise ValueError('Invalid grid size/slope')
    radius=size[2]/math.tan(math.radians(slope));rx=math.ceil(radius/size[0]-1e-10);ry=math.ceil(radius/size[1]-1e-10)
    selected,report=pseudoflow(values,grid=(*counts,rx,ry),value_scale=value_scale,cancel=cancel)
    # Validate implicit arcs without materializing the full graph.
    cube=selected.reshape(counts[::-1])
    for di in range(-rx,rx+1):
        for dj in range(-ry,ry+1):
            x0=max(0,-di);x1=min(counts[0],counts[0]-di);y0=max(0,-dj);y1=min(counts[1],counts[1]-dj)
            if x0<x1 and y0<y1 and np.any(cube[:-1,y0:y1,x0:x1]&~cube[1:,y0+dj:y1+dj,x0+di:x1+di]):raise RuntimeError('Implicit slope precedence violated')
    report.update(slope_degrees=slope,stencil_half_width_cells=[rx,ry],boundary='hard model extent; external stripping excluded')
    return selected,report


def rust_predictions(estimator,points,cancel=None,progress=None):
    """Parallel spherical point-support OK; exact Python neighbourhood policy.

    Fault barriers, caps, search ellipsoid, per-hole limits and covariance ranges
    are resolved before passing owned numeric arrays to native Rayon workers.
    """
    if estimator.method!='kriging' or estimator.variogram_model!='spherical':raise ValueError('Rust backend currently requires ordinary kriging / spherical variogram')
    points=np.asarray(points,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Invalid targets')
    original_points=points
    if estimator.restore_fault_slip:points=estimator.fault_network.restore(points,cancel)
    kernel=engine();xyz=estimator.xyz
    if estimator.covariance_ranges is None:
        coords=xyz-estimator.origin;targets=points-estimator.origin;range_m=estimator.variogram[2]
    else:
        coords=((xyz-estimator.origin)@estimator.covariance_basis)/estimator.covariance_ranges
        targets=((points-estimator.origin)@estimator.covariance_basis)/estimator.covariance_ranges;range_m=1.
    output=[]
    batch_size=min(512,max(1,2_000_000//len(xyz)))
    for start in range(0,len(points),batch_size):
        if cancel and cancel():raise RuntimeError('Rust kriging cancelled')
        chunk=points[start:start+batch_size];zones=estimator.fault_network.classify(original_points[start:start+len(chunk)],cancel)
        candidates=estimator.tree.query_ball_point(((chunk-estimator.origin)@estimator.basis)/estimator.radii,1.,workers=-1)
        ids=np.full((len(chunk),estimator.k),-1,dtype=np.int64);counts=[];supported=[]
        for j,(point,candidate) in enumerate(zip(chunk,candidates)):
            candidates_sorted=sorted((i for i in candidate if estimator.zones[i]==zones[j]),key=lambda i:(float(np.linalg.norm(((xyz[i]-point)@estimator.basis)/estimator.radii)),i))
            chosen=[];holes={}
            for i in candidates_sorted:
                hole=estimator.samples[i]['hole_id']
                if holes.get(hole,0)>=estimator.max_per_hole:continue
                chosen.append(i);holes[hole]=holes.get(hole,0)+1
                if len(chosen)==estimator.k:break
            counts.append(len(chosen));good=len(chosen)>=estimator.minimum and len(holes)>=estimator.minimum_holes;supported.append(good)
            if good:ids[j,:len(chosen)]=chosen
        result=np.asarray(kernel.ok_batch(np.ascontiguousarray(coords),np.ascontiguousarray(estimator.values),np.ascontiguousarray(targets[start:start+len(chunk)]),ids,*estimator.variogram[:2],range_m))
        if cancel and cancel():raise RuntimeError('Rust kriging cancelled')
        for j,row in enumerate(result):
            status=int(row[4]);record={'grade':None,'variance':None,'neighbors':counts[j],'status':'insufficient_support' if not supported[j] else 'singular_kriging_system' if status==2 else 'invalid_variance'}
            if status==0:
                exact=any(np.linalg.norm(xyz[i]-chunk[j])<1e-9 for i in ids[j] if i>=0)
                record.update(grade=float(row[0]),variance=float(row[1]),kriging_efficiency=float(row[2]),slope_of_regression=float(row[3]) if np.isfinite(row[3]) else None,block_variance=sum(estimator.variogram[:2]),status='exact_sample' if exact else 'estimated')
            output.append(record)
        if progress:progress(start+len(chunk),len(points))
    return output
