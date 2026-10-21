"""Metric drillhole geometry. North-clockwise azimuth, negative-down dip.
Minimum curvature integrates spherical interpolation of tangent vectors.
No estimation, reserve classification or economic assumptions are made.
"""
from dataclasses import dataclass, asdict, field
from pathlib import Path
import csv
import io
import json
import math
import os
import tempfile

MAX_ROWS = 100_000
MAX_FILE = 32_000_000

@dataclass(frozen=True)
class Collar:
    hole_id: str
    x: float
    y: float
    z: float
    depth: float
    azimuth: float = 0
    dip: float = -90

@dataclass(frozen=True)
class Survey:
    hole_id: str
    depth: float
    azimuth: float
    dip: float

@dataclass(frozen=True)
class Assay:
    hole_id: str
    from_m: float
    to_m: float
    grade: float

@dataclass
class Project:
    name: str = 'Шинэ төсөл'
    crs: str = 'Локал метрийн координат — CRS тодорхойлоогүй'
    grade_unit: str = '%'
    collars: list = field(default_factory=list)
    surveys: list = field(default_factory=list)
    assays: list = field(default_factory=list)
    surface: list = field(default_factory=list)

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name)>200:
            raise ValueError('Төслийн нэр 1–200 тэмдэгт байна.')
        if not isinstance(self.crs,str) or len(self.crs)>300:
            raise ValueError('Координатын системийн тайлбар буруу.')
        if self.grade_unit not in ('%', 'g/t', 'ppm'):
            raise ValueError('Агуулгын нэгж: %, g/t эсвэл ppm.')
        for rows in (self.collars,self.surveys,self.assays,self.surface):
            if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ValueError('Хүснэгтийн хэмжээ хэтэрсэн.')
        if len(self.collars)>5000:raise ValueError('Энэ хувилбарт 5000 хүртэл цооног дэмжинэ.')
        holes={}
        for h in self.collars:
            if not isinstance(h.hole_id,str) or not h.hole_id.strip() or len(h.hole_id)>80 or h.hole_id in holes:
                raise ValueError('Цооногийн нэр хоосон, давхардсан эсвэл хэт урт.')
            finite(h.x,h.y,h.z,h.depth,h.azimuth,h.dip)
            if max(abs(h.x),abs(h.y),abs(h.z))>1e9 or not 0<h.depth<=20000:raise ValueError(f'{h.hole_id}: координат/гүн зөвшөөрөгдөх хязгаараас гарсан.')
            angles(h.azimuth,h.dip);holes[h.hole_id]=h
        stations={}; intervals={}
        for s in self.surveys:
            finite(s.depth,s.azimuth,s.dip);angles(s.azimuth,s.dip)
            if s.hole_id not in holes or not 0<=s.depth<=holes[s.hole_id].depth:raise ValueError('Survey: цооног олдохгүй эсвэл гүн зөрүүтэй.')
            stations.setdefault(s.hole_id,[]).append(s)
        for name,ss in stations.items():
            ss=sorted(ss,key=lambda s:s.depth)
            if ss[0].depth!=0:raise ValueError(f'{name}: survey 0 метрээс эхэлнэ.')
            for a,b in zip(ss,ss[1:]):
                if a.depth==b.depth:raise ValueError(f'{name}: survey гүн давхардсан.')
                if dot(direction(a.azimuth,a.dip),direction(b.azimuth,b.dip))<-.999999:raise ValueError('180° эргэлттэй survey тооцох боломжгүй.')
        for a in self.assays:
            finite(a.from_m,a.to_m,a.grade)
            if a.hole_id not in holes or not 0<=a.from_m<a.to_m<=holes[a.hole_id].depth or a.grade<0:
                raise ValueError('Сорьц: цооног, интервал эсвэл агуулга буруу.')
            if self.grade_unit=='%' and a.grade>100:raise ValueError('Хувийн агуулга 100%-аас их байж болохгүй.')
            intervals.setdefault(a.hole_id,[]).append(a)
        for name,aa in intervals.items():
            aa=sorted(aa,key=lambda a:a.from_m)
            if any(a.to_m>b.from_m for a,b in zip(aa,aa[1:])):raise ValueError(f'{name}: сорьцын интервал давхардсан.')
        seen=set()
        for p in self.surface:
            if not isinstance(p,(tuple,list)) or len(p)!=3:raise ValueError('Гадаргын цэг X,Y,Z байна.')
            finite(*p)
            if max(map(abs,p))>1e9:raise ValueError('Гадаргын координат хэт их.')
            key=(p[0],p[1])
            if key in seen:raise ValueError('Гадаргын XY координат давхардсан.')
            seen.add(key)
        if self.surface and len(self.surface)<3:raise ValueError('Гадаргад 3-аас цөөнгүй цэг хэрэгтэй.')
        if self.surface:
            a,b=self.surface[:2];dx,dy=b[0]-a[0],b[1]-a[1]
            extent=max(max(p[i] for p in self.surface)-min(p[i] for p in self.surface) for i in (0,1))
            if max(abs(dx*(p[1]-a[1])-dy*(p[0]-a[0])) for p in self.surface)<=1e-12*max(1,extent**2):
                raise ValueError('Гадаргын бүх цэг нэг шулуунд байна. TIN үүсгэх боломжгүй.')
        return self

    def to_dict(self):
        self.validate()
        return {'format':'rainymine','version':1,'units':'metres',**asdict(self)}

    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict) or data.get('format')!='rainymine' or data.get('version')!=1 or data.get('units')!='metres':
            raise ValueError('Дэмжигдээгүй RAINYMINE төслийн формат.')
        try:
            p=cls(name=data['name'],crs=data['crs'],grade_unit=data['grade_unit'],
                collars=[Collar(**r) for r in data['collars']],surveys=[Survey(**r) for r in data['surveys']],
                assays=[Assay(**r) for r in data['assays']],surface=data['surface'])
        except (KeyError,TypeError) as exc:raise ValueError('Төслийн өгөгдлийн бүтэц буруу.') from exc
        return p.validate()

