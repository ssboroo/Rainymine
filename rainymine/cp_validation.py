"""Evidence pack for a qualified reviewer, never an automatic validation letter."""
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import tempfile
from .benchmark import compare_reference, block_totals
from .core import Trajectory
from .ebmz_report import write_csv


def _read(path,required):
    path=Path(path)
    if path.stat().st_size>32_000_000:raise ValueError('Reference CSV exceeds 32 MB')
    raw=path.read_bytes();text=raw.decode('utf-8-sig')
    import io
    reader=csv.DictReader(io.StringIO(text,newline=''));headers=reader.fieldnames or []
    if len(set(headers))!=len(headers) or not set(required)<=set(headers):raise ValueError('Reference CSV columns: '+', '.join(required))
    rows=[]
    for row in reader:
        if len(rows)>=50000 or None in row or any(v is None for v in row.values()):raise ValueError('Invalid reference rows / limit exceeded')
        rows.append(row)
    if not rows:raise ValueError('Reference CSV is empty')
    return rows,hashlib.sha256(raw).hexdigest()


def _finite(value):
    value=float(value)
    if not math.isfinite(value):raise ValueError('Nonfinite validation data')
    return value


def comparison_chart(title,rows,xkey,actual_key,reference_key):
    """Self-contained SVG; missing values break lines instead of bridging gaps."""
    if not rows:return ''
    stride=max(1,math.ceil(len(rows)/2000));rows=rows[::stride]
    xs=[r[xkey] for r in rows];ys=[r[k] for r in rows for k in (actual_key,reference_key) if r.get(k) is not None]
    if not ys:return '<p>'+html.escape(title)+': no estimated data</p>'
    xmin,xmax=min(xs),max(xs);ymin,ymax=min(0,min(ys)),max(ys)
    if xmax==xmin:xmax=xmin+1
    if ymax==ymin:ymax=ymin+1
    parts=['<h3>'+html.escape(title)+'</h3><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300" style="max-width:1000px;width:100%;background:#f5f9fb">',
           '<path d="M80 20V250H970" fill="none" stroke="#456"/>']
    for key,color,label in ((actual_key,'#008f92','RAINYMINE'),(reference_key,'#bb643e','Reference')):
        current=[]
        def flush():
            if current:parts.append('<polyline fill="none" stroke="'+color+'" stroke-width="2" points="'+' '.join(current)+'"/>');current.clear()
        for r in rows:
            y=r.get(key)
            if y is None:flush();continue
            x=80+890*(r[xkey]-xmin)/(xmax-xmin);y=250-230*(y-ymin)/(ymax-ymin)
            current.append(f'{x:.3f},{y:.3f}')
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="2" fill="{color}"/>')
        flush()
        parts.append(f'<text x="{650 if key==actual_key else 820}" y="285" fill="{color}">{label}</text>')
    parts.extend([f'<text x="80" y="275">{xmin:.5g}</text><text x="900" y="275">{max(xs):.5g}</text>',
                  f'<text x="5" y="30">{ymax:.5g}</text><text x="5" y="245">{ymin:.5g}</text></svg>',
                  '<p>Display stride '+str(stride)+'; complete values in CSV/JSON.</p>'])
    return ''.join(parts)


def difference(actual,reference,relative,absolute=0):
    if actual is None or reference is None:return {'difference':None,'relative_percent':None,'passed':False}
    error=actual-reference
    return {'difference':error,'relative_percent':100*error/abs(reference) if reference else (0. if not actual else None),
            'passed':abs(error)<=absolute+relative*abs(reference)}


def trajectory_comparison(project,path,tolerance,cancel=None):
    rows,digest=_read(path,('hole_id','depth','x','y','z'))
    surveys={}
    for row in project.surveys:surveys.setdefault(row.hole_id,[]).append(row)
    traces={h.hole_id:Trajectory(h,surveys.get(h.hole_id,[]),'minimum_curvature') for h in project.collars}
    seen=set();compared=[];holes=set()
    for i,row in enumerate(rows):
        if i%1000==0 and cancel and cancel():raise RuntimeError('CP comparison cancelled')
        name=row['hole_id'];depth=_finite(row['depth']);key=(name,depth)
        if key in seen:raise ValueError('Duplicate trajectory hole/depth')
        seen.add(key)
        if name not in traces:
            compared.append({'hole_id':name,'depth':depth,'status':'unknown_hole','passed':False});continue
        actual=traces[name].at(depth);expected=[_finite(row[k]) for k in 'xyz']
        error=math.dist(actual,expected);holes.add(name)
        compared.append({'hole_id':name,'depth':depth,'error_m':error,'passed':error<=tolerance,
                         **{'actual_'+k:v for k,v in zip('xyz',actual)},**{'reference_'+k:v for k,v in zip('xyz',expected)}})
    return {'reference_sha256':digest,'rows':compared,'reviewed_holes':len(holes),
            'project_holes':len(traces),'all_holes_covered':bool(traces) and len(holes)==len(traces),
            'numerical_pass':bool(traces) and len(holes)==len(traces) and all(r['passed'] for r in compared),
            'tolerance_m':tolerance,'scope':'only supplied measured depths; no unsampled trajectory certification'}


