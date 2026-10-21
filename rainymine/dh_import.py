"""Portable DH CSV archive and explicit one-analyte projection into the core schema.

All source bytes remain recoverable inside .rmine. Auxiliary/long tables are not
forced through the 100k scientific-row admission limit or flattened into grades.
"""
import base64,csv,hashlib,io,json,math,zlib
from collections import Counter,defaultdict
from pathlib import Path
from .core import Project,Collar,Assay,Lithology,finite,MAX_FILE

NAMES={'dh_collar.csv','dh_assay.csv','dh_assay_pivoted.csv','dh_geochemistry.csv','dh_geology.csv',
       'dh_alteration.csv','dh_event.csv','dh_geotech.csv','dh_hyperspectral.csv','dh_recovery.csv','dh_specgrav.csv'}
NULLS={'','NULL','NONE','NAN','N/A'}


def scan_sources(paths,cancel=None):
    files={};total=0
    for path in paths:
        if cancel and cancel():raise RuntimeError('DH импорт цуцлагдлаа.')
        path=Path(path);name=path.name.lower()
        if name not in NAMES:raise ValueError('DH багцын танигдаагүй нэр: '+path.name)
        if name in files:raise ValueError('DH файл давхардсан: '+name)
        if path.stat().st_size>32_000_000:raise ValueError('DH нэг файл 32 MB-аас их.')
        data=path.read_bytes();total+=len(data)
        if len(data)>32_000_000 or total>128_000_000:raise ValueError('DH source хэмжээний хязгаар хэтэрсэн.')
        try:reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
        except UnicodeError as error:raise ValueError('DH CSV UTF-8 encoding шаардлагатай.') from error
        headers=reader.fieldnames or []
        if not headers or len(set(headers))!=len(headers) or any(not h for h in headers):raise ValueError('DH CSV header буруу: '+name)
        count=0;empty=False;parse_issues=[]
        for line,row in enumerate(reader,2):
            if cancel and line%2000==0 and cancel():raise RuntimeError('DH импорт цуцлагдлаа.')
            values=[v for k,v in row.items() if k is not None and v is not None]
            if values and values[0].strip().lower()=='no data found' and all(not v.strip() for v in values[1:]):
                if count or empty:raise ValueError('No data found нь өгөгдлийн мөртэй холилдсон: '+name)
                empty=True;continue
            if not values or all(not v.strip() for v in values):continue
            if empty:raise ValueError('No data found нь өгөгдөлтэй холилдсон: '+name)
            if None in row or any(v is None for v in row.values()):parse_issues.append({'row':line,'reason':'column count mismatch; raw retained, not projected'})
            count+=1
            if count>300000:raise ValueError('DH нэг файл 300000 мөрөөс их.')
        compressed=base64.b64encode(zlib.compress(data,6)).decode('ascii')
        files[name]={'headers':headers,'rows':count,'parse_issues':parse_issues,'valid_rows':count-len(parse_issues),'empty_marker':empty,'bytes':len(data),
                     'sha256':hashlib.sha256(data).hexdigest(),'codec':'zlib+base64','data':compressed}
    if 'dh_collar.csv' not in files:raise ValueError('DH импортод dh_collar.csv хамт сонгоно уу.')
    if sum(len(v['data']) for v in files.values())>12_000_000:raise ValueError('DH шахсан archive 12MB-аас их; багцыг хуваана уу.')
    return {'version':1,'files':files}


def source_bytes(bundle,name):
    entry=bundle['files'][name]
    if entry.get('codec')!='zlib+base64' or type(entry.get('bytes')) is not int or not 0<=entry['bytes']<=32_000_000:raise ValueError('DH archive metadata буруу.')
    try:
        compressed=base64.b64decode(entry['data'],validate=True);decoder=zlib.decompressobj();data=decoder.decompress(compressed,32_000_001)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(data)!=entry['bytes']:raise ValueError('DH archive хэмжээ буруу.')
    except (ValueError,zlib.error,KeyError) as error:raise ValueError('DH archive эвдэрсэн.') from error
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('DH эх файлын SHA256 тохирохгүй.')
    return data


def source_rows(bundle,name,raw=False):
    reader=csv.DictReader(io.StringIO(source_bytes(bundle,name).decode('utf-8-sig'),newline=''))
    for line,row in enumerate(reader,2):
        if bundle['files'][name]['empty_marker']:return
        if not any(v and v.strip() for v in row.values() if isinstance(v,str)):continue
        if None in row or any(v is None for v in row.values()):
            if not raw:continue
            extras=row.pop(None,[]);row['_extra_columns']=json.dumps(extras,ensure_ascii=False);row['_parse_issue']='column count mismatch; original recoverable'
        yield line,row