def finite(*values):
    if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in values):
        raise ValueError('Зөвхөн бодит, төгсгөлөг тоон утга зөвшөөрнө.')

def angles(az,dip):
    if not 0<=az<360 or not -90<=dip<=0:raise ValueError('Азимут 0 ≤ A < 360, налуу −90 ≤ D ≤ 0 байна.')

def dot(a,b):return sum(x*y for x,y in zip(a,b))

def direction(azimuth,dip):
    a,d=map(math.radians,(azimuth,dip))
    return (math.cos(d)*math.sin(a),math.cos(d)*math.cos(a),math.sin(d))

def displacement(length,u,v):
    """Minimum-curvature interval displacement (metres)."""
    cosine=max(-1.,min(1.,dot(u,v)));theta=math.acos(cosine)
    if theta>math.pi-1e-5:raise ValueError('180° эргэлтийг тооцох боломжгүй.')
    rf=1. if theta<1e-8 else 2*math.tan(theta/2)/theta
    return tuple(length*(a+b)*rf/2 for a,b in zip(u,v))

def slerp(u,v,t):
    theta=math.acos(max(-1.,min(1.,dot(u,v))))
    if theta<1e-8:return u
    if theta>math.pi-1e-5:raise ValueError('180° эргэлт.')
    return tuple((math.sin((1-t)*theta)*a+math.sin(t*theta)*b)/math.sin(theta) for a,b in zip(u,v))

class Trajectory:
    def __init__(self,collar,surveys):
        self.collar=collar
        self.stations=sorted([s for s in surveys if s.hole_id==collar.hole_id],key=lambda s:s.depth)
        if not self.stations:self.stations=[Survey(collar.hole_id,0,collar.azimuth,collar.dip)]
        if self.stations[-1].depth<collar.depth:
            s=self.stations[-1];self.stations.append(Survey(collar.hole_id,collar.depth,s.azimuth,s.dip))
        self.positions=[(collar.x,collar.y,collar.z)]
        for a,b in zip(self.stations,self.stations[1:]):
            d=displacement(b.depth-a.depth,direction(a.azimuth,a.dip),direction(b.azimuth,b.dip))
            self.positions.append(tuple(x+y for x,y in zip(self.positions[-1],d)))

    def at(self,depth):
        finite(depth)
        if not 0<=depth<=self.collar.depth:raise ValueError('Хэмжсэн гүн цооногийн хязгаараас гарсан.')
        if depth==self.collar.depth:return self.positions[-1]
        for i,(a,b) in enumerate(zip(self.stations,self.stations[1:])):
            if a.depth<=depth<=b.depth:
                u=direction(a.azimuth,a.dip);v=direction(b.azimuth,b.dip)
                t=(depth-a.depth)/(b.depth-a.depth)
                d=displacement(depth-a.depth,u,slerp(u,v,t))
                return tuple(x+y for x,y in zip(self.positions[i],d))
        return self.positions[0]

    def sample(self,start=0,end=None,step=5):
        end=self.collar.depth if end is None else end
        if not 0<=start<=end<=self.collar.depth or step<=0:raise ValueError('Замналын муж буруу.')
        depths={start,end,*[s.depth for s in self.stations if start<s.depth<end]}
        n=math.ceil((end-start)/step)
        if n>20000:raise ValueError('Замналын алхам хэт бага.')
        depths.update(min(end,start+i*step) for i in range(n))
        return [(d,self.at(d)) for d in sorted(depths)]

