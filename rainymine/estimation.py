"""Experimental deterministic point-support estimation, not classified resources.
Ordinary kriging uses a spherical semivariogram in an augmented linear system.
Optional midpoint quadrature approximates block support with a common neighbourhood.
Composite samples remain point supports at their midpoints; independent validation pending.
"""
import math
import hashlib
import json
from dataclasses import asdict
from copy import deepcopy
import numpy as np
from scipy.spatial import cKDTree
from .core import finite,Trajectory,composite_assays
from .geometry import inside_polygon,validate_polygon
from .spatial import search_basis
from .domains import validate_faults,fault_zone,adaptive_blocks


def sample_support(project,length=5,minimum_coverage=1.):
    finite(minimum_coverage)
    if not 0<minimum_coverage<=1:raise ValueError('Coverage 0–1 мужид байна.')
    grouped={}
    for s in project.surveys:grouped.setdefault(s.hole_id,[]).append(s)
    traces={h.hole_id:Trajectory(h,grouped.get(h.hole_id,[])) for h in project.collars}
    rows=[]
    for r in composite_assays(project,length):
        if r['coverage']+1e-10<minimum_coverage:continue
        p=traces[r['hole_id']].at((r['from_m']+r['to_m'])/2)
        rows.append({'hole_id':r['hole_id'],'xyz':p,'grade':r['grade'],'support_m':r['support_m']})
    return rows


def gamma_spherical(distance,nugget,partial_sill,range_m):
    finite(nugget,partial_sill,range_m)
    if nugget<0 or partial_sill<=0 or range_m<=0:raise ValueError('Variogram nugget ≥ 0, partial sill > 0, range > 0 байна.')
    d=np.asarray(distance,dtype=float);h=np.minimum(d/range_m,1.)
    return np.where(d<=1e-12,0.,nugget+partial_sill*(1.5*h-.5*h**3))


def gamma_model(distance,nugget,partial_sill,range_m,model='spherical'):
    if model=='spherical':return gamma_spherical(distance,nugget,partial_sill,range_m)
    if model not in ('exponential','gaussian'):raise ValueError('Variogram model буруу.')
    finite(nugget,partial_sill,range_m)
    if nugget<0 or partial_sill<=0 or range_m<=0:raise ValueError('Variogram параметр буруу.')
    d=np.asarray(distance,dtype=float)
    if not np.isfinite(d).all() or np.any(d<0):raise ValueError('Variogram зай буруу.')
    h=d/range_m
    return np.where(d<=1e-12,0.,nugget+partial_sill*(-np.expm1(-3*(h if model=='exponential' else h*h))))


