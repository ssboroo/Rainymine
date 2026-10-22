"""Ordered intrusion/vein/stratigraphic scalar-field ownership at block centres.

Younger events overwrite older ownership; an erosion event clears material.
This produces exclusive labels, not a watertight geological solid certificate.
RBF evaluation uses bounded local neighbours, not a dense global N×N solve.
"""
from copy import deepcopy
import hashlib
import json
import numpy as np
from scipy.interpolate import RBFInterpolator
from .fault_network import FaultNetwork


class ScalarField:
    def __init__(self,spec):
        if not isinstance(spec,dict):raise ValueError('Geological field object required')
        self.kind=spec.get('kind','plane')
        if self.kind=='plane':
            self.origin=np.asarray(spec.get('point'),dtype=float);self.normal=np.asarray(spec.get('normal'),dtype=float)
            if self.origin.shape!=(3,) or self.normal.shape!=(3,) or not np.isfinite(self.origin).all() or not np.isfinite(self.normal).all() or np.linalg.norm(self.normal)<1e-12:raise ValueError('Invalid geological plane')
            self.normal=self.normal/np.linalg.norm(self.normal)
        elif self.kind=='rbf':
            controls=spec.get('constraints',[])
            if not 4<=len(controls)<=50000:raise ValueError('Local RBF supports 4–50000 explicit signed controls')
            xyz=np.array([[c[k] for k in 'xyz'] for c in controls],dtype=float);values=np.array([c['value'] for c in controls],dtype=float)
            self.ranges=np.asarray(spec.get('ranges',[100,100,100]),dtype=float);neighbors=spec.get('neighbors',32);smoothing=float(spec.get('smoothing',0))
            if not np.isfinite(xyz).all() or not np.isfinite(values).all() or len(np.unique(xyz,axis=0))!=len(xyz) or self.ranges.shape!=(3,) or not np.isfinite(self.ranges).all() or np.any(self.ranges<=0) or type(neighbors)!=int or not 4<=neighbors<=128 or not np.isfinite(smoothing) or smoothing<0:raise ValueError('Invalid/duplicate geological RBF controls/settings')
            self.origin=xyz.mean(axis=0)
            self.interpolator=RBFInterpolator((xyz-self.origin)/self.ranges,values,kernel='linear',degree=0,neighbors=min(neighbors,len(values)),smoothing=smoothing)
        else:raise ValueError('Geological field kind must be plane or rbf')

    def __call__(self,points):
        result=(points-self.origin)@self.normal if self.kind=='plane' else self.interpolator((points-self.origin)/self.ranges)
        if not np.isfinite(result).all():raise ValueError('Geological scalar field returned nonfinite values')
        return result


class Chronology:
    def __init__(self,recipe):
        if not isinstance(recipe,dict):raise ValueError('Geological chronology object required')
        events=recipe.get('events',[])
        if recipe.get('version')!=1 or not isinstance(events,list) or not 1<=len(events)<=32:raise ValueError('Chronology version 1, 1–32 oldest-to-youngest events required')
        self.recipe=deepcopy(recipe);self.events=[];names=set();self.network=FaultNetwork(recipe.get('faults',[]))
        for event in events:
            name=event.get('name');kind=event.get('kind')
            if not isinstance(name,str) or not name.strip() or len(name)>100 or name in names:raise ValueError('Unique geological event names required')
            names.add(name)
            if kind in ('intrusion','erosion'):fields=[ScalarField(event['field'])]
            elif kind in ('vein','stratigraphy'):fields=[ScalarField(event['lower']),ScalarField(event['upper'])]
            else:raise ValueError('Event kind must be intrusion, vein, stratigraphy or erosion')
            self.events.append((name,kind,fields))

    def classify(self,points,cancel=None):
        points=np.asarray(points,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Finite N×3 target coordinates required')
        labels=np.zeros(len(points),dtype=np.int16)
        for start in range(0,len(points),4096):
            if cancel and cancel():raise RuntimeError('Geological chronology cancelled')
            # Explicit fault restoration is a common frame, not inferred history.
            xyz=self.network.restore(points[start:start+4096],cancel)
            owned=labels[start:start+4096]
            for code,(_,kind,fields) in enumerate(self.events,1):
                if cancel and cancel():raise RuntimeError('Geological chronology cancelled')
                inside=fields[0](xyz)>=0
                if len(fields)==2:inside&=fields[1](xyz)<0
                owned[inside]=0 if kind=='erosion' else code
        return labels


def apply_chronology(model,recipe,cancel=None):
    blocks=model.get('blocks',[])
    if not blocks or len(blocks)>50000:raise ValueError('Chronology desktop application supports 1–50000 blocks')
    engine=Chronology(recipe);labels=engine.classify([[b[k] for k in 'xyz'] for b in blocks],cancel)
    result=deepcopy(model);names={i:name for i,(name,_,_) in enumerate(engine.events,1)}
    for b,code in zip(result['blocks'],labels):
        name=names.get(int(code),'UNASSIGNED')
        b.update(domain=name,lithology=name,grade=None,variance=None,status='needs_estimation')
        for key in ('neighbors','kriging_efficiency','slope_of_regression','block_variance','estimation_pass'):b.pop(key,None)
    for key in ('run_sha256','input_sha256'):result.pop(key,None)
    result['status_counts']={'needs_estimation':len(blocks)}
    result['geological_chronology']=deepcopy(recipe)
    report={'recipe_sha256':hashlib.sha256(json.dumps(recipe,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            'event_order':[name for name,_,_ in engine.events],
            'counts':{names.get(int(i),'UNASSIGNED'):int((labels==i).sum()) for i in np.unique(labels)},
            'ownership':'one material per block centre; younger overwrites older; erosion clears',
            'fault_frame':'explicit common-frame restoration; no inferred event timing',
            'watertight_mesh_verified':False,'geological_review_verified':False,'rbf_backend':'scipy local neighbors; not Rust FMM/PoU'}
    return result,report
