"""Auditable exploratory statistics and proposed classification, not certification."""
from copy import deepcopy
from statistics import NormalDist
import math
import numpy as np
from scipy.spatial import cKDTree
from .chronology import ScalarField


def sample_arrays(samples):
    if not 1<=len(samples)<=100000:raise ValueError('1–100000 samples required')
    xyz=np.asarray([s['xyz'] for s in samples],float);grades=np.asarray([s['grade'] for s in samples],float)
    support=np.asarray([s.get('support_m',1.) for s in samples],float)
    if xyz.shape!=(len(samples),3) or not np.isfinite(xyz).all() or not np.isfinite(grades).all() or np.any(grades<0) or not np.isfinite(support).all() or np.any(support<=0):raise ValueError('Invalid sample coordinates/grades/support')
    return xyz,grades,support


def cap_analysis(samples,cap=None,bins=20):
    _,grades,support=sample_arrays(samples)
    if type(bins)!=int or not 2<=bins<=100:raise ValueError('Histogram bins 2–100')
    if cap is not None and (not math.isfinite(cap) or cap<=0):raise ValueError('Positive cap required')
    counts,edges=np.histogram(grades,bins=bins,weights=support)
    histogram=[{'from_grade':float(a),'to_grade':float(b),'support_m':float(v)} for a,b,v in zip(edges,edges[1:],counts)]
    order=np.argsort(grades,kind='stable');total=float(grades@support);deciles=[]
    for i,ids in enumerate(np.array_split(order,10),1):
        deciles.append({'decile':i,'samples':len(ids),'grade_min':float(grades[ids].min()) if len(ids) else None,
                        'grade_max':float(grades[ids].max()) if len(ids) else None,
                        'grade_support_fraction':float(grades[ids]@support[ids])/total if total else None})
    positive=np.sort(grades[grades>0]);distribution=NormalDist()
    probability=[{'normal_score':distribution.inv_cdf((i+.5)/len(positive)),'log_grade':float(np.log(g)),'grade':float(g)} for i,g in enumerate(positive)]
    capped=np.minimum(grades,cap) if cap is not None else grades
    return {'raw_mean':float(grades@support/support.sum()),'capped_mean':float(capped@support/support.sum()),
            'cap':cap,'capped_samples':int((grades>cap).sum()) if cap is not None else 0,
            'nonpositive_excluded_from_log_plot':int((grades<=0).sum()),'histogram':histogram,
            'deciles':deciles,'lognormal_probability':probability,
            'scope':'support-weighted statistics; equal-count deciles; probability plot uses positive sample ranks; cap chosen by geologist'}


def cell_decluster(samples,size,offsets=None):
    xyz,grades,support=sample_arrays(samples);size=np.asarray(size,float)
    if size.shape!=(3,) or not np.isfinite(size).all() or np.any(size<=0):raise ValueError('Three positive cell sizes required')
    offsets=offsets if offsets is not None else [[a,b,c] for a in (0,.5) for b in (0,.5) for c in (0,.5)]
    offsets=np.asarray(offsets,float)
    if offsets.ndim!=2 or offsets.shape[1]!=3 or not 1<=len(offsets)<=64 or not np.isfinite(offsets).all():raise ValueError('1–64 finite grid shifts required')
    weights=np.zeros(len(xyz));origin=xyz.min(axis=0)
    for offset in offsets:
        scaled=(xyz-origin)/size-offset
        if not np.isfinite(scaled).all() or np.any(abs(scaled)>9e15):raise ValueError('Declustering cell indices exceed numeric precision')
        indices=np.floor(scaled)
        _,inverse=np.unique(indices,axis=0,return_inverse=True)
        cell_support=np.bincount(inverse,weights=support)
        weights+=support/cell_support[inverse]/len(cell_support)
    weights/=len(offsets);weights/=weights.sum()
    return {'cell_size':size.tolist(),'offsets':offsets.tolist(),'weights':weights.tolist(),
            'declustered_mean':float(weights@grades),'raw_support_mean':float(grades@support/support.sum()),
            'effective_sample_count':float(1/(weights@weights)),
            'scope':'equal occupied-cell weighting, support-proportional inside each cell, averaged grid shifts; no automatic best-size selection'}


