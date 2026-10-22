"""Stream a regular SQLite model into implicit-graph native pseudoflow.

The model remains on disk; solver node/excess state resides in RAM.
"""
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
import numpy as np
from .disk_model import DiskModel
from .native_engine import grid_pseudoflow


def optimize_disk_pit(path,output,price,recovery,mining_cost,processing_cost,density_fallback,
                      slope=45,value_scale=1_000_000.,memory_budget_mib=2048,cancel=None,progress=None):
    numbers=[price,recovery,mining_cost,processing_cost,density_fallback,memory_budget_mib]
    if not all(math.isfinite(v) for v in numbers) or price<0 or not 0<=recovery<=1 or min(mining_cost,processing_cost)<0 or density_fallback<=0 or memory_budget_mib<=0:raise ValueError('Invalid disk pit economics/budget')
    output=Path(output)
    if output.suffix.lower()!='.csv':raise ValueError('Pit output must use .csv extension')
    if output.resolve()==Path(path).resolve():raise ValueError('Output must not overwrite the block database')
    with DiskModel(path) as store:
        if store.meta.get('grid_kind')=='unstructured_axis_aligned':raise ValueError('Disk pseudoflow requires a verified complete regular grid; imported leaf geometry is not a regular grid')
        store.db.execute('BEGIN')
        store.meta=json.loads(store.db.execute('SELECT value FROM metadata WHERE key="model"').fetchone()[0])
        counts=store.meta['counts'];size=np.asarray(store.meta['size'],dtype=float);origin=np.asarray(store.meta['origin'],dtype=float)
        if len(counts)!=3 or any(type(v)!=int or v<=0 for v in counts) or math.prod(counts)>10_000_000 or size.shape!=(3,) or origin.shape!=(3,) or not np.isfinite(size).all() or not np.isfinite(origin).all() or min(size)<=0:raise ValueError('Invalid regular grid metadata')
        from pyproj import CRS
        crs=CRS.from_user_input(store.meta['crs'])
        if not crs.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in crs.axis_info[:2]):raise ValueError('Projected metre CRS required')
        n=math.prod(counts)
        # Conservative admission estimate; native allocator peak still needs measurement.
        if n*1024>memory_budget_mib*1024**2:raise ValueError('Estimated solver memory exceeds chosen budget (1024 bytes/block admission estimate)')
        values=np.empty(n);tonnes=np.empty(n);processed=np.zeros(n,dtype=bool);offset=0;digest=hashlib.sha256()
        digest.update(json.dumps(store.meta,sort_keys=True,allow_nan=False).encode('utf-8'))
        cursor=store.db.execute('SELECT id,x,y,z,dx,dy,dz,grade,density FROM blocks ORDER BY id')
        while True:
            if cancel and cancel():raise RuntimeError('Disk pit cancelled')
            rows=cursor.fetchmany(32768)
            if not rows:break
            data=np.asarray(rows,dtype=float);ids=np.arange(offset,offset+len(rows),dtype=np.int64)
            if offset+len(rows)>n or not np.array_equal(data[:,0],ids) or not np.isfinite(data[:,:8]).all() or np.any(data[:,7]<0):raise ValueError('Complete ordered grid with known nonnegative grades required')
            ijk=np.column_stack((ids%counts[0],(ids//counts[0])%counts[1],ids//(counts[0]*counts[1])))
            if not np.allclose(data[:,1:4],origin+(ijk+.5)*size,rtol=0,atol=1e-6) or not np.allclose(data[:,4:7],size,rtol=0,atol=1e-7):raise ValueError('Stored geometry does not match regular-grid metadata')
            density=np.where(np.isnan(data[:,8]),density_fallback,data[:,8])
            if not np.isfinite(density).all() or np.any(density<=0):raise ValueError('Invalid density')
            mass=math.prod(size)*density;margin=data[:,7]*price*recovery-processing_cost
            stop=offset+len(rows);tonnes[offset:stop]=mass;processed[offset:stop]=margin>0
            values[offset:stop]=mass*(np.maximum(0.,margin)-mining_cost)
            digest.update(np.ascontiguousarray(data,dtype='<f8').tobytes());offset=stop
            if progress:progress(offset,n*2)
        if offset!=n:raise ValueError('Incomplete regular grid')
        mask,report=grid_pseudoflow(values,counts,size,slope,value_scale,cancel)
        report.update(input_sha256=digest.hexdigest(),counts=counts,size=size.tolist(),crs=store.meta['crs'],grade_unit=store.meta['grade_unit'],
            density_fallback=density_fallback,price_per_grade_tonne=price,recovery=recovery,mining_cost_per_tonne=mining_cost,
            processing_cost_per_tonne=processing_cost,mined_tonnes=float(tonnes[mask].sum()),processed_tonnes=float(tonnes[mask&processed].sum()),
            memory_admission_estimate_mib=n/1024,source=str(Path(path).resolve()),output=str(output.resolve()))
        fd,temp=tempfile.mkstemp(dir=output.parent,prefix='.pit-',suffix='.csv');os.close(fd)
        try:
            with open(temp,'w',newline='',encoding='utf-8') as stream:
                writer=csv.writer(stream);writer.writerow(['block_id','selected','net_value','tonnes','processed'])
                for i in range(n):
                    if i%32768==0:
                        if cancel and cancel():raise RuntimeError('Disk pit export cancelled')
                        if progress:progress(n+i,n*2)
                    writer.writerow([i,int(mask[i]),values[i],tonnes[i],int(mask[i] and processed[i])])
                stream.flush();os.fsync(stream.fileno())
            if cancel and cancel():raise RuntimeError('Disk pit cancelled')
            with open(temp,'rb') as stream:report['output_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
            os.replace(temp,output)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        if progress:progress(n*2,n*2)
        return report