def _reference_blocks(path):
    rows,digest=_read(path,('x','y','z','dx','dy','dz','grade'));blocks=[]
    for row in rows:
        b={k:_finite(row[k]) for k in ('x','y','z','dx','dy','dz')}
        if min(b[k] for k in ('dx','dy','dz'))<=0:raise ValueError('Reference dimensions must be positive')
        b['grade']=None if row['grade'].strip().upper() in ('','NULL','NONE','NAN') else _finite(row['grade'])
        b['density']=None if row.get('density','').strip().upper() in ('','NULL','NONE','NAN') else _finite(row['density'])
        if b['density'] is not None and b['density']<=0:raise ValueError('Reference density must be positive')
        if 'domain' in row:b['domain']=row['domain']
        blocks.append(b)
    return blocks,digest


def swath_comparison(actual,reference,width,relative,absolute,cancel=None):
    result=[]
    for axis in 'xyz':
        def bins(blocks):
            values={}
            for i,b in enumerate(blocks):
                if i%1000==0 and cancel and cancel():raise RuntimeError('CP swath cancelled')
                key=math.floor(b[axis]/width);r=values.setdefault(key,[0.,0.,0.]);v=math.prod(b[k] for k in ('dx','dy','dz'))
                if b.get('grade') is None:r[2]+=v
                else:r[0]+=v;r[1]+=v*b['grade']
            return values
        a,r=bins(actual),bins(reference)
        for key in sorted(a.keys()|r.keys()):
            av,rv=a.get(key,[0,0,0]),r.get(key,[0,0,0])
            ag=av[1]/av[0] if av[0] else None;rg=rv[1]/rv[0] if rv[0] else None
            check=difference(ag,rg,relative,absolute)
            if ag is None and rg is None and av[2]==rv[2]:check.update(passed=True,applicable=False)
            result.append({'axis':axis.upper(),'from_m':key*width,'to_m':(key+1)*width,
                'actual_grade':ag,'reference_grade':rg,'actual_unestimated_volume_m3':av[2],
                'reference_unestimated_volume_m3':rv[2],**check})
    return result