def source_page(bundle,name,page=0,size=200):
    if type(page) is not int or page<0 or type(size) is not int or not 1<=size<=500:raise ValueError('DH page буруу.')
    out=[]
    for index,(line,row) in enumerate(source_rows(bundle,name,raw=True)):
        if index<page*size:continue
        if len(out)==size:break
        out.append({'source_row':line,**row})
    return out


def options(bundle):
    channels=[];raw_units=defaultdict(set);conflicts=[]
    if 'dh_assay.csv' in bundle['files']:
        for line,row in source_rows(bundle,'dh_assay.csv'):raw_units[row['attributecolumn']].add(row['units'])
        channels=[('dh_assay.csv',column,unit) for column,units in sorted(raw_units.items()) for unit in sorted(units)]
    if 'dh_assay_pivoted.csv' in bundle['files']:
        for h in bundle['files']['dh_assay_pivoted.csv']['headers']:
            if '_' not in h:continue
            column,unit=h.rsplit('_',1)
            if unit.upper() not in ('PPM','PCT','PERCENT','GPT'):continue
            if column in raw_units and {u.upper() for u in raw_units[column]}!={unit.upper()}:
                conflicts.append({'column':h,'raw_units':sorted(raw_units[column])});continue
            channels.append(('dh_assay_pivoted.csv',column,unit))
    rocks=sorted({r['attributecolumn'] for line,r in source_rows(bundle,'dh_geology.csv')}) if 'dh_geology.csv' in bundle['files'] else []
    return {'channels':channels,'lithology_columns':rocks,'pivot_unit_conflicts':conflicts}


def measurement(raw,qualifier,policy):
    """Keep censored results out by default. Never infer negative metal grades."""
    text=str(raw).strip()
    if text.upper() in NULLS:return None,'missing'
    less=text.startswith('<') or qualifier.strip().upper() in ('<','LDL','BDL','BELOW DETECTION')
    if text.startswith('>') or qualifier.strip()=='>':return None,'upper_censored'
    try:value=float(text.lstrip('<').strip());finite(value)
    except ValueError:return None,'non_numeric'
    if value<0:less=True
    if less:
        if policy=='exclude':return None,'below_detection_excluded'
        if policy=='half_limit':return abs(value)/2,'below_detection_half_limit'
        raise ValueError('Detection limit policy буруу.')
    return value,'measured'


def _nonoverlap(items,report,kind):
    groups=defaultdict(list);out=[]
    for item,source in items:groups[item.hole_id].append((item,source))
    for hole,rows in groups.items():
        rows.sort(key=lambda r:(r[0].from_m,r[0].to_m));cluster=[];end=-math.inf
        def flush():
            if len(cluster)==1:out.append(cluster[0][0])
            elif cluster:
                for item,source in cluster:report['issues'].append({'kind':kind,'row':source,'hole_id':hole,'reason':'overlapping interval; held out, original retained'})
        for item,source in rows:
            if cluster and item.from_m>=end:flush();cluster=[];end=-math.inf
            cluster.append((item,source));end=max(end,item.to_m)
        flush()
    return out


