"""Synthetic bounded-reader benchmark; no claim about physical GPU frame rates."""
import argparse
import gc
import json
import platform
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np


def run(count=1_000_000,maximum=100_000):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import laspy
    from pyproj import CRS
    from rainymine.engineering import morton_codes
    from rainymine.formats import las_preview
    from rainymine.large_view import parquet_preview,preview_polydata
    if not 1<=count<=10_000_000:raise ValueError('count 1…10000000 байна.')
    origin=[500000.,5300000.,1400.];result={'synthetic':True,'platform':platform.platform(),'python':platform.python_version(),'source_points':count,'preview_limit':maximum,'physical_gpu_fps_measured':False,'cache':'warm immediately-after-write; no cold-cache run'}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);parquet=root/'model.parquet';las=root/'points.las'
        bounds=origin+[501000.,5301000.,1400.+10*np.ceil(count/10000)]
        metadata={'version':1,'origin':origin,'model':{'bounds':bounds,'grid_origin':origin,'grid_angles':[90,0,0],'size':[10]*3},'crs':'EPSG:32648','grade_unit':'%','sort':'unsorted synthetic benchmark fixture'}
        started=time.perf_counter();writer=None
        try:
            for start in range(0,count,262144):
                ids=np.arange(start,min(count,start+262144),dtype=np.int64)
                table=pa.table({'row_id':ids,'morton_id':morton_codes(np.column_stack((ids%100,(ids//100)%100,ids//10000))),'xc':(ids%100)*10.+5,'yc':((ids//100)%100)*10.+5,'zc':(ids//10000)*10.+5,
                                'dx':np.full(len(ids),10.),'dy':np.full(len(ids),10.),'dz':np.full(len(ids),10.),'grade':(ids%17)/5.})
                table=table.replace_schema_metadata({b'rainymine':json.dumps(metadata).encode()})
                if writer is None:writer=pq.ParquetWriter(parquet,table.schema,compression='zstd',compression_level=3)
                writer.write_table(table,row_group_size=262144)
        finally:
            if writer:writer.close()
        result['fixture_parquet_write_seconds']=time.perf_counter()-started
        started=time.perf_counter();payload=parquet_preview(parquet,maximum=maximum,cutoff=1.)
        result['parquet_scan_seconds']=time.perf_counter()-started;result['parquet_displayed']=len(payload['xyz']);result['parquet_matching']=payload['matched_before_sampling'];result['parquet_bytes']=parquet.stat().st_size
        started=time.perf_counter();poly,local_origin=preview_polydata(payload);result['vtk_buffer_build_seconds']=time.perf_counter()-started;result['vtk_point_type']=poly.GetPoints().GetData().GetDataTypeAsString();del payload,poly;gc.collect()
        header=laspy.LasHeader(point_format=3,version='1.2');header.offsets=origin;header.scales=[.001]*3;header.add_crs(CRS.from_epsg(32648))
        with laspy.open(las,mode='w',header=header) as writer:
            for start in range(0,count,250000):
                ids=np.arange(start,min(count,start+250000),dtype=np.int64);points=laspy.ScaleAwarePointRecord.zeros(len(ids),header=header)
                points.x=origin[0]+(ids%1000)*.1;points.y=origin[1]+((ids//1000)%1000)*.1;points.z=origin[2]+ids%100*.01;writer.write_points(points)
        started=time.perf_counter();cloud=las_preview(las,maximum=maximum);result['las_scan_seconds']=time.perf_counter()-started;result['las_displayed']=len(cloud['xyz']);result['las_bytes']=las.stat().st_size
        try:
            import resource
            result['process_peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024 if sys.platform!='darwin' else 1024**2)
        except ImportError:result['process_peak_rss_mib']=None
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--points',type=int,default=1_000_000);parser.add_argument('--maximum',type=int,default=100_000);parser.add_argument('--output',required=True);args=parser.parse_args()
    report=run(args.points,args.maximum);path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