class Estimator:
    def __init__(self,samples,params):
        if not samples:raise ValueError('Тооцох сорьц алга. Композитын coverage-ийг шалгана уу.')
        self.samples=samples;self.params=deepcopy(params)
        self.faults=deepcopy(params.get('faults',[]));validate_faults(self.faults)
        self.zones=[fault_zone(s['xyz'],self.faults) for s in samples]
        self.xyz=np.asarray([r['xyz'] for r in samples],dtype=float);self.values=np.asarray([r['grade'] for r in samples],dtype=float)
        if not np.isfinite(self.xyz).all() or not np.isfinite(self.values).all():raise ValueError('Sample утга буруу.')
        if self.xyz.shape!=(len(samples),3):raise ValueError('Sample XYZ бүтэц буруу.')
        self.top_cut=params.get('top_cut')
        if self.top_cut is not None:
            finite(self.top_cut)
            if self.top_cut<=0:raise ValueError('Top cut > 0 байна.')
            self.values=np.minimum(self.values,self.top_cut)
        self.capped_count=int(sum(r['grade']>self.top_cut for r in samples)) if self.top_cut is not None else 0
        self.max_per_hole=int(params.get('max_per_hole',64));self.minimum_holes=int(params.get('minimum_holes',1))
        if not 1<=self.max_per_hole<=64 or not 1<=self.minimum_holes<=64:raise ValueError('Hole хязгаар 1…64 байна.')
        if len(np.unique(self.xyz,axis=0))!=len(self.xyz):raise ValueError('Ижил координаттай композит байна. Давхардлыг эх өгөгдөл дээр шийднэ үү.')
        radii=np.asarray(params.get('radii',[200,200,100]),dtype=float)
        if radii.shape!=(3,) or not np.isfinite(radii).all() or (radii<=0).any():raise ValueError('Search ellipsoid-ийн 3 радиус эерэг байна.')
        angles=params.get('search_angles',[90.,0.,0.])
        if len(angles)!=3:raise ValueError('Search azimuth/dip/roll шаардлагатай.')
        self.basis=search_basis(*angles)
        self.radii=radii;self.origin=self.xyz[0];self.tree=cKDTree(((self.xyz-self.origin)@self.basis)/radii)
        self.k=int(params.get('neighbors',12));self.minimum=int(params.get('minimum',3));self.method=params.get('method','idw');self.power=float(params.get('power',2))
        finite(self.power)
        if self.method not in ('idw','kriging','nearest','simple_kriging') or not 1<=self.minimum<=self.k<=64 or self.power<=0:raise ValueError('Estimator тохиргоо буруу.')
        self.mean=float(params.get('known_mean',0))
        finite(self.mean)
        if self.method=='simple_kriging' and 'known_mean' not in params:raise ValueError('Simple kriging-д хараат бусаар тогтоосон known_mean шаардлагатай.')
        self.variogram_model=params.get('variogram_model','spherical')
        gamma_model(1,0,1,1,self.variogram_model)
        self.variogram=(float(params.get('nugget',0)),float(params.get('partial_sill',1)),float(params.get('range_m',100)))
        if self.minimum_holes>self.k:raise ValueError('Minimum holes нь neighbors-оос их байж болохгүй.')
        self._within_cache={}
        gamma_spherical(1,*self.variogram)
        self.covariance_ranges=params.get('variogram_ranges')
        self.covariance_basis=search_basis(*params.get('variogram_angles',[90.,0.,0.]))
        if self.covariance_ranges is not None:
            self.covariance_ranges=np.asarray(self.covariance_ranges,dtype=float)
            if self.covariance_ranges.shape!=(3,) or not np.isfinite(self.covariance_ranges).all() or (self.covariance_ranges<=0).any():
                raise ValueError('Variogram-ийн 3 range эерэг байна.')

    def semivariance(self,delta):
        if self.covariance_ranges is None:
            return gamma_model(np.linalg.norm(delta,axis=-1),*self.variogram,self.variogram_model)
        distance=np.linalg.norm((np.asarray(delta)@self.covariance_basis)/self.covariance_ranges,axis=-1)
        return gamma_model(distance,self.variogram[0],self.variogram[1],1.,self.variogram_model)

    def predict(self,point,excluded=None,exclude_hole=None,support_offsets=None):
        point=np.asarray(point,dtype=float)
        if point.shape!=(3,) or not np.isfinite(point).all():raise ValueError('Target цэг буруу.')
        offsets=np.zeros((1,3)) if support_offsets is None else np.asarray(support_offsets,dtype=float)
        if offsets.ndim!=2 or offsets.shape[1]!=3 or not 1<=len(offsets)<=64 or not np.isfinite(offsets).all():
            raise ValueError('Block support 1…64 XYZ offset байна.')
        diagnostics={'kriging_efficiency':None,'slope_of_regression':None,'block_variance':None}
        targets=point+offsets
        candidate=self.tree.query_ball_point(((point-self.origin)@self.basis)/self.radii,1.)
        zone=fault_zone(point,self.faults)
        candidate=[i for i in candidate if self.zones[i]==zone and i!=excluded and (exclude_hole is None or self.samples[i]['hole_id']!=exclude_hole)]
        ordered=sorted(candidate,key=lambda i:(float(np.linalg.norm((self.xyz[i]-point) if self.method=='nearest' else ((self.xyz[i]-point)@self.basis)/self.radii)),i))
        candidate=[];hole_counts={}
        for i in ordered:
            hole=self.samples[i]['hole_id']
            if hole_counts.get(hole,0)>=self.max_per_hole:continue
            candidate.append(i);hole_counts[hole]=hole_counts.get(hole,0)+1
            if len(candidate)==self.k:break
        if len(candidate)<self.minimum or len(hole_counts)<self.minimum_holes:return {'grade':None,'variance':None,'neighbors':len(candidate),'status':'insufficient_support'}
        xyz=self.xyz[candidate];values=self.values[candidate];d=np.linalg.norm(xyz-point,axis=1)
        exact=np.flatnonzero(d<1e-9)
        if len(offsets)==1 and np.all(offsets==0) and len(exact):
            kriging=self.method in ('kriging','simple_kriging')
            return {'grade':float(values[exact[0]]),'variance':0. if kriging else None,'neighbors':len(candidate),'status':'exact_sample',
                    'kriging_efficiency':1. if kriging else None,'slope_of_regression':1. if kriging else None,'block_variance':sum(self.variogram[:2]) if kriging else None}
        if self.method in ('idw','nearest'):
            target_distances=np.linalg.norm(xyz[:,None,:]-targets[None,:,:],axis=2)
            predictions=[]
            for column in target_distances.T:
                exact_target=np.flatnonzero(column<1e-9)
                if len(exact_target):predictions.append(float(values[exact_target[0]]));continue
                if self.method=='nearest':predictions.append(float(values[np.argmin(column)]));continue
                weights=(column.min()/column)**self.power
                predictions.append(float(np.dot(weights,values)/weights.sum()))
            grade=float(np.mean(predictions));variance=None
        elif self.method=='simple_kriging':
            sill=sum(self.variogram[:2]);n=len(candidate)
            covariance=sill-self.semivariance(xyz[:,None,:]-xyz[None,:,:])
            rhs=sill-self.semivariance(xyz[:,None,:]-targets[None,:,:]).mean(axis=1)
            within=float(self.semivariance(offsets[:,None,:]-offsets[None,:,:]).mean())
            try:
                if np.linalg.cond(covariance)>1e12:raise np.linalg.LinAlgError('ill-conditioned')
                weights=np.linalg.solve(covariance,rhs)
            except np.linalg.LinAlgError:return {'grade':None,'variance':None,'neighbors':n,'status':'singular_kriging_system'}
            grade=float(self.mean+np.dot(weights,values-self.mean));variance=float(sill-within-np.dot(weights,rhs))
            if variance< -1e-8 or not math.isfinite(variance):return {'grade':None,'variance':None,'neighbors':n,'status':'invalid_variance'}
            variance=max(0.,variance)
        else:
            n=len(candidate)
            matrix=np.ones((n+1,n+1));matrix[:n,:n]=self.semivariance(xyz[:,None,:]-xyz[None,:,:]);matrix[n,n]=0
            rhs=np.r_[self.semivariance(xyz[:,None,:]-targets[None,:,:]).mean(axis=1),1.]
            key=offsets.tobytes()
            if key not in self._within_cache:
                if len(self._within_cache)>64:self._within_cache.clear()
                self._within_cache[key]=float(self.semivariance(offsets[:,None,:]-offsets[None,:,:]).mean())
            within=self._within_cache[key]
            try:
                if np.linalg.cond(matrix)>1e12:raise np.linalg.LinAlgError('ill-conditioned')
                solution=np.linalg.solve(matrix,rhs)
            except np.linalg.LinAlgError:return {'grade':None,'variance':None,'neighbors':n,'status':'singular_kriging_system'}
            grade=float(np.dot(solution[:n],values));variance=float(np.dot(solution[:n],rhs[:n])+solution[n]-within)
            if variance< -1e-8 or not math.isfinite(variance):return {'grade':None,'variance':None,'neighbors':n,'status':'invalid_variance'}
            variance=max(0.,variance)
        if self.method in ('kriging','simple_kriging'):
            sill=sum(self.variogram[:2]);block_variance=sill-within
            w=weights if self.method=='simple_kriging' else solution[:n]
            covariance=sill-self.semivariance(xyz[:,None,:]-xyz[None,:,:])
            cross=sill-self.semivariance(xyz[:,None,:]-targets[None,:,:]).mean(axis=1)
            prediction_variance=float(w@covariance@w)
            diagnostics={'kriging_efficiency':1.-variance/block_variance if block_variance>1e-12 else None,
                         'slope_of_regression':float(w@cross)/prediction_variance if prediction_variance>1e-12 else None,
                         'block_variance':float(block_variance)}
        return {'grade':grade,'variance':variance,'neighbors':len(candidate),'status':'estimated',**diagnostics}