def atomic_write(path,text):
    p=Path(path);fd,temp=tempfile.mkstemp(dir=p.parent,prefix='.rainymine-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def save_project(path,project):atomic_write(path,json.dumps(project.to_dict(),ensure_ascii=False,indent=2,allow_nan=False))

def load_project(path):
    if Path(path).stat().st_size>MAX_FILE:raise ValueError('Төсөл 32 MB-аас их байна.')
    return Project.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))

def read_rows(path,columns):
    if Path(path).stat().st_size>MAX_FILE:raise ValueError('CSV 32 MB-аас их байна.')
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not set(columns).issubset(reader.fieldnames or []):raise ValueError('Шаардлагатай баганууд: '+', '.join(columns))
        rows=[]
        for i,row in enumerate(reader,2):
            if i>MAX_ROWS+1:raise ValueError('CSV мөрийн хязгаар хэтэрсэн.')
            try:
                parsed={k:str(row[k]).strip() if k=='hole_id' else float(row[k]) for k in columns}
                finite(*[v for k,v in parsed.items() if k!='hole_id']);rows.append(parsed)
            except (ValueError,TypeError) as exc:raise ValueError(f'CSV {i}-р мөр: тоон утга буруу.') from exc
    if not rows:raise ValueError('CSV хоосон байна.')
    return rows

def read_collars(path):return [Collar(**r) for r in read_rows(path,('hole_id','x','y','z','depth','azimuth','dip'))]
def read_surveys(path):return [Survey(**r) for r in read_rows(path,('hole_id','depth','azimuth','dip'))]
def read_assays(path):return [Assay(**r) for r in read_rows(path,('hole_id','from_m','to_m','grade'))]
def read_surface(path):return [[r[k] for k in ('x','y','z')] for r in read_rows(path,('x','y','z'))]

def export_trajectories(path,project):
    out=io.StringIO(newline='');w=csv.writer(out);w.writerow(('hole_id','depth','x','y','z'))
    for h in project.collars:
        for depth,p in Trajectory(h,project.surveys).sample():w.writerow((h.hole_id,depth,*p))
    atomic_write(path,'\ufeff'+out.getvalue())

def composite_assays(project,length=5):
    """Length-weighted bins anchored at 0, omitting missing support.
    Coverage is explicit; gaps are never assigned zero grade.
    """
    finite(length)
    if length<=0:raise ValueError('Композитын урт эерэг байна.')
    project.validate();result=[]
    if sum(math.ceil(h.depth/length) for h in project.collars)>MAX_ROWS:raise ValueError('Композитын тоо хэт их.')
    by_hole={}
    for a in project.assays:by_hole.setdefault(a.hole_id,[]).append(a)
    for h in project.collars:
        assays=sorted(by_hole.get(h.hole_id,[]),key=lambda a:a.from_m)
        cursor=0
        for i in range(math.ceil(h.depth/length)):
            start=i*length;end=min(h.depth,start+length);support=weighted=0.
            while cursor<len(assays) and assays[cursor].to_m<=start:cursor+=1
            for a in assays[cursor:]:
                if a.from_m>=end:break
                overlap=max(0.,min(end,a.to_m)-max(start,a.from_m));support+=overlap;weighted+=overlap*a.grade
            if support:result.append({'hole_id':h.hole_id,'from_m':start,'to_m':end,'grade':weighted/support,'support_m':support,'coverage':support/(end-start)})
    return result

def write_records(path,rows,fields):
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows(rows)
    atomic_write(path,'\ufeff'+out.getvalue())

def demo():
    p=Project(name='ЖИШЭЭ • Өрөмдлөгийн талбай',crs='Зохиомол локал метрийн систем — бодит орд биш')
    for i in range(20):
        name=f'RM-{i+1:03}';depth=180+(i*23)%150
        p.collars.append(Collar(name,500000+(i%5)*90,5300000+(i//5)*110,1450+10*math.sin(i),depth,(i*37)%360,-65))
        p.surveys.extend([Survey(name,0,(i*37)%360,-65),Survey(name,depth,(i*37+25)%360,-80)])
        for j in range(0,depth,10):p.assays.append(Assay(name,j,min(j+10,depth),round(.2+2.8*math.exp(-((j-depth*.55)/40)**2)+(i%3)*.1,3)))
    for x in range(-1,7):
        for y in range(-1,6):p.surface.append([500000+x*90,5300000+y*110,1460+12*math.sin(x*.6)*math.cos(y*.7)])
    return p.validate()