class DynamicOrientation:
    def __init__(self,spec):
        if not isinstance(spec,dict):raise ValueError('Dynamic orientation recipe required')
        self.kind=spec.get('kind')
        if self.kind=='field_gradient':
            self.field=ScalarField(spec['field']);self.step=float(spec.get('step_m',1))
            if not math.isfinite(self.step) or self.step<=0:raise ValueError('Positive gradient step required')
        elif self.kind=='normal_controls':
            controls=spec.get('controls',[])
            if not 1<=len(controls)<=50000:raise ValueError('1–50000 orientation controls required')
            xyz=np.asarray([r['xyz'] for r in controls],float);normals=np.asarray([r['normal'] for r in controls],float)
            if xyz.shape!=(len(controls),3) or normals.shape!=xyz.shape or not np.isfinite(xyz).all() or not np.isfinite(normals).all() or np.any(np.linalg.norm(normals,axis=1)<1e-12):raise ValueError('Invalid orientation controls')
            self.tree=cKDTree(xyz);self.normals=normals;self.maximum=float(spec.get('maximum_distance_m',1e9))
            if not math.isfinite(self.maximum) or self.maximum<=0:raise ValueError('Positive orientation extrapolation distance required')
        else:raise ValueError('Dynamic orientation: field_gradient or normal_controls required')

    def at(self,point):
        p=np.asarray(point,float)
        if p.shape!=(3,) or not np.isfinite(p).all():raise ValueError('Finite target required')
        if self.kind=='field_gradient':
            normal=np.array([(self.field(np.array([p+axis*self.step]))[0]-self.field(np.array([p-axis*self.step]))[0])/(2*self.step) for axis in np.eye(3)])
        else:
            distance,index=self.tree.query(p)
            if distance>self.maximum:raise ValueError('No orientation control within declared extrapolation distance')
            normal=self.normals[index].copy()
        length=np.linalg.norm(normal)
        if length<1e-12 or not np.isfinite(length):raise ValueError('Local gradient is zero/undefined; orientation cannot be inferred')
        normal/=length
        if normal[2]<0:normal=-normal
        strike=np.cross([0,0,1],normal)
        if np.linalg.norm(strike)<1e-10:strike=np.array([1.,0,0])
        strike/=np.linalg.norm(strike);dip=np.cross(normal,strike)
        return np.column_stack((strike,dip,normal))


def propose_classes(model,rules):
    if not isinstance(rules,list) or not 1<=len(rules)<=10:raise ValueError('1–10 priority-ordered classification proposal rules required')
    allowed={'maximum_variance':'variance','minimum_sor':'slope_of_regression',
             'maximum_sample_distance_m':'nearest_sample_distance_m','minimum_holes':'distinct_holes','maximum_pass':'estimation_pass'}
    names=set()
    for rule in rules:
        if rule.get('name') not in ('Measured','Indicated','Inferred') or rule['name'] in names:raise ValueError('Unique proposal class labels required; no automatic reporting-code equivalence')
        names.add(rule['name'])
        checks={k:v for k,v in rule.items() if k!='name'}
        if not checks or set(checks)-set(allowed) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in checks.values()):raise ValueError('Invalid proposal rule diagnostics/thresholds')
    output=deepcopy(model);counts={}
    for block in output.get('blocks',[]):
        chosen=None
        if block.get('grade') is not None:
            for rule in rules:
                valid=True
                for key,value in rule.items():
                    if key=='name':continue
                    actual=block.get(allowed[key])
                    if actual is None or not math.isfinite(actual) or (actual>value if key.startswith('maximum') else actual<value):valid=False;break
                if valid:chosen=rule['name'];break
        block['classification_proposal']={'proposed_class':chosen or 'Unclassified','review_status':'PENDING_QUALIFIED_REVIEW'}
        counts[chosen or 'Unclassified']=counts.get(chosen or 'Unclassified',0)+1
    output['classification_proposal_rules']=deepcopy(rules)
    return output,{'counts':counts,'approval':False,'scope':'diagnostic proposal only; resource_class unchanged; no A/B/C or JORC equivalence inferred'}