def make_blocks(bounds,size,domain=None,grid_angles=None):
    finite(*bounds,*size)
    if len(bounds)!=6 or len(size)!=3 or min(size)<=0:raise ValueError('Блокийн bounds/хэмжээ буруу.')
    low=bounds[:3];high=bounds[3:];basis=search_basis(*(grid_angles or [90.,0.,0.]))
    if any(a>=b for a,b in zip(low,high)):raise ValueError('Блокийн min нь max-аас бага байна.')
    counts=[math.ceil((b-a)/s) for a,b,s in zip(low,high,size)]
    if math.prod(counts)>50000:raise ValueError('50000-аас их блок. Хэмжээг томруулна уу.')
    if domain:validate_polygon(domain['points'])
    blocks=[]
    for k in range(counts[2]):
        for j in range(counts[1]):
            for i in range(counts[0]):
                index=(i,j,k);mins=[low[a]+index[a]*size[a] for a in range(3)];dims=[min(size[a],high[a]-mins[a]) for a in range(3)];center=[mins[a]+dims[a]/2 for a in range(3)]
                center=(np.asarray(low)+(np.asarray(center)-low)@basis.T).tolist()
                if domain and not inside_polygon(center[0],center[1],domain['points']):continue
                blocks.append(dict(zip(('x','y','z','dx','dy','dz'),center+dims),i=i,j=j,k=k,grade=None,variance=None,status='unestimated'))
    if not blocks:raise ValueError('Домэйн дотор блок олдсонгүй.')
    return blocks