def create_validation_pack(project,block_reference,trajectory_reference,metadata_path,destination,
                           settings,cancel=None):
    from pyproj import CRS
    model=project.workspace.get('block_model')
    if not model or not model.get('blocks') or len(model['blocks'])>50000:raise ValueError('CP reference pack supports desktop models up to 50000 blocks')
    if Path(metadata_path).stat().st_size>1_000_000:raise ValueError('Validation metadata exceeds 1 MB')
    raw_meta=Path(metadata_path).read_bytes();meta=json.loads(raw_meta.decode('utf-8-sig'))
    if meta.get('grade_unit')!=project.grade_unit or not project.crs_code or CRS.from_user_input(meta.get('crs'))!=CRS.from_user_input(project.crs_code):raise ValueError('Explicit reference CRS/grade unit must match the project')
    reference_crs=CRS.from_user_input(project.crs_code)
    if not reference_crs.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in reference_crs.axis_info[:2]):raise ValueError('CP comparison requires projected metre coordinates')
    relative=_finite(settings.get('relative',.02));absolute=_finite(settings.get('grade_absolute',.001));tolerance=_finite(settings.get('coordinate_m',.01));width=_finite(settings.get('swath_width_m',50))
    if not 0<=relative<=1 or absolute<0 or tolerance<=0 or width<=0:raise ValueError('Invalid CP comparison tolerances')
    cutoffs=[_finite(c) for c in settings.get('cutoffs',[0])]
    if not 1<=len(cutoffs)<=100 or any(c<0 for c in cutoffs) or cutoffs!=sorted(set(cutoffs)):raise ValueError('1–100 distinct ascending nonnegative cutoffs required')
    density=settings.get('density');density=None if density in ('',None) else _finite(density)
    if density is not None and density<=0:raise ValueError('Fallback density must be positive')
    if cancel and cancel():raise RuntimeError('CP validation cancelled')
    comparator=compare_reference(model,block_reference,tolerance,absolute,relative,project.grade_unit,density)
    reference,reference_digest=_reference_blocks(block_reference);actual=model['blocks']
    if reference_digest!=comparator['reference_sha256']:raise ValueError('Reference file changed during validation; retry with a stable snapshot')
    trajectory=trajectory_comparison(project,trajectory_reference,tolerance,cancel)
    swaths=swath_comparison(actual,reference,width,relative,absolute,cancel)
    curves=[]
    for cutoff in cutoffs:
        if cancel and cancel():raise RuntimeError('CP curve cancelled')
        totals=[]
        for blocks in (actual,reference):
            selected=[b for b in blocks if b.get('grade') is not None and b['grade']>=cutoff]
            t=block_totals(selected,project.grade_unit,density)
            t['mean_grade']=t['contained_metal_tonnes']/(.01 if project.grade_unit=='%' else 1e-6)/t['tonnes'] if t['tonnes'] and t['contained_metal_tonnes'] is not None else None
            totals.append(t)
        a,r=totals
        for field in ('volume_m3','tonnes','mean_grade','contained_metal_tonnes'):
            check=difference(a[field],r[field],relative,absolute if field=='mean_grade' else 0)
            if field=='mean_grade' and a['blocks']==r['blocks']==0:check.update(passed=True,applicable=False)
            curves.append({'cutoff':cutoff,'metric':field,'actual':a[field],'reference':r[field],**check})
    gates={'block_geometry_null_grade':comparator['numerical_pass'],'trajectory':trajectory['numerical_pass'],
           'swath':all(r['passed'] for r in swaths),'grade_tonnage':all(r['passed'] for r in curves),
           'source_hash_matches':meta.get('reference_sha256')==comparator['reference_sha256'],
           'trajectory_hash_matches':meta.get('trajectory_sha256')==trajectory['reference_sha256'],
           'same_estimation_parameters_declared':meta.get('estimation_parameters')==model.get('params') and bool(model.get('params')),
           'same_grid_orientation_declared':meta.get('grid_angles')==model.get('grid_angles',[90,0,0]),
           'authorization_declared':meta.get('authorized_for_validation') is True,
           'source_version_declared':bool(meta.get('source_software')) and bool(meta.get('source_version'))}
    report={'status':'NUMERICAL_CHECKS_PASS_REVIEW_PENDING' if all(gates.values()) else 'REVIEW_REQUIRED',
            'independent_review_verified':False,'gates':gates,'settings':settings,'reference_provenance':meta,
            'metadata_sha256':hashlib.sha256(raw_meta).hexdigest(),'block_comparison':comparator,
            'trajectory':trajectory,'swath':swaths,'grade_tonnage':curves,
            'model_blocks_sha256':hashlib.sha256(json.dumps(actual,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            'scope':'comparison of supplied data and declared parameters; no wireframe overlap, geological validity, CP competence or global software certification',
            'review_notice':'±1–2% is a project-selected numerical threshold, not automatic JORC/EBMZ approval or entitlement to a validation letter.'}
    destination=Path(destination)
    if destination.exists():raise ValueError('Validation destination already exists')
    stage=Path(tempfile.mkdtemp(prefix='.cp-review-',dir=destination.parent))
    try:
        (stage/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        for name,rows in [('trajectory',trajectory['rows']),('swath',swaths),('grade-tonnage',curves)]:
            columns=list(dict.fromkeys(k for row in rows for k in row));write_csv(stage/(name+'.csv'),rows,columns)
        checklist=[{'Хянах зүйл':name,'Автомат шалгалт':passed,'Мэргэжилтний тэмдэглэл':''} for name,passed in gates.items()]
        checklist += [{'Хянах зүйл':item,'Автомат шалгалт':'ХИЙГДЭЭГҮЙ','Мэргэжилтний тэмдэглэл':''} for item in ('Өгөгдлийн гарал ба ашиглах зөвшөөрөл','CP / мэргэшсэн геологичийн эрх, туршлага','Wireframe / домэйны геологийн үндэслэл','Композит, top-cut, variogram, search, discretization, NULL дүрэм','Локал алдаа ба зөрүү бүрийн шалтгаан','Тайлангийн хамрах хүрээ, хязгаарлалт, гарын үсэг, огноо')]
        write_csv(stage/'review-checklist.csv',checklist,['Хянах зүйл','Автомат шалгалт','Мэргэжилтний тэмдэглэл'])
        escaped=html.escape(json.dumps({k:v for k,v in report.items() if k not in ('block_comparison','trajectory','swath','grade_tonnage')},ensure_ascii=False,indent=2))
        sections=[]
        for axis in 'XYZ':
            sections.append(comparison_chart('Swath '+axis+' • volume-weighted grade',
                            [r for r in swaths if r['axis']==axis],'from_m','actual_grade','reference_grade'))
        for metric in ('tonnes','mean_grade','contained_metal_tonnes'):
            sections.append(comparison_chart('Grade–tonnage • '+metric,[r for r in curves if r['metric']==metric],
                            'cutoff','actual','reference'))
        for title,rows in [('Trajectory',trajectory['rows']),('Swath',swaths),('Grade–tonnage',curves)]:
            columns=list(dict.fromkeys(k for row in rows for k in row));sections.append('<h2>'+title+'</h2><table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in columns)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in columns)+'</tr>' for r in rows[:500])+'</table><p>Full rows: CSV / JSON</p>')
        (stage/'review.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:14px sans-serif;color:#19364c;margin:30px}table{border-collapse:collapse}td,th{border:1px solid #bacbd4;padding:5px}pre{white-space:pre-wrap}</style><h1>RAINYMINE • CP хяналтын багц</h1><p>МЭРГЭЖИЛТНИЙ ХЯНАЛТ ХҮЛЭЭГДЭЖ БАЙНА</p><pre>'+escaped+'</pre>'+''.join(sections),encoding='utf-8')
        if cancel and cancel():raise RuntimeError('CP validation cancelled')
        stage.rename(destination)
        return {'path':str(destination),'status':report['status'],'gates':gates,'independent_review_verified':False}
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise
