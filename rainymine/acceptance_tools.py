"""Explicit bounded engineering scenarios with mass balance and analytic fixtures.

These primitives do not implement a general fault solver or a dispatch simulator.
"""
from copy import deepcopy
import math
import numpy as np
from .core import finite
from .geometry import points_valid


def restore_planar_slip(points,faults):
    """Undo oldest-to-newest planar shear events, in reverse chronological order.

    Positive half-space moves by slip. Slip must lie in the plane, keeping the
    side test invariant for an isolated event. Intersecting network topology,
    deformation, finite fault tips and volume reconstruction are not solved.
    """
    xyz=np.asarray(points,dtype=np.float64).copy()
    if xyz.ndim!=2 or xyz.shape[1]!=3 or not np.isfinite(xyz).all() or len(faults)>8:raise ValueError('Invalid points/fault count')
    for fault in reversed(faults):
        p=np.asarray(fault['point'],dtype=float);n=np.array(fault['normal'],dtype=float,copy=True);slip=np.asarray(fault['slip'],dtype=float)
        if any(a.shape!=(3,) or not np.isfinite(a).all() for a in (p,n,slip)) or np.linalg.norm(n)<1e-12:raise ValueError('Invalid planar fault')
        n/=np.linalg.norm(n)
        if abs(float(np.dot(n,slip)))>1e-8*max(1.,np.linalg.norm(slip)):raise ValueError('Slip must be tangent to fault plane')
        positive=(xyz-p)@n>=0
        xyz[positive]-=slip
    return xyz


def classify_stratigraphy(model,normal,origin,contacts,names,faults=()):
    normal=np.asarray(normal,dtype=float);origin=np.asarray(origin,dtype=float)
    if normal.shape!=(3,) or origin.shape!=(3,) or not np.isfinite(normal).all() or not np.isfinite(origin).all() or np.linalg.norm(normal)<1e-12:raise ValueError('Invalid stratigraphic frame')
    if not contacts or len(contacts)>100 or len(names)!=len(contacts)+1 or len(set(names))!=len(names) or any(not isinstance(n,str) or not n.strip() or len(n)>100 for n in names):raise ValueError('Unique layer names and ordered contacts required')
    finite(*contacts)
    if any(a>=b for a,b in zip(contacts,contacts[1:])):raise ValueError('Contacts must be strictly ascending')
    blocks=model.get('blocks',[])
    if not blocks:raise ValueError('No blocks')
    restored=restore_planar_slip([[b[k] for k in ('x','y','z')] for b in blocks],faults)
    coordinate=(restored-origin)@(normal/np.linalg.norm(normal))
    indices=np.searchsorted(contacts,coordinate,side='right');result=deepcopy(model)
    for block,index in zip(result['blocks'],indices):
        for key in ('neighbors','kriging_efficiency','slope_of_regression','block_variance','estimation_pass'):block.pop(key,None)
        block.update(domain=names[int(index)],lithology=names[int(index)],grade=None,variance=None,status='needs_estimation')
    result.pop('run_sha256',None)
    result.pop('input_sha256',None)
    result['status_counts']={'needs_estimation':len(blocks)}
    report={'tool':'parallel-contact stratigraphy with ordered planar shear restoration','contacts':list(contacts),'names':list(names),'normal':normal.tolist(),'origin':origin.tolist(),'faults':deepcopy(list(faults)),'layer_counts':{n:int((indices==i).sum()) for i,n in enumerate(names)},'estimates_invalidated':True,'boundary':'centre classification; no exact solid clipping','engineering_review':False}
    result['stratigraphy']=deepcopy(report)
    return result,report