def estimate_model(project,bounds,size,params,domain=None,cancel=None,progress=None):
    if cancel and cancel():raise RuntimeError('Тооцоог цуцаллаа. Өмнөх төсөл өөрчлөгдөөгүй.')
    grid_angles=params.get('grid_angles',[90.,0.,0.]);grid_basis=search_basis(*grid_angles)
    discretization=params.get('discretization',[1,1,1])
    if (len(discretization)!=3 or any(type(v) is not int or not 1<=v<=4 for v in discretization)):
        raise ValueError('Discretization axis бүр 1…4 бүхэл тоо байна (64 хүртэл support).')
    params=deepcopy(params);faults=deepcopy(params.get('faults',project.workspace.get('faults',[])));validate_faults(faults);params['faults']=faults
    levels=params.get('subblock_levels',0)
    if type(levels) is not int or not 0<=levels<=3:raise ValueError('Sub-block levels 0…3 байна.')
    parents=make_blocks(bounds,size,None,grid_angles)
    blocks=adaptive_blocks(parents,bounds,grid_angles,domain,faults,levels,cancel) if levels or faults else make_blocks(bounds,size,domain,grid_angles)
    samples=sample_support(project,params.get('composite_length',5),params.get('minimum_coverage',1.))
    if domain:samples=[s for s in samples if inside_polygon(s['xyz'][0],s['xyz'][1],domain['points']) and 0<=((np.asarray(s['xyz'])-bounds[:3])@grid_basis)[2]<=bounds[5]-bounds[2]]
    estimator=Estimator(samples,params)
    for i,b in enumerate(blocks):
        if cancel and cancel():raise RuntimeError('Тооцоог цуцаллаа. Өмнөх төсөл өөрчлөгдөөгүй.')
        axes=[((np.arange(n)+.5)/n-.5)*b[key] for n,key in zip(discretization,('dx','dy','dz'))]
        offsets=np.array(np.meshgrid(*axes,indexing='ij')).reshape(3,-1).T@grid_basis.T
        b.update(estimator.predict((b['x'],b['y'],b['z']),support_offsets=offsets))
        if progress and i%50==0:progress(i,len(blocks))
    if progress:progress(len(blocks),len(blocks))
    inputs={'collars':[asdict(h) for h in project.collars],'surveys':[asdict(s) for s in project.surveys],'assays':[asdict(a) for a in project.assays],'crs':project.crs_code,'unit':project.grade_unit}
    fingerprint=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    from . import __version__
    run={'input_sha256':fingerprint,'params':params,'bounds':list(bounds),'size':list(size),'domain':domain,'software_version':__version__}
    run_sha256=hashlib.sha256(json.dumps(run,sort_keys=True,allow_nan=False).encode()).hexdigest()
    statuses={}
    for b in blocks:statuses[b['status']]=statuses.get(b['status'],0)+1
    return {'blocks':blocks,'params':deepcopy(params),'subblock_levels':levels,'faults':faults,'grid_angles':list(grid_angles),'grid_origin':list(bounds[:3]),'capped_sample_count':estimator.capped_count,'bounds':list(bounds),'size':list(size),'domain':deepcopy(domain),'input_sha256':fingerprint,'run_sha256':run_sha256,'status_counts':statuses,'software_version':__version__,'support':('point at block centre' if math.prod(discretization)==1 else 'discretized block average; midpoint quadrature; common centre-selected neighborhood'),'discretization':list(discretization),'classification':'UNCLASSIFIED — independent geological benchmark pending','sample_count':len(samples)}


