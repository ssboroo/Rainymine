"""Read-only whitelisted local tool calls; generated SQL/Python is never executed."""
import json
import math
import re
import sqlite3
from pathlib import Path
import numpy as np


FIELDS={'grade','x','y','z','density','domain'}
OPS={'=','>','>=','<','<='}


def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)-{'tool','conditions','limit'} or plan.get('tool')!='filter_blocks':raise ValueError('Only the read-only filter_blocks tool is allowed')
    conditions=plan.get('conditions',[]);limit=plan.get('limit',50000)
    if not isinstance(conditions,list) or len(conditions)>10 or type(limit)!=int or not 1<=limit<=250000:raise ValueError('Invalid query limit/conditions')
    for c in conditions:
        if not isinstance(c,dict) or set(c)!={'field','op','value'} or c['field'] not in FIELDS or c['op'] not in OPS:raise ValueError('Unsupported block filter')
        v=c['value']
        if c['field']=='domain':
            if c['op']!='=' or not isinstance(v,str) or not v or len(v)>200:raise ValueError('Exact domain text required')
        elif isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Finite numeric filter required')
    return {'tool':'filter_blocks','conditions':conditions,'limit':limit}


def parse_query(text,domains=()):
    """Small deterministic MN/EN grammar; ambiguity is rejected, not guessed."""
    if not isinstance(text,str) or len(text)>2000:raise ValueError('Query length exceeded')
    conditions=[];lower=text.casefold()
    if re.search(r'(?i)\b(or|not)\b|эсвэл|биш|!=|<>',text):raise ValueError('Only explicit AND filters are supported; OR/NOT is ambiguous')
    found=[d for d in domains if isinstance(d,str) and d.casefold() in lower]
    if len(found)>1:raise ValueError('Several domain names match; specify one exact domain')
    if not found and re.search(r'(?i)\bdomain\b|бүс|оксид|oxide',text):raise ValueError('Specify an existing exact domain name')
    if found:conditions.append({'field':'domain','op':'=','value':found[0]})
    aliases={'grade':'grade','агуулга':'grade','x':'x','y':'y','z':'z','өндөр':'z','density':'density','нягт':'density'}
    for name,op,value in re.findall(r'(?i)(grade|агуулга|density|нягт|өндөр|\bx\b|\by\b|\bz\b)\s*(>=|<=|>|<|=|≥|≤)\s*(-?\d+(?:\.\d+)?)',text):
        conditions.append({'field':aliases[name.casefold()],'op':{'≥':'>=','≤':'<='}.get(op,op),'value':float(value)})
    if not conditions:raise ValueError('Use an exact domain and/or grade > 0.5, Z > 1200; the active project grade channel is used')
    # Explicit element names require an identified active channel; do not infer Au/Cu.
    if re.search(r'(?i)\b(?:Au|Cu|Ag|Zn|Pb)\s*[><=≥≤]',text):raise ValueError('Use grade/агуулга for the active channel; element-specific channel must be selected in the project first')
    return validate_plan({'tool':'filter_blocks','conditions':conditions})


def model_query(model,plan,grade_unit,cancel=None):
    plan=validate_plan(plan);selected=[];ids=[]
    def match(b,c):
        value=b.get(c['field']);target=c['value']
        if value is None:return False
        op=c['op']
        return value==target if op=='=' else value>target if op=='>' else value>=target if op=='>=' else value<target if op=='<' else value<=target
    for i,b in enumerate(model.get('blocks',[])):
        if i%1000==0 and cancel and cancel():raise RuntimeError('Copilot query cancelled')
        if all(match(b,c) for c in plan['conditions']):selected.append(b);ids.append(i)
    from .benchmark import block_totals
    totals=block_totals(selected,grade_unit)
    weighted=sum(b['dx']*b['dy']*b['dz']*b['density']*b['grade'] for b in selected if b.get('grade') is not None and b.get('density') is not None)
    estimated=sum(b['dx']*b['dy']*b['dz']*b['density'] for b in selected if b.get('grade') is not None and b.get('density') is not None)
    totals['mean_grade']=weighted/estimated if estimated and all(b.get('density') is not None for b in selected) else None
    return _payload(selected[:plan['limit']],ids[:plan['limit']],totals,plan,grade_unit,len(selected))


