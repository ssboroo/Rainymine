"""Versioned, atomic Morton-sorted Parquet exchange plus bounded SoA scanning.

This is a separate block-model store, not a migration of .rmine projects. Morton
is a spatial sort key; row_id retains original picking identity and octree IDs.
Scientific positions/grades remain float64 on disk; GPU conversion is separate.
"""
import json
import os
from pathlib import Path
import tempfile
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds
from .engineering import morton_codes
from .spatial import model_basis

RESERVED={'morton_id','row_id','xc','yc','zc'}


def write_block_parquet(path,model,crs='',grade_unit=''):
    blocks=model.get('blocks',[])
    if not blocks:raise ValueError('Хадгалах блок алга.')
    keys=set().union(*(b.keys() for b in blocks))
    if keys&RESERVED:raise ValueError('Parquet reserved column давхардсан.')
    xyz=np.asarray([[b[k] for k in ('x','y','z')] for b in blocks],dtype=np.float64)
    sizes=np.asarray([[b[k] for k in ('dx','dy','dz')] for b in blocks],dtype=np.float64)
    if not np.isfinite(xyz).all() or not np.isfinite(sizes).all() or np.any(sizes<=0):raise ValueError('Блокийн XYZ / хэмжээ буруу.')
    for block in blocks:
        for key in ('grade','variance','density','kriging_efficiency','slope_of_regression','block_variance'):
            value=block.get(key)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value)):
                raise ValueError('Блокийн тооцооны утга буруу: '+key)
    origin=np.asarray(model.get('grid_origin',xyz.min(axis=0)),dtype=np.float64)
    if origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('Origin буруу.')
    grid=(xyz-origin)@model_basis(model);quantum=sizes.min(axis=0);grid_min=grid.min(axis=0)
    index=np.floor((grid-grid_min)/quantum+1e-8)
    if np.any(index>=2**21):raise ValueError('Morton 21-bit тэнхлэгийн хязгаар хэтэрсэн.')
    codes=morton_codes(index.astype(np.int64));order=np.argsort(codes,kind='stable');local=xyz-origin
    metadata={'version':1,'origin':origin.tolist(),'model':{k:v for k,v in model.items() if k!='blocks'},
              'crs':crs,'grade_unit':grade_unit,'sort':'morton_id; stable original row order on ties',
              'quantum':quantum.tolist(),'grid_min':grid_min.tolist(),'coordinates':'local float64; world=local+origin',
              'classification':'UNCLASSIFIED; codes never imply equivalence between reporting standards'}
    encoded=json.dumps(metadata,ensure_ascii=False,allow_nan=False).encode()
    if len(encoded)>1048576:raise ValueError('Parquet metadata 1 MiB-аас их байна.')
    columns={'morton_id':pa.array(codes[order],type=pa.uint64()),'row_id':pa.array(order,type=pa.int64())}
    for i,key in enumerate(('xc','yc','zc')):columns[key]=pa.array(np.ascontiguousarray(local[order,i]),type=pa.float64())
    for key in sorted(keys-{'x','y','z'}):columns[key]=pa.array([blocks[int(i)].get(key) for i in order])
    table=pa.table(columns).replace_schema_metadata({b'rainymine':encoded})
    path=Path(path);fd,temp=tempfile.mkstemp(prefix='.rainymine-parquet-',dir=path.parent);os.close(fd)
    try:
        floats=[field.name for field in table.schema if pa.types.is_floating(field.type)]
        pq.write_table(table,temp,row_group_size=262144,compression='zstd',compression_level=3,
                       use_dictionary=[k for k in ('domain','lithology','status','subblock_level') if k in columns],
                       use_byte_stream_split=floats,write_statistics=True)
        # Windows _commit/FlushFileBuffers requires a writable descriptor.
        with open(temp,'r+b') as stream:os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'blocks':len(blocks),'bytes':path.stat().st_size,'row_groups':pq.ParquetFile(path).metadata.num_row_groups}


def block_metadata(path):
    raw=(pq.read_schema(path).metadata or {}).get(b'rainymine')
    if raw is None or len(raw)>1048576:raise ValueError('RAINYMINE Parquet metadata алга / хэт их.')
    metadata=json.loads(raw)
    if metadata.get('version')!=1:raise ValueError('Parquet schema version дэмжихгүй.')
    origin=np.asarray(metadata.get('origin'),dtype=float)
    if origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('Parquet origin буруу.')
    return metadata


def scan_block_batches(path,bounds=None,columns=None,batch_size=65536):
    """Arrow predicate pushdown in local XYZ, inclusive bounds; bounded SoA batches.

    Caller retains metadata origin. Compressed Parquet decodes into RAM batches;
    memory_map is not a zero-copy promise for compressed pages.
    """
    if type(batch_size) is not int or not 1<=batch_size<=262144:raise ValueError('Batch хэмжээ буруу.')
    metadata=block_metadata(path);origin=metadata['origin'];expression=None
    if bounds is not None:
        b=np.asarray(bounds,dtype=float)
        if b.shape!=(6,) or not np.isfinite(b).all() or np.any(b[:3]>b[3:]):raise ValueError('Filter bounds буруу.')
        for i,key in enumerate(('xc','yc','zc')):
            condition=(ds.field(key)>=b[i]-origin[i])&(ds.field(key)<=b[i+3]-origin[i])
            expression=condition if expression is None else expression&condition
    scanner=ds.dataset(str(path),format='parquet').scanner(columns=columns,filter=expression,batch_size=batch_size)
    yield from scanner.to_batches()


def read_block_model(path,maximum=50000):
    """Bounded desktop materialization; use scan_block_batches for larger stores."""
    if type(maximum) is not int or maximum<=0:raise ValueError('Maximum буруу.')
    metadata=block_metadata(path)
    if pq.ParquetFile(path).metadata.num_rows>maximum:raise ValueError('Desktop блокийн хязгаар хэтэрсэн; streaming scanner ашиглана уу.')
    table=pq.read_table(path,memory_map=True);rows=table.to_pylist();rows.sort(key=lambda b:b['row_id'])
    for row in rows:
        for i,(source,target) in enumerate(zip(('xc','yc','zc'),('x','y','z'))):row[target]=row.pop(source)+metadata['origin'][i]
        row.pop('morton_id');row.pop('row_id')
    return {**metadata['model'],'blocks':rows},metadata