def project_from_bundle(bundle,channel=None,lithology_column=None,policy='exclude',name='DH импорт',cancel=None):
    if policy not in ('exclude','half_limit'):raise ValueError('Detection policy exclude/half_limit байна.')
    report={'sources':[{ 'file':n,**{k:v for k,v in f.items() if k not in ('data','headers')}} for n,f in bundle['files'].items()],
            'channel':list(channel) if channel else None,'lithology_column':lithology_column,'detection_policy':policy,'issues':[],
            'survey':'NO DOWNHOLE SURVEY: collar azimuth/dip straight-hole assumption only; not measured trajectories','measurement_counts':{}}
    report['source_parse_issues']=[{'file':n,**issue} for n,f in bundle['files'].items() for issue in f.get('parse_issues',[])]
    p=Project(name=name);ids={};names={};systems=set();heights=set();normalised=0
    for line,row in source_rows(bundle,'dh_collar.csv'):
        if cancel and cancel():raise RuntimeError('DH импорт цуцлагдлаа.')
        try:
            hole=row['companyholeid'].strip();source_id=row['id'];az=float(row['azimuth']);dip=float(row['dip'])
            if az==360:az=0.;normalised+=1
            h=Collar(hole,float(row['easting']),float(row['northing']),float(row['elevation']),float(row['maxdepth']),az,dip)
            Project(collars=[h]).validate()
            if hole in names or source_id in ids:raise ValueError('Collar ID / companyholeid давхардсан; нийлүүлэхгүй.')
            datum=row['datum'].strip().upper();zone=int(row['zone']);projection=row['projection'].strip().upper()
            if datum!='GDA94' or projection not in ('UTM','MAP GRID OF AUSTRALIA (MGA)') or not 48<=zone<=58:raise ValueError('Энэ DH preset зөвхөн GDA94 / MGA Australia zone 48…58 дэмжинэ.')
            systems.add(28300+zone);heights.add(row.get('height_datum','unspecified'));ids[source_id]=h;names[hole]=h;p.collars.append(h)
        except (ValueError,KeyError,TypeError) as error:raise ValueError(f'dh_collar.csv мөр {line}: {error}') from error
    if not p.collars:raise ValueError('Collar өгөгдөл алга.')
    if len(systems)!=1:raise ValueError('DH амсрууд өөр CRS zone-той; эхлээд CRS-ээр тусгаарлана уу.')
    from pyproj import CRS
    p.crs_code=f'EPSG:{systems.pop()}';crs=CRS.from_user_input(p.crs_code);p.crs=crs.name+' · Z: '+', '.join(sorted(heights))+' · Surveyгүй: амсрын өнцгөөр шулуун таамаг'
    report.update(crs=p.crs_code,height_datums=sorted(heights),azimuth_360_to_0=normalised)
    if channel:
        source,column,unit=channel
        units={'PPM':'ppm','GPT':'g/t','PCT':'%','PERCENT':'%'}
        if unit.upper() not in units:raise ValueError('Assay нэгжийг таамаглахгүй: '+unit)
        if source=='dh_assay_pivoted.csv' and 'dh_assay.csv' in bundle['files']:
            raw_units={row['units'].upper() for line,row in source_rows(bundle,'dh_assay.csv') if row['attributecolumn']==column}
            if raw_units and raw_units!={unit.upper()}:raise ValueError('Pivot баганын unit эх assay-тай зөрсөн; raw dh_assay channel сонгоно уу.')
        p.grade_unit=units[unit.upper()];selected=[];counts=Counter()
        for line,row in source_rows(bundle,source):
            if cancel and line%1000==0 and cancel():raise RuntimeError('DH импорт цуцлагдлаа.')
            if source=='dh_assay.csv':
                if row['attributecolumn']!=column or row['units']!=unit:continue
                raw=row['attributevalue'];qualifier=row.get('dsc','')
            elif source=='dh_assay_pivoted.csv':raw=row[column+'_'+unit];qualifier=''
            else:raise ValueError('Assay source дэмжихгүй.')
            value,state=measurement(raw,qualifier,policy);counts[state]+=1
            if value is None:continue
            try:
                h=names[row['companyholeid']];item=Assay(h.hole_id,float(row['fromdepth']),float(row['todepth']),value)
                if not 0<=item.from_m<item.to_m<=h.depth or (p.grade_unit=='%' and value>100):raise ValueError('Интервал/агуулга зөвшөөрөгдөх хязгаараас гарсан.')
                selected.append((item,line))
            except (ValueError,KeyError) as error:report['issues'].append({'kind':'assay','row':line,'reason':str(error)})
        p.assays=_nonoverlap(selected,report,'assay');report['measurement_counts']=dict(counts)
    if lithology_column and 'dh_geology.csv' in bundle['files']:
        selected=[]
        for line,row in source_rows(bundle,'dh_geology.csv'):
            if cancel and line%1000==0 and cancel():raise RuntimeError('DH импорт цуцлагдлаа.')
            if row['attributecolumn']!=lithology_column:continue
            rock=row['attributevalue'].strip()
            if rock.upper() in NULLS:continue
            try:
                h=ids[row['collarid']];item=Lithology(h.hole_id,float(row['fromdepth']),float(row['todepth']),rock)
                if not 0<=item.from_m<item.to_m<=h.depth or len(rock)>100:raise ValueError('Lithology интервал / rock code буруу.')
                selected.append((item,line))
            except (ValueError,KeyError) as error:report['issues'].append({'kind':'lithology','row':line,'reason':str(error)})
        p.lithology=_nonoverlap(selected,report,'lithology')
    report.update(collars=len(p.collars),active_assays=len(p.assays),active_lithology=len(p.lithology),survey_stations=0)
    p.workspace={'dh_bundle':bundle,'dh_import_report':report};p.validate()
    if len(json.dumps(p.to_dict(),ensure_ascii=False,allow_nan=False).encode())>MAX_FILE:raise ValueError('DH төсөл 32MB хязгаараас их; эх багцыг хуваана уу.')
    return p,report