def disk_query(path,plan,cancel=None):
    plan=validate_plan(plan);clauses=[];parameters=[]
    for condition in plan['conditions']:
        clauses.append('"'+condition['field']+'" '+condition['op']+' ?');parameters.append(condition['value'])
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if cancel:db.set_progress_handler(lambda:1 if cancel() else 0,1000)
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        if db.execute('PRAGMA application_id').fetchone()[0]!=0x524d4442:raise ValueError('Not a RAINYMINE block store')
        meta=json.loads(db.execute('SELECT value FROM metadata WHERE key="model"').fetchone()[0]);unit=meta['grade_unit']
        row=db.execute('SELECT count(*),sum(grade IS NULL),sum(dx*dy*dz),sum(density IS NULL),sum(dx*dy*dz*density),sum(CASE WHEN grade IS NOT NULL THEN dx*dy*dz*density END),sum(dx*dy*dz*density*grade) FROM blocks'+where,parameters).fetchone()
        count,unknown,volume,missing,tonnes,estimated,weighted=row
        totals={'blocks':count,'unestimated_blocks':unknown or 0,'volume_m3':volume or 0.,'tonnes':None if missing else tonnes or 0.,
                'contained_metal_tonnes':None if missing else (weighted or 0.)*(.01 if unit=='%' else 1e-6),
                'mean_grade':weighted/estimated if not missing and estimated and weighted is not None else None}
        columns=['x','y','z','dx','dy','dz','grade','density','domain']
        rows=db.execute('SELECT id,'+','.join(columns)+' FROM blocks'+where+' ORDER BY id LIMIT ?',parameters+[plan['limit']]).fetchall()
        return _payload([dict(zip(columns,r[1:])) for r in rows],[r[0] for r in rows],totals,plan,unit,count)
    finally:db.close()


def _payload(blocks,ids,totals,plan,unit,count):
    return {'plan':plan,'totals':totals,'rows':[{**b,'source_index':i} for b,i in zip(blocks,ids)],
            'preview':{'kind':'blocks','xyz':np.array([[b[k] for k in 'xyz'] for b in blocks],dtype=float).reshape(-1,3),
                       'sizes':np.array([[b[k] for k in ('dx','dy','dz')] for b in blocks],dtype=float).reshape(-1,3),
                       'grade':np.array([b.get('grade') if b.get('grade') is not None else np.nan for b in blocks]),
                       'source_index':np.asarray(ids,dtype=np.int64),'source_points':count,'matched_before_sampling':count,
                       'stride':1,'grade_unit':unit},'scope':'read-only; totals cover all matches, table/3D limited by plan limit; no grade or density invented'}


def methodology_draft(project,locale='mn'):
    model=project.workspace.get('block_model',{});params=model.get('params',{})
    data={'project':project.name,'crs':project.crs_code or 'UNSPECIFIED','grade_unit':project.grade_unit,
          'holes':len(project.collars),'assays':len(project.assays),'blocks':len(model.get('blocks',[])),
          'parameters':params,'support':model.get('support','UNSPECIFIED'),'run_sha256':model.get('run_sha256'),'classification':'UNCLASSIFIED / qualified review pending'}
    title='Нөөцийн тооцооны аргачлал — ХЯНАХ НООРОГ' if locale=='mn' else 'Estimation methodology — REVIEW DRAFT'
    method=str(params.get('method','UNSPECIFIED'));composite=params.get('composite_length','UNSPECIFIED')
    if locale=='mn':
        prose=(f"{project.name} төслийн бүртгэлд {len(project.collars)} цооног, {len(project.assays)} сорьцын интервал, "
               f"{len(model.get('blocks',[]))} блок байна. Агуулгын нэгж {project.grade_unit}; CRS: {data['crs']}. "
               f"Блок загварын бүртгэлтэй үнэлгээний арга {method}, композитын урт {composite} м. "
               f"Тооцооны support: {data['support']}. Вариограмм, хайлтын тохиргоо болон run fingerprint-ийг доорх бүртгэлээр шалгана. "
               "NULL болон хангалтгүй support бүхий блокуудыг үр дүнгийн status-аар тусад нь хянана. "
               "Нөөцийн ангилал, геологийн үргэлжлэл, эдийн засгийн олборлох үндэслэлийн баталгааг энэ ноорог тогтоохгүй.")
    else:
        prose=(f"The recorded {project.name} project contains {len(project.collars)} drillholes, {len(project.assays)} assay intervals "
               f"and {len(model.get('blocks',[]))} blocks. Grade unit: {project.grade_unit}; CRS: {data['crs']}. "
               f"The recorded estimation method is {method}, with composite length {composite} m and support {data['support']}. "
               "Variogram, search settings and run fingerprint are included below for review. NULL and insufficient-support blocks "
               "require separate status review. This draft does not establish resource classification, geological continuity or economic extraction assumptions.")
    return title+'\n\n'+prose+'\n\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n\n'+('Энэ ноорог нь төслийн бүртгэлтэй үзүүлэлтүүдийг л тусгав. Геологийн үндэслэл, жишиг, өгөгдлийн чанар, нөөцийн ангилал болон CP-ийн дүгнэлтийг мэргэжилтэн нөхөж хянана.' if locale=='mn' else 'Only recorded project facts are included. Geological interpretation, economic assumptions, data quality, classification and qualified-person review must be supplied and checked separately.')
