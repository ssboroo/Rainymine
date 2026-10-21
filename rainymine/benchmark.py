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
