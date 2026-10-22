"""Local command plans: bounded capabilities, detached computation and audit journal."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import re
from uuid import uuid4

TOOLS={'validate_project','composite','estimate_blocks','qaqc_summary','classification_proposal'}
MUTATIONS={'composite','estimate_blocks','classification_proposal'}
METHODS={'nearest','idw','kriging','simple_kriging'}
FORBIDDEN=r'(?i)устг|арилга|батал|биш|эсвэл|бодохгүй|хийхгүй|тооцохгүй|хэрэггүй|\b(delete|remove|approve|certify|exec|python|shell|sql|powershell|not|or)\b'


def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!={'version','steps'} or type(plan['version']) is not int or plan['version']!=1:raise ValueError('Command plan version 1 required')
    steps=plan['steps']
    if not isinstance(steps,list) or not 1<=len(steps)<=6:raise ValueError('1–6 allowlisted command steps required')
    for step in steps:
        if not isinstance(step,dict) or set(step)!={'tool','params'} or not isinstance(step['tool'],str) or step['tool'] not in TOOLS or not isinstance(step['params'],dict):raise ValueError('Unsupported command; approval/deletion/code execution are unavailable')
        tool,p=step['tool'],step['params']
        allowed={'length','minimum_coverage'} if tool=='composite' else {'method','composite_length'} if tool=='estimate_blocks' else set()
        if set(p)-allowed:raise ValueError('Unsupported command parameter')
        if tool=='composite' and 'length' not in p:raise ValueError('Specify composite length in metres')
        if tool=='estimate_blocks' and (not isinstance(p.get('method'),str) or p['method'] not in METHODS):raise ValueError('Explicit NN/IDW/OK/SK method required')
        for key in ('length','composite_length','minimum_coverage'):
            if key in p:
                v=p[key]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 or v>(1 if key=='minimum_coverage' else 1000):raise ValueError('Invalid composite length or coverage')
    return deepcopy(plan)


def parse_command(question):
    if not isinstance(question,str) or not 1<=len(question.strip())<=2000:raise ValueError('Command length 1–2000 required')
    if re.search(FORBIDDEN,question):raise ValueError('AI cannot approve resources, delete data or execute code')
    steps=[];text=question.casefold()
    if 'композит' in text or 'composite' in text:
        match=re.search(r'(?i)(\d+(?:\.\d+)?)\s*(?:метр|метрээр|м\b|m\b)',question)
        if not match:raise ValueError('Example: 5 метрээр композит хий')
        steps.append({'tool':'composite','params':{'length':float(match.group(1))}})
    method=re.search(r'(?i)\b(IDW|NN|OK|SK)\b',question)
    if method:steps.append({'tool':'estimate_blocks','params':{'method':{'idw':'idw','nn':'nearest','ok':'kriging','sk':'simple_kriging'}[method.group(1).lower()]}})
    if not steps:
        if re.search(r'(?i)qa\s*/?\s*qc',question):steps.append({'tool':'qaqc_summary','params':{}})
        elif ('ангил' in text and 'санал' in text) or 'classification proposal' in text:steps.append({'tool':'classification_proposal','params':{}})
        elif ('төс' in text and 'шалга' in text) or text.strip() in ('validate','validate project','check project'):steps.append({'tool':'validate_project','params':{}})
    if not steps:raise ValueError('Supported examples: Төслийг шалга; 5 метрээр композит хий; IDW бод; QA/QC шалга')
    return validate_plan({'version':1,'steps':steps})


def execute_plan(project,plan,command_id=None,cancel=None,progress=None):
    """No IO, no live-project mutation; callers apply the detached result once."""
    from .estimation import sample_support,estimate_model
    from .geostat_tools import propose_classes
    from .quality_advisor import quality_advice
    plan=validate_plan(plan);candidate=deepcopy(project);results=[];length=None;coverage=None
    command_id=command_id or uuid4().hex
    for i,step in enumerate(plan['steps']):
        if cancel and cancel():raise RuntimeError('AI command cancelled; project unchanged')
        tool,p=step['tool'],step['params']
        if progress:progress(i,len(plan['steps']))
        if tool=='validate_project':candidate.validate();result={'valid':True}
        elif tool=='composite':
            length=p['length'];coverage=p.get('minimum_coverage',1.);samples=sample_support(candidate,length,coverage)
            candidate.workspace['ai_composites']={'length_m':length,'minimum_coverage':p.get('minimum_coverage',1.),'samples':samples,'command_id':command_id}
            result={'samples':len(samples),'length_m':length,'source_assays_unchanged':True}
        elif tool=='estimate_blocks':
            model=candidate.workspace.get('block_model') or {}
            if not all(k in model for k in ('bounds','size','params')):raise ValueError('Configure a block extent, size and estimation/search parameters in the application first')
            params=deepcopy(model['params']);params['method']=p['method']
            if p['method'] in ('kriging','simple_kriging') and not all(k in params for k in ('nugget','partial_sill','range_m')):raise ValueError('Configure and review variogram nugget, partial_sill and range_m first')
            if p['method']=='simple_kriging' and 'mean' not in params:raise ValueError('Configure the simple-kriging mean first')
            for key,value in candidate.workspace.get('estimation_overrides',{}).items():
                if key in ('high_grade_restriction','dynamic_anisotropy'):params[key]=deepcopy(value)
            if 'composite_length' in p:params['composite_length']=p['composite_length']
            elif length is not None:params['composite_length']=length
            if coverage is not None:params['minimum_coverage']=coverage
            def inner(value,total):
                if progress:progress(i*100+int(100*value/max(1,total)),len(plan['steps'])*100)
            if any(b.get('resource_class') is not None for b in model.get('blocks',[])):raise ValueError('Existing reviewed resource classes require manual model replacement; AI cannot discard them')
            output=estimate_model(candidate,model['bounds'],model['size'],params,model.get('domain'),cancel,inner)
            old_blocks=model['blocks'];new_blocks=output['blocks']
            geometry=('x','y','z','dx','dy','dz')
            if len(old_blocks)!=len(new_blocks) or any(any(a.get(k)!=b.get(k) for k in geometry) for a,b in zip(old_blocks,new_blocks)):
                raise ValueError('Model geometry differs from the configured grid; use manual model replacement')
            for old,new in zip(old_blocks,new_blocks):
                for key in ('density','domain','rock'):
                    if key in old:new[key]=deepcopy(old[key])
            candidate.workspace['block_model']=output;result={'blocks':len(output['blocks']),'method':p['method'],'run_sha256':output['run_sha256']}
        elif tool=='classification_proposal':
            model=candidate.workspace.get('block_model',{});rules=model.get('classification_proposal_rules')
            if not rules:raise ValueError('A professional must configure classification proposal rules first')
            output,result=propose_classes(model,rules);candidate.workspace['block_model']=output
        else:
            rows=candidate.workspace.get('qaqc_controls',{}).get('results',[])
            if not rows:raise ValueError('Import QA/QC controls first')
            report=quality_advice(rows);result={'text':report['text'],'issues':report['issues']}
        results.append({'step':i+1,'tool':tool,'result':result})
        if progress:progress((i+1)*100,len(plan['steps'])*100)
    if cancel and cancel():raise RuntimeError('AI command cancelled; project unchanged')
    changed=any(s['tool'] in MUTATIONS for s in plan['steps'])
    if changed:
        receipts=candidate.workspace.setdefault('ai_command_receipts',[])
        receipts.append({'id':command_id,'utc':datetime.now(timezone.utc).isoformat(),'plan':plan,'status':'computed_pending_apply'})
        candidate.workspace['ai_command_receipts']=receipts[-50:]
    candidate.validate()
    if changed:
        from .core import project_text
        project_text(candidate)  # Reject an unsaveable candidate before the UI commit.
    return {'candidate':candidate,'changed':changed,'results':results,'command_id':command_id,'plan':plan}


class AuditJournal:
    """Local append-only NDJSON outside Undo snapshots; not a tamper-proof server log."""
    def __init__(self,path=None):
        if path is None:
            from .local_engine import data_root
            path=data_root().parent/'audit'/'ai-commands.jsonl'
        self.path=Path(path)
    def append(self,command_id,event,**details):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        record={'id':command_id,'utc':datetime.now(timezone.utc).isoformat(),'event':event,**details}
        raw=json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
        with self.path.open('a',encoding='utf-8') as file:file.write(raw);file.flush();os.fsync(file.fileno())
        return record
    def tail(self,limit=200):
        from collections import deque
        if not self.path.exists():return []
        with self.path.open(encoding='utf-8') as file:lines=deque(file,maxlen=limit)
        return [json.loads(line) for line in lines]
