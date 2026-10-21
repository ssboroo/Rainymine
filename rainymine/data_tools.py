"""Transactional data preparation; no network or silent data repair."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import csv
import hashlib
import math
from .core import finite, Collar, Survey, Assay, Lithology

SCHEMAS={
 'collars':('hole_id','x','y','z','depth','azimuth','dip'),
 'surveys':('hole_id','depth','azimuth','dip'),
 'assays':('hole_id','from_m','to_m','grade'),
 'lithology':('hole_id','from_m','to_m','rock'),
 'surface':('x','y','z')}

class History:
    """Bounded full-project snapshots; edits are validated before commit."""
    def __init__(self,limit=20):self.undo_items=[];self.redo_items=[];self.limit=limit
    def apply(self,current,candidate,label):
        candidate.validate();self.undo_items.append((label,deepcopy(current)))
        self.undo_items=self.undo_items[-self.limit:];self.redo_items=[];return candidate
    def undo(self,current):
        if not self.undo_items:return current
        label,p=self.undo_items.pop();self.redo_items.append((label,deepcopy(current)));return p
    def redo(self,current):
        if not self.redo_items:return current
        label,p=self.redo_items.pop();self.undo_items.append((label,deepcopy(current)));return p

def validate_mapping(kind, mapping, headers=None):
    """Require complete, one-to-one mappings; never silently remap a profile."""
    if kind not in SCHEMAS or not isinstance(mapping, dict):
        raise ValueError('Импортын төрөл / баганын тохиргоо буруу.')
    if (set(mapping) != set(SCHEMAS[kind]) or
            any(not isinstance(v, str) or not v.strip() for v in mapping.values()) or
            len(set(mapping.values())) != len(mapping)):
        raise ValueError('Багана бүрийг давхардуулахгүй тохируулна уу.')
    if headers is not None and not set(mapping.values()).issubset(headers):
        raise ValueError('Загварын багана CSV файлд алга. Тохиргоог шалгана уу.')
    return dict(mapping)


def save_mapping_profile(project, name, kind, mapping):
    """Return a validated project copy so profile changes participate in undo."""
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('Загварын нэр 1–80 тэмдэгт байна.')
    mapping = validate_mapping(kind, mapping)
    candidate = deepcopy(project)
    profiles = candidate.workspace.setdefault('mapping_profiles', {})
    profiles.setdefault(kind, {})[name] = mapping
    candidate.validate()
    return candidate


def mapping_profile(project, name, kind, headers):
    profiles = project.workspace.get('mapping_profiles', {}).get(kind, {})
    if name not in profiles:
        raise ValueError('Баганын загвар олдсонгүй.')
    return validate_mapping(kind, profiles[name], headers)


def csv_preview(path):
    if Path(path).stat().st_size>32_000_000:raise ValueError('CSV хэмжээ 32 MB-аас их.')
    with open(path,encoding='utf-8-sig',newline='') as f:
        sample=f.read(8192);f.seek(0)
        try:delimiter=csv.Sniffer().sniff(sample,delimiters=',;\t').delimiter
        except csv.Error:delimiter=','
        reader=csv.DictReader(f,delimiter=delimiter);headers=reader.fieldnames or []
        if not headers or any(not h.strip() for h in headers) or len(set(headers))!=len(headers):raise ValueError('CSV гарчиг хоосон эсвэл давхардсан.')
        rows=[]
        for _,r in zip(range(8),reader):rows.append(r)
    return headers,rows,delimiter

def mapped_import(path,kind,mapping,delimiter=','):
    mapping=validate_mapping(kind,mapping)
    schema=SCHEMAS[kind]
    rows=[];issues=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter=delimiter)
        headers=reader.fieldnames or []
        if not headers or any(not h.strip() for h in headers) or len(set(headers))!=len(headers):
            raise ValueError('CSV гарчиг хоосон эсвэл давхардсан.')
        validate_mapping(kind,mapping,headers)
        for i,row in enumerate(reader,2):
            if i>100001:raise ValueError('CSV 100000 мөрөөс их.')
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('Мөрийн баганын тоо гарчигтай тохирохгүй.')
                item={}
                for field in schema:
                    raw=row[mapping[field]]
                    if raw is None or not raw.strip():raise ValueError(field+' хоосон')
                    value=raw.strip() if field in ('hole_id','rock') else float(raw)
                    if field not in ('hole_id','rock'):finite(value)
                    item[field]=value
                rows.append(item)
            except (TypeError,ValueError,KeyError) as e:issues.append({'row':i,'error':str(e)})
    report={'source_name':Path(path).name,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'kind':kind,'mapping':mapping,'delimiter':delimiter,'accepted':len(rows),'rejected':len(issues),'issues':issues}
    if not rows and not issues:raise ValueError('CSV өгөгдөлгүй.')
    return rows,report

def rows_to_values(kind,rows):
    if kind=='surface':return [[r[k] for k in ('x','y','z')] for r in rows]
    cls={'collars':Collar,'surveys':Survey,'assays':Assay,'lithology':Lithology}[kind]
    return [cls(**r) for r in rows]

def transform_project(project,source,target):
    """Horizontal projected/geographic CRS transform; retain Z and measured depths.
    Bearings are rotated using local projected tangents / geodesic tangents.
    A vertical datum conversion is deliberately not inferred.
    """
    from pyproj import CRS, Transformer, network
    network.set_network_enabled(False)
    src,dst=CRS.from_user_input(source),CRS.from_user_input(target)
    if not dst.is_projected or any(abs(axis.unit_conversion_factor-1)>1e-9 for axis in dst.axis_info[:2]):
        raise ValueError('Зорилтот CRS нь метрийн проекц байна.')
    if not (src.is_projected or src.is_geographic):raise ValueError('Эх CRS дэмжигдэхгүй.')
    if src.is_projected and any(abs(axis.unit_conversion_factor-1)>1e-9 for axis in src.axis_info[:2]):raise ValueError('Эх проекц метрийн нэгжтэй байна.')
    if project.workspace.get('meshes') or project.workspace.get('strings') or project.workspace.get('block_model'):
        raise ValueError('Геометр/блок модель үүсгэхийн өмнө CRS хөрвүүлнэ үү.')
    t=Transformer.from_crs(src,dst,always_xy=True,allow_ballpark=False,only_best=True)
    def xy(x,y):
        a,b=t.transform(x,y,errcheck=True);finite(a,b);return a,b
    def bearing(x,y,az):
        if src.is_geographic:
            x2,y2,_=src.get_geod().fwd(x,y,az,10)
        else:x2,y2=x+10*math.sin(math.radians(az)),y+10*math.cos(math.radians(az))
        a,b=xy(x,y);c,d=xy(x2,y2)
        return math.degrees(math.atan2(c-a,d-b))%360
    result=deepcopy(project);collars={h.hole_id:h for h in project.collars}
    result.collars=[replace(h,x=xy(h.x,h.y)[0],y=xy(h.x,h.y)[1],azimuth=bearing(h.x,h.y,h.azimuth)) for h in project.collars]
    result.surveys=[replace(s,azimuth=bearing(collars[s.hole_id].x,collars[s.hole_id].y,s.azimuth)) for s in project.surveys]
    result.surface=[[*xy(p[0],p[1]),p[2]] for p in project.surface]
    result.crs=dst.to_string();result.crs_code=dst.to_string()
    result.workspace.setdefault('transforms',[]).append({'source':src.to_string(),'target':dst.to_string(),'operation':t.description,'accuracy_m':t.accuracy,'z':'unchanged; no vertical datum conversion','azimuth':'local horizontal bearing rotation; no measured-depth rescaling'})
    return result.validate()

def qaqc_assays(project):
    project.validate();by={};results=[]
    for a in project.assays:by.setdefault(a.hole_id,[]).append(a)
    for h in project.collars:
        aa=sorted(by.get(h.hole_id,[]),key=lambda a:a.from_m);cursor=0
        for a in aa:
            if a.from_m>cursor:results.append({'type':'gap','hole_id':h.hole_id,'from_m':cursor,'to_m':a.from_m,'message':'Сорьцгүй интервал'})
            cursor=a.to_m
        if cursor<h.depth:results.append({'type':'gap','hole_id':h.hole_id,'from_m':cursor,'to_m':h.depth,'message':'Сорьцгүй интервал'})
    return results

def evaluate_controls(rows,blank_limit=.05,relative_limit=.2,z_limit=3):
    """No deletion. Standards use certified SD; duplicates use symmetric RPD."""
    finite(blank_limit,relative_limit,z_limit)
    if min(blank_limit,relative_limit)<0 or z_limit<=0:raise ValueError('QA/QC хязгаар буруу.')
    result=[]
    for i,row in enumerate(rows,2):
        kind=str(row['type']).strip().lower();measured=float(row['measured']);finite(measured)
        if measured<0:raise ValueError(f'{i}: хэмжилт сөрөг.')
        statistic=None
        if kind=='blank':statistic=measured;passed=measured<=blank_limit
        elif kind=='standard':
            expected,sd=float(row['expected']),float(row['sd']);finite(expected,sd)
            if sd<=0:raise ValueError('Стандартын SD эерэг байна.')
            statistic=(measured-expected)/sd;passed=abs(statistic)<=z_limit
        elif kind=='duplicate':
            other=float(row['expected']);finite(other)
            if other<0:raise ValueError('Хос сорьцын агуулга сөрөг.')
            statistic=0. if measured+other==0 else abs(measured-other)/((measured+other)/2);passed=statistic<=relative_limit
        else:raise ValueError(f'QA/QC төрөл дэмжигдэхгүй: {kind}')
        result.append({'row':i,'sample_id':row.get('sample_id',''),'type':kind,'statistic':statistic,'passed':passed})
    return result
