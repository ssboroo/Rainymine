"""Persisted display settings and named sections; does not alter source assays."""
from copy import deepcopy
from .core import finite

DEFAULT_STYLE={'visible':True,'opacity':1.,'representation':'surface','color':None}

def validate_viewing(workspace):
    from .render_controls import validate_workspace
    validate_workspace(workspace)
    styles=workspace.get('layer_styles',{})
    if not isinstance(styles,dict):raise ValueError('Давхаргын тохиргооны бүтэц буруу.')
    for key,style in styles.items():
        if not isinstance(key,str) or len(key)>100 or not isinstance(style,dict):raise ValueError('Давхаргын нэр/тохиргоо буруу.')
        if set(style)-set(DEFAULT_STYLE):raise ValueError('Давхаргын тохиргооны төрөл дэмжигдэхгүй.')
        merged={**DEFAULT_STYLE,**style};finite(merged['opacity'])
        if type(merged['visible'])!=bool or not 0<=merged['opacity']<=1 or merged['representation'] not in ('surface','wireframe','points'):raise ValueError('Давхаргын харагдац буруу.')
        color=merged['color']
        if color is not None:
            if not isinstance(color,(list,tuple)) or len(color)!=3:raise ValueError('RGB өнгө буруу.')
            finite(*color)
            if any(not 0<=c<=1 for c in color):raise ValueError('RGB утга 0–1 байна.')
    sections=workspace.get('sections',[])
    if not isinstance(sections,list) or len(sections)>200:raise ValueError('Огтлолын жагсаалт буруу.')
    names=set()
    for s in sections:
        if not isinstance(s,dict) or not isinstance(s.get('name'),str) or not s['name'].strip() or len(s['name'])>80 or s['name'] in names:raise ValueError('Огтлолын нэр хоосон эсвэл давхардсан.')
        validate_section(s.get('values'));names.add(s['name'])
    positions=workspace.get('block_slice_positions')
    if positions is not None:
        if not isinstance(positions,list) or len(positions)!=3:raise ValueError('Зүсэлтийн X/Y/Z байрлал буруу.')
        finite(*positions)
        model=workspace.get('block_model')
        if model and any(not model['bounds'][i]<=p<model['bounds'][i+3] for i,p in enumerate(positions)):raise ValueError('Зүсэлтийн байрлал model bounds дотор байна (max орохгүй).')

def validate_section(values):
    if not isinstance(values,(list,tuple)) or len(values)!=3:raise ValueError('Огтлолын азимут/шилжилт/зузаан шаардлагатай.')
    az,offset,width=values;finite(*values)
    if not 0<=az<360 or not .1<=width<=200000 or abs(offset)>100000:raise ValueError('Огтлолын тохиргоо хязгаараас гарсан.')

def styled_project(project,key,changes):
    p=deepcopy(project);style=p.workspace.setdefault('layer_styles',{}).setdefault(key,{})
    style.update(changes);p.validate();return p

def named_section(project,name,values):
    name=name.strip();validate_section(values);p=deepcopy(project)
    sections=p.workspace.setdefault('sections',[]);sections[:]=[s for s in sections if s['name']!=name]
    sections.append({'name':name,'values':list(values)});p.validate();return p
