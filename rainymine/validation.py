"""Non-mutating, multi-issue SRS VAL-01…VAL-10 preflight for raw table records.

Rows use the application's lower-case keys. No assay-tag substitution or depth
extension is automatic; every result carries source table, 1-based row and field.
"""
from collections import defaultdict
import math
import numpy as np
from .core import direction,dot


def numeric(value):
    if isinstance(value,bool):return None
    try:value=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return value if math.isfinite(value) else None


def parse_assay_tag(value, policy='null'):
    """Explicit lab policy; half_detection substitutes only strict <positive DL."""
    if policy not in ('null','half_detection'):raise ValueError('Assay tag policy буруу.')
    number=numeric(value)
    if number is not None:return {'value':number,'qualifier':'numeric','source':value}
    text=str(value).strip().upper()
    if text.startswith('<'):
        dl=numeric(text[1:])
        if dl is None or dl<=0:raise ValueError('Detection limit буруу.')
        return {'value':dl/2 if policy=='half_detection' else None,'qualifier':'below_detection','detection_limit':dl,'source':value}
    if text in ('','NS','SNR','IS'):return {'value':None,'qualifier':text or 'missing','source':value}
    raise ValueError('Танихгүй assay тэмдэглэгээ: '+text)


def validate_tables(tables, tolerance=1e-4, max_dogleg=5., sigma=4., elevation=None, max_dz=15.):
    """Accumulate all issues without requiring already-valid Project objects.

    `elevation(x,y)` must return DTM Z or None outside coverage; no extrapolation.
    Mean±sigma standard deviations is a warning heuristic, not a robust outlier test.
    """
    if any(numeric(x) is None or float(x)<0 for x in (tolerance,max_dogleg,sigma,max_dz)) or sigma==0:
        raise ValueError('Validation threshold буруу.')
    issues=[]
    def add(code,level,table,row,hole,field,message):
        issues.append({'code':code,'severity':level,'table':table,'row':row,'hole_id':hole,'field':field,'message':message})
    collars={};xyz=[]
    for row,r in enumerate(tables.get('collars',[]),1):
        hole=r.get('hole_id');coords=[numeric(r.get(k)) for k in ('x','y','z')];depth=numeric(r.get('depth'))
        if not isinstance(hole,str) or not hole.strip() or hole in collars:
            add('VAL-08','Critical','collars',row,hole,'hole_id','Хоосон / давхардсан collar ID.')
        else:collars[hole]=(row,r,depth)
        if depth is None or depth<=0 or any(v is None for v in coords):
            add('VAL-06','Critical','collars',row,hole,'depth/xyz','Collar гүн / координат буруу.')
        else:xyz.append((row,hole,coords))
    groups={};sample_ids=set()
    for table in ('surveys','assays','lithology','structure','geotech'):
        grouped=defaultdict(list);seen=set()
        for row,r in enumerate(tables.get(table,[]),1):
            hole=r.get('hole_id');h=collars.get(hole)
            if h is None:add('VAL-01','Critical',table,row,hole,'hole_id','Collar олдсонгүй.')
            interval=table in ('assays','lithology','geotech')
            start=numeric(r.get('from_m' if interval else 'depth'));end=numeric(r.get('to_m')) if interval else start
            key=(hole,start,end)
            if key in seen:add('VAL-08','Critical',table,row,hole,'depth','Давхардсан интервал / гүн.')
            seen.add(key)
            sample=r.get('sample_id')
            if sample:
                if sample in sample_ids:add('VAL-08','Critical',table,row,hole,'sample_id','Sample ID давхардсан.')
                sample_ids.add(sample)
            if start is None or end is None or start<0 or (interval and end<=start):
                add('VAL-05','Critical',table,row,hole,'from_m/to_m' if interval else 'depth','Гүн / интервал буруу.')
            else:
                grouped[hole].append((start,end,row,r))
                if h and h[2] is not None and end>h[2]+tolerance:
                    add('VAL-06','Critical',table,row,hole,'to_m' if interval else 'depth','Collar нийт гүнээс хэтэрсэн.')
            if table=='assays' and numeric(r.get('grade')) is None:
                try:parse_assay_tag(r.get('grade'));level='Info'
                except ValueError:level='Critical'
                add('VAL-09',level,table,row,hole,'grade','Assay tag / missing / invalid: '+str(r.get('grade')))
            if table=='surveys':
                az=numeric(r.get('azimuth'));dip=numeric(r.get('dip'))
                if az is None or dip is None or not 0<=az<360 or not -90<=dip<=90:
                    add('VAL-07','Critical',table,row,hole,'azimuth/dip','Survey өнцөг буруу.')
        groups[table]=grouped
        if table in ('assays','lithology','geotech'):
            for hole,records in grouped.items():
                records.sort(key=lambda x:x[0]);furthest=None
                for start,end,row,r in records:
                    if furthest is not None:
                        if start<furthest-tolerance:add('VAL-03','Critical',table,row,hole,'from_m','Өмнөх интервалтай давхцсан.')
                        elif start>furthest+tolerance:add('VAL-04','Warning',table,row,hole,'from_m','Интервалын завсар байна.')
                    furthest=max(furthest,end) if furthest is not None else end
    for hole,(row,r,depth) in collars.items():
        records=sorted(groups['surveys'].get(hole,[]))
        if not records or abs(records[0][0])>tolerance:
            add('VAL-02','Warning','surveys',records[0][2] if records else None,hole,'depth','0 м-ийн survey алга; collar fallback байна.')
        for a,b in zip(records,records[1:]):
            az1,d1,az2,d2=[numeric(v) for v in (a[3].get('azimuth'),a[3].get('dip'),b[3].get('azimuth'),b[3].get('dip'))]
            if None in (az1,d1,az2,d2) or not (0<=az1<360 and 0<=az2<360 and -90<=d1<=90 and -90<=d2<=90) or b[0]<=a[0]:continue
            angle=math.degrees(math.acos(max(-1.,min(1.,dot(direction(az1,d1),direction(az2,d2))))))
            if angle*30/(b[0]-a[0])>max_dogleg:
                add('VAL-07','Error','surveys',b[2],hole,'azimuth/dip','Dogleg босго давсан.')
    if xyz:
        values=np.asarray([r[2] for r in xyz]);mean=values.mean(axis=0);std=values.std(axis=0)
        for row,hole,coord in xyz:
            outlier=bool(np.any(np.abs(np.asarray(coord)-mean)>sigma*std+1e-9))
            dem=elevation(*coord[:2]) if elevation else None
            if dem is not None and numeric(dem) is None:raise ValueError('DTM elevation буруу.')
            if outlier or (dem is not None and abs(coord[2]-dem)>max_dz):
                add('VAL-10','Warning','collars',row,hole,'xyz','Spatial / DTM outlier; гараар шалгана уу.')
    return issues