def cross_validate(samples,params,mode='hole',limit=1000):
    if len(samples)>10000:raise ValueError('Cross-validation-д 10000 хүртэл support дэмжинэ.')
    if mode not in ('hole','sample'):raise ValueError('Validation горим буруу.')
    est=Estimator(samples,params);indices=np.linspace(0,len(samples)-1,min(len(samples),limit),dtype=int);rows=[]
    for i in indices:
        s=samples[int(i)];prediction=est.predict(s['xyz'],excluded=int(i),exclude_hole=s['hole_id'] if mode=='hole' else None)
        if prediction['grade'] is not None:rows.append({'sample_index':int(i),'hole_id':s['hole_id'],'observed':s['grade'],'estimated':prediction['grade'],'error':prediction['grade']-s['grade']})
    errors=np.array([r['error'] for r in rows]);obs=np.array([r['observed'] for r in rows]);pred=np.array([r['estimated'] for r in rows])
    # Baseline is computed from each training fold, never from the held-out values.
    baseline=[]
    for r in rows:
        train=[s['grade'] for j,s in enumerate(samples) if (s['hole_id']!=r['hole_id'] if mode=='hole' else j!=r['sample_index'])]
        baseline.append(float(np.mean(train))-r['observed'])
    return {'params':deepcopy(params),'mode':'leave-one-hole-out' if mode=='hole' else 'leave-one-sample-out','attempted':len(indices),'predicted':len(rows),'unestimated':len(indices)-len(rows),
        'bias':float(errors.mean()) if len(rows) else None,'mae':float(np.abs(errors).mean()) if len(rows) else None,'rmse':float(np.sqrt((errors**2).mean())) if len(rows) else None,
        'baseline_rmse':float(np.sqrt(np.mean(np.array(baseline)**2))) if baseline else None,'rows':rows,'independent_geologist_review':False}


