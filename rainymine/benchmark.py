"""Compare a saved model with externally supplied reference CSV; no self-certification."""
import csv
import hashlib
import io
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from .core import finite


def compare_reference(model,path,coordinate_tolerance=.01,grade_absolute=.001,grade_relative=.01):
    finite(coordinate_tolerance,grade_absolute,grade_relative)
    if coordinate_tolerance<=0 or min(grade_absolute,grade_relative)<0:raise ValueError('Benchmark tolerance буруу.')
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
            values=[float(row[k]) for k in ('x','y','z','grade')];finite(*values);reference.append(values)
            if len(reference)>50000:raise ValueError('Reference 50000 мөрөөс их.')
    if not reference or not model['blocks']:raise ValueError('Reference/model өгөгдөлгүй.')
    ref=np.asarray(reference);xyz=np.array([[b[a] for a in ('x','y','z')] for b in model['blocks']])
    if len(np.unique(ref[:,:3],axis=0))!=len(ref):raise ValueError('Reference coordinate давхардсан.')
    tree=cKDTree(xyz);used=set();rows=[]
    for i,r in enumerate(ref):
        matches=tree.query_ball_point(r[:3],coordinate_tolerance)
        if len(matches)!=1 or matches[0] in used:
            rows.append({'reference_row':i+2,'status':'ambiguous_or_missing_coordinate','passed':False});continue
        index=matches[0];used.add(index);observed=model['blocks'][index].get('grade')
        if observed is None:
            rows.append({'reference_row':i+2,'status':'unestimated','passed':False});continue
        error=observed-r[3];tolerance=grade_absolute+grade_relative*abs(r[3])
        rows.append({'reference_row':i+2,'status':'compared','model_index':index,'expected':float(r[3]),'actual':observed,'error':float(error),'passed':bool(abs(error)<=tolerance)})
    complete=len(used)==len(model['blocks'])==len(ref)
    return {'source_name':path.name,'reference_sha256':hashlib.sha256(raw).hexdigest(),'model_run_sha256':model.get('run_sha256'),
            'coordinate_tolerance':coordinate_tolerance,'grade_absolute':grade_absolute,'grade_relative':grade_relative,
            'reference_count':len(ref),'model_count':len(model['blocks']),'complete_coverage':complete,
            'numerical_pass':complete and all(r['passed'] for r in rows),'rows':rows,
            'independent_review_verified':False,'review_status':'PENDING — external provenance, real-deposit authorization and qualified geologist sign-off required'}


def compare_block_geometry(model,path,reference_angles,coordinate_tolerance=.001,dimension_tolerance=.001,grade_absolute=.001,grade_relative=.01,cancel=None):
    """Compare externally supplied world centres/local dimensions/NULL grades.

    Reference angles use RAINYMINE ENU convention and must be established outside
    this routine. A numerical pass never establishes independent provenance.
    """
    from .spatial import search_basis,model_basis
    finite(coordinate_tolerance,dimension_tolerance,grade_absolute,grade_relative)
    if min(coordinate_tolerance,dimension_tolerance)<=0 or min(grade_absolute,grade_relative)<0:
        raise ValueError('Reference tolerance буруу.')
    angle_basis=search_basis(*reference_angles)
    orientation=bool(np.allclose(model_basis(model),angle_basis,rtol=0,atol=1e-9))
    path=Path(path)
    if path.stat().st_size>32_000_000:raise ValueError('Reference CSV 32 MB-аас их.')
    raw=path.read_bytes()
    if len(raw)>32_000_000:raise ValueError('Reference CSV 32 MB-аас их.')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
    keys=('x','y','z','dx','dy','dz','grade')
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or not set(keys)<=set(reader.fieldnames):
        raise ValueError('Reference нь x,y,z,dx,dy,dz,grade header шаардлагатай.')
    reference=[]
    for line,row in enumerate(reader,2):
        if cancel and cancel():raise RuntimeError('Reference comparison cancelled.')
        if None in row or any(v is None for v in row.values()):raise ValueError(f'Reference мөр {line}: баганын тоо зөрсөн.')
        values=[float(row[k]) for k in keys[:6]];finite(*values)
        if min(values[3:])<=0:raise ValueError('Reference хэмжээ эерэг байна.')
        token=row['grade'].strip()
        grade=None if token.upper() in ('','NULL','NONE','NAN') else float(token)
        if grade is not None:finite(grade)
        reference.append((values,grade))
        if len(reference)>50000:raise ValueError('Reference 50000 мөрөөс их.')
    blocks=model.get('blocks',[])
    if not reference or not blocks or len(blocks)>50000:raise ValueError('Reference/model блокийн тоо буруу.')
    xyz=np.array([[b[k] for k in 'xyz'] for b in blocks]);tree=cKDTree(xyz)
    if len(np.unique(np.array([r[0][:3] for r in reference]),axis=0))!=len(reference):
        raise ValueError('Reference төв давхардсан.')
    rows=[];used=set()
    for line,(values,grade) in enumerate(reference,2):
        if cancel and cancel():raise RuntimeError('Reference comparison cancelled.')
        matches=tree.query_ball_point(values[:3],coordinate_tolerance)
        if len(matches)!=1 or matches[0] in used:
            rows.append({'reference_row':line,'passed':False,'status':'ambiguous_or_missing_coordinate'});continue
        index=matches[0];used.add(index);block=blocks[index]
        size_error=max(abs(block[k]-values[i+3]) for i,k in enumerate(('dx','dy','dz')))
        actual=block.get('grade')
        grade_pass=actual is grade if actual is None or grade is None else abs(actual-grade)<=grade_absolute+grade_relative*abs(grade)
        rows.append({'reference_row':line,'model_index':index,'dimension_max_error_m':size_error,
                     'grade_pass':bool(grade_pass),'passed':bool(size_error<=dimension_tolerance and grade_pass and orientation),
                     'status':'compared'})
    complete=len(used)==len(blocks)==len(reference)
    import json
    model_hash=hashlib.sha256(json.dumps(model,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
    return {'reference_sha256':hashlib.sha256(raw).hexdigest(),'model_sha256':model_hash,'source_name':path.name,
            'reference_count':len(reference),'model_count':len(blocks),'complete_coverage':complete,
            'orientation_pass':orientation,'reference_angles':list(reference_angles),
            'coordinate_tolerance_m':coordinate_tolerance,'dimension_tolerance_m':dimension_tolerance,
            'grade_absolute':grade_absolute,'grade_relative':grade_relative,
            'reference_volume_m3':sum(v[3]*v[4]*v[5] for v,g in reference),
            'model_volume_m3':sum(b['dx']*b['dy']*b['dz'] for b in blocks),
            'numerical_pass':complete and orientation and all(r['passed'] for r in rows),'rows':rows,
            'independent_review_verified':False,'review_status':'PENDING external engineer provenance and sign-off'}
