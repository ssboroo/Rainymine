"""Experimental deterministic point-support estimation, not classified resources.
Ordinary kriging uses a spherical semivariogram in an augmented linear system.
Block-centre estimates are not block-averaged kriging estimates.
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

def search_basis(azimuth=90., dip=0., roll=0.):
    """Columns are local X/Y/Z in world ENU; azimuth clockwise from north.
    Dip is positive upwards. Roll rotates local Y towards local Z about local X.
    The default (90, 0, 0) preserves the historical world-axis search.
    """
    finite(azimuth, dip, roll)
    if not -90 <= dip <= 90:
        raise ValueError('Search dip −90…90 градус байна.')
    a,d,r=np.radians([azimuth,dip,roll])
    x=np.array([np.sin(a)*np.cos(d),np.cos(a)*np.cos(d),np.sin(d)])
    y=np.array([-np.cos(a),np.sin(a),0.])
    z=np.cross(x,y)
    return np.column_stack((x,np.cos(r)*y+np.sin(r)*z,-np.sin(r)*y+np.cos(r)*z))


class Estimator:
    def __init__(self,samples,params):
        if not samples:raise ValueError('Тооцох сорьц алга. Композитын coverage-ийг шалгана уу.')
        self.samples=samples;self.params=params
        self.xyz=np.asarray([r['xyz'] for r in samples],dtype=float);self.values=np.asarray([r['grade'] for r in samples],dtype=float)
        if not np.isfinite(self.xyz).all() or not np.isfinite(self.values).all():raise ValueError('Sample утга буруу.')
        if len(np.unique(self.xyz,axis=0))!=len(self.xyz):raise ValueError('Ижил координаттай композит байна. Давхардлыг эх өгөгдөл дээр шийднэ үү.')
        radii=np.asarray(params.get('radii',[200,200,100]),dtype=float)
        if radii.shape!=(3,) or not np.isfinite(radii).all() or (radii<=0).any():raise ValueError('Search ellipsoid-ийн 3 радиус эерэг байна.')
        angles=params.get('search_angles',[90.,0.,0.])
        if len(angles)!=3:raise ValueError('Search azimuth/dip/roll шаардлагатай.')
        self.basis=search_basis(*angles)
        self.radii=radii;self.origin=self.xyz[0];self.tree=cKDTree(((self.xyz-self.origin)@self.basis)/radii)
        self.k=int(params.get('neighbors',12));self.minimum=int(params.get('minimum',3));self.method=params.get('method','idw');self.power=float(params.get('power',2))
        finite(self.power)
        if self.method not in ('idw','kriging') or not 1<=self.minimum<=self.k<=64 or self.power<=0:raise ValueError('Estimator тохиргоо буруу.')
        self.variogram=(float(params.get('nugget',0)),float(params.get('partial_sill',1)),float(params.get('range_m',100)))
        gamma_spherical(1,*self.variogram)

    def predict(self,point,excluded=None,exclude_hole=None):
        point=np.asarray(point,dtype=float)
        if point.shape!=(3,) or not np.isfinite(point).all():raise ValueError('Target цэг буруу.')
        candidate=self.tree.query_ball_point(((point-self.origin)@self.basis)/self.radii,1.)
        candidate=[i for i in candidate if i!=excluded and (exclude_hole is None or self.samples[i]['hole_id']!=exclude_hole)]
        candidate=sorted(candidate,key=lambda i:(float(np.linalg.norm(((self.xyz[i]-point)@self.basis)/self.radii)),i))[:self.k]
        if len(candidate)<self.minimum:return {'grade':None,'variance':None,'neighbors':len(candidate),'status':'insufficient_support'}
        xyz=self.xyz[candidate];values=self.values[candidate];d=np.linalg.norm(xyz-point,axis=1)
        exact=np.flatnonzero(d<1e-9)
        if len(exact):return {'grade':float(values[exact[0]]),'variance':0. if self.method=='kriging' else None,'neighbors':len(candidate),'status':'exact_sample'}
        if self.method=='idw':
            weights=(d.min()/d)**self.power;grade=float(np.dot(weights,values)/weights.sum());variance=None
        else:
            distances=np.linalg.norm(xyz[:,None,:]-xyz[None,:,:],axis=2);n=len(candidate)
            matrix=np.ones((n+1,n+1));matrix[:n,:n]=gamma_spherical(distances,*self.variogram);matrix[n,n]=0
            rhs=np.r_[gamma_spherical(d,*self.variogram),1.]
            try:
                if np.linalg.cond(matrix)>1e12:raise np.linalg.LinAlgError('ill-conditioned')
                solution=np.linalg.solve(matrix,rhs)
            except np.linalg.LinAlgError:return {'grade':None,'variance':None,'neighbors':n,'status':'singular_kriging_system'}
            grade=float(np.dot(solution[:n],values));variance=float(np.dot(solution[:n],rhs[:n])+solution[n])
            if variance< -1e-8 or not math.isfinite(variance):return {'grade':None,'variance':None,'neighbors':n,'status':'invalid_variance'}
            variance=max(0.,variance)
        return {'grade':grade,'variance':variance,'neighbors':len(candidate),'status':'estimated'}


def make_blocks(bounds,size,domain=None):
    finite(*bounds,*size)
    if len(bounds)!=6 or len(size)!=3 or min(size)<=0:raise ValueError('Блокийн bounds/хэмжээ буруу.')
    low=bounds[:3];high=bounds[3:]
    if any(a>=b for a,b in zip(low,high)):raise ValueError('Блокийн min нь max-аас бага байна.')
    counts=[math.ceil((b-a)/s) for a,b,s in zip(low,high,size)]
    if math.prod(counts)>50000:raise ValueError('50000-аас их блок. Хэмжээг томруулна уу.')
    if domain:validate_polygon(domain['points'])
    blocks=[]
    for k in range(counts[2]):
        for j in range(counts[1]):
            for i in range(counts[0]):
                index=(i,j,k);mins=[low[a]+index[a]*size[a] for a in range(3)];dims=[min(size[a],high[a]-mins[a]) for a in range(3)];center=[mins[a]+dims[a]/2 for a in range(3)]
                if domain and not inside_polygon(center[0],center[1],domain['points']):continue
                blocks.append(dict(zip(('x','y','z','dx','dy','dz'),center+dims),i=i,j=j,k=k,grade=None,variance=None,status='unestimated'))
    if not blocks:raise ValueError('Домэйн дотор блок олдсонгүй.')
    return blocks


def estimate_model(project,bounds,size,params,domain=None,cancel=None,progress=None):
    blocks=make_blocks(bounds,size,domain);samples=sample_support(project,params.get('composite_length',5),params.get('minimum_coverage',1.))
    if domain:samples=[s for s in samples if inside_polygon(s['xyz'][0],s['xyz'][1],domain['points']) and bounds[2]<=s['xyz'][2]<=bounds[5]]
    estimator=Estimator(samples,params)
    for i,b in enumerate(blocks):
        if cancel and cancel():raise RuntimeError('Тооцоог цуцаллаа. Өмнөх төсөл өөрчлөгдөөгүй.')
        b.update(estimator.predict((b['x'],b['y'],b['z'])))
        if progress and i%50==0:progress(i,len(blocks))
    inputs={'collars':[asdict(h) for h in project.collars],'surveys':[asdict(s) for s in project.surveys],'assays':[asdict(a) for a in project.assays],'crs':project.crs_code,'unit':project.grade_unit}
    fingerprint=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    from . import __version__
    return {'blocks':blocks,'params':params,'bounds':list(bounds),'size':list(size),'domain':domain,'input_sha256':fingerprint,'software_version':__version__,'support':'point at block centre; no block discretisation','classification':'UNCLASSIFIED — independent geological benchmark pending','sample_count':len(samples)}


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


def experimental_variogram(samples,lag_width=20,lags=15,direction=None):
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
    return {'rows':rows,'pair_count':len(distances),'candidate_pair_count':candidate_pairs,'isotropic':direction is None,'pair_sampling_seed':2026,'directional_variogram':direction is not None,'direction':direction,'lag_width':lag_width,'lags':lags}


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
