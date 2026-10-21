"""Indicator probability kriging, deterministic expanding passes and constrained blends."""
from copy import deepcopy
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from .core import finite
from .estimation import Estimator


def indicator_kriging(samples,point,threshold,params):
    finite(threshold)
    indicators=[{**s,'grade':float(s['grade']>=threshold)} for s in samples]
    settings={**params,'method':'kriging'};settings.pop('top_cut',None)
    result=Estimator(indicators,settings).predict(point)
    raw=result['grade']
    return {**result,'probability':None if raw is None else float(np.clip(raw,0,1)),
            'unclipped_probability':raw,'threshold':threshold,'grade':None,
            'note':'binary-indicator covariance required; clipping recorded; not a metal grade'}


def estimate_passes(samples,blocks,passes,cancel=None):
    if not 1<=len(passes)<=5:raise ValueError('1…5 estimation pass байна.')
    result=deepcopy(blocks);pending=list(range(len(result)));counts=[]
    for index,params in enumerate(passes,1):
        estimator=Estimator(samples,params);remaining=[];estimated=0
        for i in pending:
            if cancel and cancel():raise RuntimeError('Estimation cancelled; no project changes.')
            b=result[i];prediction=estimator.predict([b[k] for k in ('x','y','z')])
            b.update(prediction,estimation_pass=index if prediction['grade'] is not None else None)
            if prediction['grade'] is None:remaining.append(i)
            else:estimated+=1
        counts.append({'pass':index,'estimated':estimated,'remaining':len(remaining)});pending=remaining
    return result,counts


def blend_schedule(tasks,mining_capacity,processing_capacity,periods,minimum_grade,maximum_grade,discount=0.,seconds=20):
    """Joint indivisible task extraction/processing and feed-grade constraints.

    Optional tasks; ore is processed in its mining period; no stockpile/reclaim.
    Price/cost are captured in per-task value, with one currency throughout.
    """
    finite(mining_capacity,processing_capacity,minimum_grade,maximum_grade,discount,seconds)
    if min(mining_capacity,processing_capacity,seconds)<=0 or not 0<=minimum_grade<=maximum_grade or not 0<=discount<1 or type(periods) is not int or periods<1:
        raise ValueError('Schedule/blend параметр буруу.')
    n=len(tasks)
    if not n or n*periods>10000:raise ValueError('1…10000 task-period variables байна.')
    ids=[t['id'] for t in tasks]
    if len(set(ids))!=n:raise ValueError('Task ID давхардсан.')
    lookup={name:i for i,name in enumerate(ids)};precedence=[]
    for i,t in enumerate(tasks):
        finite(t['tonnes'],t['process_tonnes'],t['value'],t['grade'])
        if t['tonnes']<=0 or not 0<=t['process_tonnes']<=t['tonnes'] or t['grade']<0:raise ValueError('Task тоон утга буруу.')
        for p in t.get('predecessors',[]):
            if p not in lookup or p==t['id']:raise ValueError('Predecessor буруу.')
            precedence.append((i,lookup[p]))
    if len(precedence)*periods>100000:raise ValueError('Precedence matrix хэт том.')
    children=[[] for _ in tasks];degree=[0]*n
    for child,parent in precedence:children[parent].append(child);degree[child]+=1
    ready=[i for i,d in enumerate(degree) if d==0];visited=0
    while ready:
        current=ready.pop();visited+=1
        for child in children[current]:
            degree[child]-=1
            if degree[child]==0:ready.append(child)
    if visited!=n:raise ValueError('Precedence циклтэй.')
    rows=n+4*periods+len(precedence)*periods;a=lil_matrix((rows,n*periods),dtype=float);lower=np.full(rows,-np.inf);upper=np.full(rows,np.inf);r=0
    for i in range(n):a[r,i*periods:(i+1)*periods]=1;upper[r]=1;r+=1
    for t in range(periods):
        for i,task in enumerate(tasks):a[r,i*periods+t]=task['tonnes']
        upper[r]=mining_capacity;r+=1
        for i,task in enumerate(tasks):a[r,i*periods+t]=task['process_tonnes']
        upper[r]=processing_capacity;r+=1
        for i,task in enumerate(tasks):a[r,i*periods+t]=task['process_tonnes']*(task['grade']-minimum_grade)
        lower[r]=0;r+=1
        for i,task in enumerate(tasks):a[r,i*periods+t]=task['process_tonnes']*(task['grade']-maximum_grade)
        upper[r]=0;r+=1
    for child,parent in precedence:
        for t in range(periods):
            a[r,child*periods+t]=1
            for previous in range(t):a[r,parent*periods+previous]=-1
            upper[r]=0;r+=1
    objective=np.array([-task['value']/(1+discount)**t for task in tasks for t in range(periods)])
    solved=milp(objective,integrality=np.ones(n*periods),bounds=Bounds(0,1),constraints=LinearConstraint(a.tocsr(),lower,upper),options={'time_limit':seconds,'mip_rel_gap':.001})
    if solved.x is None:raise ValueError('Solver incumbent алга: '+solved.message)
    selected=np.rint(solved.x)
    if np.max(abs(selected-solved.x))>1e-5 or np.any(a@selected>upper+1e-6) or np.any(a@selected<lower-1e-6):raise ValueError('MILP residual failed.')
    scheduled=[{'period':t+1,**task} for i,task in enumerate(tasks) for t in range(periods) if selected[i*periods+t]>.5]
    periods_report=[]
    for t in range(1,periods+1):
        chosen=[task for task in scheduled if task['period']==t];feed=sum(task['process_tonnes'] for task in chosen)
        periods_report.append({'period':t,'mined_tonnes':sum(task['tonnes'] for task in chosen),'feed_tonnes':feed,
                               'feed_grade':sum(task['process_tonnes']*task['grade'] for task in chosen)/feed if feed else None})
    return {'rows':scheduled,'periods':periods_report,'optimal':solved.status==0,'mip_gap':float(solved.mip_gap),
            'npv':float(-objective@selected),'unselected':[t['id'] for t in tasks if t['id'] not in {r['id'] for r in scheduled}],
            'scope':'joint optional extraction and same-period processing/blend; no stockpile'}
