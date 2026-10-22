"""Declarative replay only. No Python, shell or arbitrary function execution."""
from copy import deepcopy
from .estimation import estimate_model,sample_support
from .geostat_tools import cap_analysis,cell_decluster,propose_classes

TOOLS={'validate','composite','estimate','cap_analysis','decluster','classification_proposal','contact_rbf','report'}


def validate_recipe(recipe):
    if not isinstance(recipe,dict) or set(recipe)-{'version','name','steps'} or recipe.get('version')!=1:raise ValueError('Workflow version 1 required')
    steps=recipe.get('steps',[])
    if not isinstance(steps,list) or not 1<=len(steps)<=20:raise ValueError('Workflow requires 1–20 steps')
    for i,step in enumerate(steps):
        if not isinstance(step,dict) or set(step)!={'tool','params'} or step['tool'] not in TOOLS or not isinstance(step['params'],dict):raise ValueError('Unsupported workflow step')
        if step['tool']=='report' and i!=len(steps)-1:raise ValueError('Report may only be the final step')
    return deepcopy(recipe)


def run_workflow(project,recipe,report_destination=None,cancel=None,progress=None):
    recipe=validate_recipe(recipe);candidate=deepcopy(project);log=[]
    for index,step in enumerate(recipe['steps']):
        if cancel and cancel():raise RuntimeError('Workflow cancelled; original project unchanged')
        tool,p=step['tool'],deepcopy(step['params'])
        if tool=='validate':candidate.validate();result={'valid':True}
        elif tool=='composite':result={'samples':len(sample_support(candidate,**p))}
        elif tool=='estimate':
            if set(p)-{'bounds','size','params','domain'}:raise ValueError('Unsupported estimate parameters')
            model=estimate_model(candidate,**p,cancel=cancel);candidate.workspace['block_model']=model;result={'blocks':len(model['blocks'])}
        elif tool=='cap_analysis':
            result=cap_analysis(sample_support(candidate,p.pop('composite_length',5)),**p)
        elif tool=='decluster':
            result=cell_decluster(sample_support(candidate,p.pop('composite_length',5)),**p)
        elif tool=='classification_proposal':
            model,result=propose_classes(candidate.workspace.get('block_model',{}),**p);candidate.workspace['block_model']=model
        elif tool=='contact_rbf':
            from .implicit_domains import contact_surface
            controls=candidate.workspace.get('contact_controls',[])
            mesh,result=contact_surface(controls,**p,cancel=cancel);mesh['contact_guide_surface']=True
            candidate.workspace['meshes']=[m for m in candidate.workspace.get('meshes',[]) if not m.get('contact_guide_surface')]+[mesh]
        else:
            if report_destination is None:raise ValueError('Report output folder must be selected outside the workflow recipe')
            from .ebmz_report import export_pack
            candidate.validate();result={'path':export_pack(candidate,p,report_destination,cancel or (lambda:False))}
        log.append({'step':index+1,'tool':tool,'result':result})
        if progress:progress(index+1,len(recipe['steps']))
    candidate.validate()
    return candidate,log
