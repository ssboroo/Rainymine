"""Compare a saved model with externally supplied reference CSV; no self-certification."""
import csv
import hashlib
import io
import math
import json
import html
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from .core import finite


def compare_reference(model,path,coordinate_tolerance=.01,grade_absolute=.001,grade_relative=.01,
                      grade_unit=None,density=None,geometry_relative=1e-6):
    finite(coordinate_tolerance,grade_absolute,grade_relative)
    finite(geometry_relative)
    if coordinate_tolerance<=0 or min(grade_absolute,grade_relative,geometry_relative)<0:raise ValueError('Benchmark tolerance буруу.')
    if grade_unit is not None and grade_unit not in ('%','ppm','g/t'):raise ValueError('Grade unit буруу.')
    if density is not None:
        finite(density)
        if density<=0:raise ValueError('Density must be positive')
    path=Path(path)
    if path.stat().st_size>32_000_000:raise ValueError('Reference CSV 32 MB-аас их.')
    raw=path.read_bytes()
    if len(raw)>32_000_000:raise ValueError('Reference CSV 32 MB-аас их.')
    with io.StringIO(raw.decode('utf-8-sig'),newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or not {'x','y','z','grade'}<=set(reader.fieldnames):
            raise ValueError('Reference CSV x,y,z,grade баганатай байна.')
        reference=[]
        for row in reader:
            if None in row or any(v is None for v in row.values()):raise ValueError('Reference CSV баганын тоо зөрсөн.')
            values=[float(row[k]) for k in ('x','y','z')];finite(*values)
            grade=float(row['grade']) if row['grade'].strip() else None
            if grade is not None:
                finite(grade)
                if grade<0 or (grade_unit=='%' and grade>100):raise ValueError('Resolve invalid/censored grade before comparison')
            parsed={**row,**dict(zip(('x','y','z'),values)),'grade':grade}
            for key in ('dx','dy','dz','density'):
                if key in row:
                    parsed[key]=float(row[key]);finite(parsed[key])
                    if parsed[key]<=0:raise ValueError(key+' must be positive')
            if any(k in row for k in ('dx','dy','dz')) and not all(k in row for k in ('dx','dy','dz')):raise ValueError('All dx/dy/dz required')
            reference.append(parsed)
            if len(reference)>50000:raise ValueError('Reference 50000 мөрөөс их.')
    if not reference or not model['blocks']:raise ValueError('Reference/model өгөгдөлгүй.')
    ref=np.array([[r[k] for k in ('x','y','z')] for r in reference]);xyz=np.array([[b[a] for a in ('x','y','z')] for b in model['blocks']])
    if not np.isfinite(xyz).all():raise ValueError('Model coordinates must be finite')
    if len(np.unique(ref,axis=0))!=len(ref):raise ValueError('Reference coordinate давхардсан.')
    tree=cKDTree(xyz);used=set();rows=[]
    for i,r in enumerate(reference):
        matches=tree.query_ball_point(ref[i],coordinate_tolerance)
        if len(matches)!=1 or matches[0] in used:
            rows.append({'reference_row':i+2,'status':'ambiguous_or_missing_coordinate','passed':False});continue
        index=matches[0];used.add(index);block=model['blocks'][index];observed=block.get('grade')
        checks={}
        for key in ('dx','dy','dz','density'):
            if key in r:
                actual=block.get(key)
                if actual is None and key=='density':actual=density
                checks[key]=actual is not None and math.isfinite(actual) and abs(actual-r[key])<=geometry_relative*abs(r[key])+1e-9
        if 'domain' in r:checks['domain']=str(block.get('domain',''))==r['domain']
        if observed is None and r['grade'] is None:
            rows.append({'reference_row':i+2,'model_index':index,'status':'both_unestimated','checks':checks,'passed':all(checks.values())});continue
        if observed is None or r['grade'] is None:
            rows.append({'reference_row':i+2,'status':'unestimated','passed':False});continue
        finite(observed)
        if observed<0 or (grade_unit=='%' and observed>100):raise ValueError('Invalid model grade')
        error=observed-r['grade'];tolerance=grade_absolute+grade_relative*abs(r['grade'])
        rows.append({'reference_row':i+2,'status':'compared','model_index':index,'expected':r['grade'],'actual':observed,'error':float(error),'checks':checks,'passed':bool(abs(error)<=tolerance and all(checks.values()))})
    complete=len(used)==len(model['blocks'])==len(ref)
    totals={'reference':block_totals(reference,grade_unit,density),'model':block_totals(model['blocks'],grade_unit,density)}
    differences={k:totals['model'][k]-totals['reference'][k] for k in ('volume_m3','tonnes','contained_metal_tonnes') if totals['model'][k] is not None and totals['reference'][k] is not None}
    errors=[r['error'] for r in rows if 'error' in r]
    return {'source_name':path.name,'reference_sha256':hashlib.sha256(raw).hexdigest(),'model_run_sha256':model.get('run_sha256'),
            'coordinate_tolerance':coordinate_tolerance,'grade_absolute':grade_absolute,'grade_relative':grade_relative,
            'reference_count':len(ref),'model_count':len(model['blocks']),'complete_coverage':complete,
            'numerical_pass':complete and all(r['passed'] for r in rows),'rows':rows,
            'grade_unit':grade_unit,'fallback_density_t_m3':density,'geometry_relative':geometry_relative,
            'checked_fields':['x','y','z','grade']+[k for k in ('dx','dy','dz','density','domain') if k in reference[0]],
            'totals':totals,'total_differences':differences,
            'grade_error_summary':{'count':len(errors),'bias':sum(errors)/len(errors) if errors else None,'rmse':math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,'max_absolute':max(map(abs,errors),default=None)},
            'scope':'Centre, dimensions and optional attributes; not mesh overlap, orientation or geological validity',
            'independent_review_verified':False,'review_status':'PENDING — external provenance, real-deposit authorization and qualified geologist sign-off required'}


def block_totals(blocks,grade_unit=None,density=None):
    volumes=[];tonnes=[];metals=[];unestimated=0;estimated_tonnes=[]
    factor={'%':.01,'ppm':1e-6,'g/t':1e-6}.get(grade_unit)
    for block in blocks:
        dims=[block.get(k) for k in ('dx','dy','dz')]
        volume=math.prod(dims) if all(v is not None and math.isfinite(v) and v>0 for v in dims) else None
        rho=block.get('density') if block.get('density') is not None else density
        weight=volume*rho if volume is not None and rho is not None and math.isfinite(rho) and rho>0 else None
        grade=block.get('grade')
        if grade is None:unestimated+=1
        elif not math.isfinite(grade):raise ValueError('Non-finite grade')
        volumes.append(volume);tonnes.append(weight)
        if grade is not None and weight is not None:
            estimated_tonnes.append(weight)
            if factor is not None:metals.append(weight*grade*factor)
    return {'blocks':len(blocks),'unestimated_blocks':unestimated,
            'volume_m3':math.fsum(volumes) if all(v is not None for v in volumes) else None,
            'tonnes':math.fsum(tonnes) if all(v is not None for v in tonnes) else None,
            'estimated_tonnes':math.fsum(estimated_tonnes),
            'contained_metal_tonnes':math.fsum(metals) if factor is not None and len(metals)==len(blocks)-unestimated else None,
            'metal_scope':'estimated blocks only; unestimated material excluded, not assigned zero grade'}


def write_comparison_report(path,result):
    """Escaped, standalone review report; JSON remains available for automation."""
    from .core import atomic_write
    encoded=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if Path(path).suffix.lower()=='.json':atomic_write(path,encoded);return
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(row.get(k,'')))+'</td>' for k in ('reference_row','status','expected','actual','error','checks','passed'))+'</tr>' for row in result['rows'])
    summary={k:v for k,v in result.items() if k!='rows'}
    atomic_write(path,'<!doctype html><html lang="mn"><meta charset="utf-8"><title>RAINYMINE — Reference comparison</title><style>body{font:15px system-ui;margin:32px;color:#101c2c}table{border-collapse:collapse}td,th{border:1px solid #9aa6b2;padding:8px}pre{white-space:pre-wrap}</style><h1>RAINYMINE — Хараат бус хяналтад өгөх тоон харьцуулалт</h1><p>Тоон харьцуулалт нь ордын баталгаажуулалт биш. Эх сурвалж, нэгж, CRS, геологийн тайлбар, мэргэжилтний хяналт шаардлагатай.</p><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False))+'</pre><table><tr><th>Row</th><th>Status</th><th>Reference</th><th>Model</th><th>Error</th><th>Checks</th><th>Pass</th></tr>'+rows+'</table></html>')