def estimate_stratigraphy(project,model,params,cancel=None):
    """Centre-support estimates with hard layer boundaries in restored coordinates."""
    import hashlib,json
    from .estimation import Estimator,sample_support
    frame=model.get('stratigraphy')
    if not frame:raise ValueError('Classify stratigraphy first')
    if params.get('faults') or params.get('discretization',[1,1,1])!=[1,1,1]:raise ValueError('This workflow uses restored-coordinate layer barriers and centre support only')
    # Validate/reclassify, clearing all previous scientific estimates.
    result,_=classify_stratigraphy(model,frame['normal'],frame['origin'],frame['contacts'],frame['names'],frame['faults'])
    samples=sample_support(project,params.get('composite_length',5),params.get('minimum_coverage',1.))
    if not samples:raise ValueError('No complete composite support')
    restored=restore_planar_slip([s['xyz'] for s in samples],frame['faults'])
    normal=np.asarray(frame['normal']);normal=normal/np.linalg.norm(normal)
    indices=np.searchsorted(frame['contacts'],(restored-frame['origin'])@normal,side='right')
    grouped={name:[] for name in frame['names']}
    for sample,xyz,index in zip(samples,restored,indices):grouped[frame['names'][int(index)]].append(dict(sample,xyz=xyz.tolist()))
    estimators={name:Estimator(rows,params) for name,rows in grouped.items() if rows}
    targets=restore_planar_slip([[b[k] for k in 'xyz'] for b in result['blocks']],frame['faults'])
    for block,target in zip(result['blocks'],targets):
        if cancel and cancel():raise RuntimeError('Stratigraphy estimation cancelled')
        estimator=estimators.get(block['domain'])
        block.update(estimator.predict(target) if estimator else {'grade':None,'variance':None,'neighbors':0,'status':'no_layer_support'})
    fingerprint={'samples':samples,'params':params,'stratigraphy':frame,'geometry':[[b.get(k) for k in ('x','y','z','dx','dy','dz')] for b in result['blocks']],'crs':project.crs_code,'grade_unit':project.grade_unit}
    result['run_sha256']=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,allow_nan=False).encode()).hexdigest()
    result['params']=deepcopy(params);result['support']='point at block centre; layer-isolated restored-coordinate estimation'
    result['status_counts']={status:sum(b['status']==status for b in result['blocks']) for status in {b['status'] for b in result['blocks']}}
    result['stratigraphy']['estimates_invalidated']=False
    return result


def stockpile_ledger(rows,grade_unit,processing_capacity,haul_capacity,initial=None):
    """Replay specified receipts/reclaims, perfectly mixed, receipts before reclaim.

    Capacity is checked at peak inventory, before reclaim. Haul capacity counts
    receipt plus reclaim tonnes. No automatic optimization or segregation model.
    """
    finite(processing_capacity,haul_capacity)
    if grade_unit not in ('%','g/t','ppm') or min(processing_capacity,haul_capacity)<=0 or len(rows)>10000:raise ValueError('Invalid capacities/unit/row count')
    factor=.01 if grade_unit=='%' else 1e-6
    piles={};received=0.;received_metal=0.;reclaimed=0.;reclaimed_metal=0.;seen=set();periods={};details=[]
    for name,item in (initial or {}).items():
        tonnes,grade=item['tonnes'],item['grade'];finite(tonnes,grade)
        if tonnes<0 or grade<0 or (grade_unit=='%' and grade>100):raise ValueError('Invalid initial stockpile')
        piles[name]=[tonnes,tonnes*grade*factor]
    initial_t=math.fsum(v[0] for v in piles.values());initial_m=math.fsum(v[1] for v in piles.values())
    for row in sorted(rows,key=lambda r:r['period']):
        period=row['period'];name=row['pile'];incoming=row['received_t'];grade=row['received_grade'];outgoing=row['reclaimed_t'];capacity=row['capacity_t']
        finite(incoming,grade,outgoing,capacity)
        if type(period)!=int or period<1 or not isinstance(name,str) or not name.strip() or (period,name) in seen or min(incoming,grade,outgoing)<0 or capacity<=0 or (grade_unit=='%' and grade>100):raise ValueError('Invalid or duplicate stockpile row')
        seen.add((period,name));inventory,metal=piles.get(name,[0.,0.]);inventory+=incoming;metal+=incoming*grade*factor
        if inventory>capacity+1e-8 or outgoing>inventory+1e-8:raise ValueError('Stockpile overflow or insufficient inventory')
        outgoing=min(outgoing,inventory)
        feed_grade=metal/inventory/factor if inventory>0 else None
        removed=metal*outgoing/inventory if inventory>0 else 0.
        inventory-=outgoing;metal-=removed;piles[name]=[inventory,metal]
        received+=incoming;received_metal+=incoming*grade*factor;reclaimed+=outgoing;reclaimed_metal+=removed
        period_total=periods.setdefault(period,{'processed_t':0.,'contained_metal_t':0.,'hauled_t':0.})
        period_total['processed_t']+=outgoing;period_total['contained_metal_t']+=removed;period_total['hauled_t']+=incoming+outgoing
        if period_total['processed_t']>processing_capacity+1e-8 or period_total['hauled_t']>haul_capacity+1e-8:raise ValueError('Period processing or haul capacity exceeded')
        details.append({'period':period,'pile':name,'received_t':incoming,'reclaimed_t':outgoing,'feed_grade':feed_grade,'closing_t':inventory,'closing_metal_t':metal})
    for item in periods.values():item['feed_grade']=item['contained_metal_t']/item['processed_t']/factor if item['processed_t'] else None
    closing=math.fsum(v[0] for v in piles.values());closing_m=math.fsum(v[1] for v in piles.values())
    return {'rows':details,'periods':[dict(period=k,**v) for k,v in sorted(periods.items())],'closing_piles':{name:{'tonnes':v[0],'contained_metal_t':v[1],'grade':v[1]/v[0]/factor if v[0] else None} for name,v in piles.items()},'tonnage_balance_error':initial_t+received-reclaimed-closing,'metal_balance_error_t':initial_m+received_metal-reclaimed_metal-closing_m,'grade_unit':grade_unit,'assumptions':'perfect mixing; receipts before reclaim; hauled tonnes=receipts+reclaims; no losses or scheduling optimization','engineering_review':False}


def segment_haul(points,speed_bands,payload_t,trucks,shift_hours,utilization,load_min,dump_min,queue_min,max_gradient=10.):
    """User-supplied signed-gradient speed bands, reversed for empty return."""
    from .planning import haul_route
    route=haul_route(points,1.,max_gradient)
    finite(payload_t,shift_hours,utilization,load_min,dump_min,queue_min)
    if not route['within_gradient_limit'] or payload_t<=0 or type(trucks)!=int or trucks<1 or shift_hours<=0 or not 0<utilization<=1 or min(load_min,dump_min,queue_min)<0:raise ValueError('Invalid route/fleet')
    bands=sorted(speed_bands,key=lambda b:b['min_gradient'])
    for i,band in enumerate(bands):
        finite(*[band[k] for k in ('min_gradient','max_gradient','loaded_kmh','empty_kmh')])
        if band['min_gradient']>=band['max_gradient'] or min(band['loaded_kmh'],band['empty_kmh'])<=0:raise ValueError('Invalid speed band')
        if i and abs(bands[i-1]['max_gradient']-band['min_gradient'])>1e-9:raise ValueError('Speed bands must be contiguous and non-overlapping')
    def speed(gradient,key):
        for i,b in enumerate(bands):
            if b['min_gradient']<=gradient<b['max_gradient'] or (i==len(bands)-1 and gradient==b['max_gradient']):return b[key]
        raise ValueError('Speed bands do not cover route gradients')
    loaded=0.;empty=0.;segments=[]
    for item in route['segments']:
        gradient=item['gradient_percent'];a=speed(gradient,'loaded_kmh');b=speed(-gradient,'empty_kmh')
        lm=item['length_m']/1000/a*60;em=item['length_m']/1000/b*60;loaded+=lm;empty+=em
        segments.append(dict(item,loaded_minutes=lm,empty_return_minutes=em,loaded_kmh=a,empty_kmh=b))
    cycle=loaded+empty+load_min+dump_min+queue_min
    return {'segments':segments,'loaded_minutes':loaded,'empty_minutes':empty,'cycle_minutes':cycle,'fleet_tonnes_per_shift':shift_hours*60*utilization/cycle*payload_t*trucks,'speed_bands':bands,'assumptions':'constant supplied speed within each gradient band; no acceleration, dispatch, traffic, braking or fuel simulation','engineering_review':False}