def experimental_variogram(samples,lag_width=20,lags=15,direction=None,faults=None):
    finite(lag_width)
    if lag_width<=0 or not 1<=lags<=100 or not 2<=len(samples)<=10000:raise ValueError('Variogram тохиргоо/өгөгдлийн хэмжээ буруу.')
    axis=None
    if direction is not None:
        azimuth=float(direction['azimuth']);dip=float(direction.get('dip',0.))
        tolerance=float(direction.get('tolerance',22.5));bandwidth=float(direction.get('bandwidth',100.))
        finite(tolerance,bandwidth)
        if not 0<tolerance<=90 or bandwidth<=0:raise ValueError('Tolerance 0…90°, bandwidth > 0 байна.')
        axis=search_basis(azimuth,dip)[:,0]
        direction={'azimuth':azimuth,'dip':dip,'tolerance':tolerance,'bandwidth':bandwidth}
    xyz=np.array([s['xyz'] for s in samples],dtype=float);v=np.array([s['grade'] for s in samples],dtype=float);n=len(samples)
    if xyz.shape!=(n,3) or not np.isfinite(xyz).all() or not np.isfinite(v).all():raise ValueError('Variogram sample утга буруу.')
    if n*(n-1)//2<=250000:a,b=np.triu_indices(n,1)
    else:
        rng=np.random.default_rng(2026);pairs=np.sort(rng.integers(0,n,(300000,2)),axis=1);pairs=np.unique(pairs[pairs[:,0]!=pairs[:,1]],axis=0)[:250000];a,b=pairs.T
    faults=deepcopy(faults or []);validate_faults(faults)
    if faults:
        zones=np.array([fault_zone(p,faults) for p in xyz]);same=zones[a]==zones[b];a=a[same];b=b[same]
    delta=xyz[a]-xyz[b];distances=np.linalg.norm(delta,axis=1);semi=.5*(v[a]-v[b])**2
    candidate_pairs=len(a)
    if axis is not None:
        axial=np.abs(delta@axis)
        perpendicular=np.sqrt(np.maximum(0.,distances**2-axial**2))
        mask=(distances>1e-12)&(axial>=distances*np.cos(np.radians(tolerance))-1e-10)&(perpendicular<=bandwidth+1e-10)
        distances=distances[mask];semi=semi[mask]
    rows=[]
    for i in range(lags):
        mask=(distances>=i*lag_width)&(distances<(i+1)*lag_width);count=int(mask.sum())
        if count:rows.append({'lag':i+1,'distance':float(distances[mask].mean()),'semivariance':float(semi[mask].mean()),'pairs':count})
    return {'rows':rows,'pair_count':len(distances),'candidate_pair_count':candidate_pairs,'isotropic':direction is None,'pair_sampling_seed':2026,'directional_variogram':direction is not None,'faults':faults,'direction':direction,'lag_width':lag_width,'lags':lags}


def fit_variogram(rows):
    from scipy.optimize import least_squares
    if len(rows)<3:raise ValueError('Variogram fit-д 3-аас цөөнгүй lag хэрэгтэй.')
    x=np.array([r['distance'] for r in rows]);y=np.array([r['semivariance'] for r in rows]);weights=np.sqrt([r['pairs'] for r in rows]);weights=weights/weights.max()
    initial=[max(1e-9,float(y.min())),max(1e-6,float(y.max())),max(1,float(x.max())/2)]
    fit=least_squares(lambda p:(gamma_spherical(x,*p)-y)*weights,initial,bounds=([0,1e-12,1e-9],[np.inf,np.inf,np.inf]))
    return {'nugget':float(fit.x[0]),'partial_sill':float(fit.x[1]),'range_m':float(fit.x[2]),'converged':bool(fit.success),'model':'spherical; isotropic; exploratory fit'}


def tonnage_grade(model,density,cutoffs):
    finite(density,*cutoffs)
    if density<=0 or any(c<0 for c in cutoffs):raise ValueError('Density > 0 т/м³, cutoff ≥ 0 байна.')
    rows=[];blocks=model['blocks'];total=sum(b['dx']*b['dy']*b['dz'] for b in blocks)
    for cutoff in cutoffs:
        selected=[b for b in blocks if b.get('grade') is not None and b['grade']>=cutoff]
        volume=sum(b['dx']*b['dy']*b['dz'] for b in selected);tonnes=volume*density
        metal=sum(b['dx']*b['dy']*b['dz']*density*b['grade'] for b in selected)
        missing=sum(b['dx']*b['dy']*b['dz'] for b in blocks if b.get('grade') is None)
        rows.append({'cutoff':cutoff,'volume_m3':volume,'density_t_m3':density,'tonnes':tonnes,'mean_grade':metal/tonnes if tonnes else None,'unestimated_volume_m3':missing,'total_volume_m3':total,'classification':'UNCLASSIFIED; block-centre boundary approximation'})
    return rows
