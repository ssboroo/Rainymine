"""Measured streaming import/aggregate/edit/preview/export synthetic fixture.

No FPS, kriging, independent orebody or Windows-device performance is inferred.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.disk_import import import_disk_csv
from rainymine.disk_model import DiskModel
from rainymine.large_view import preview_polydata
from benchmark_disk_workflow import peak_memory_mib


def run(rows):
    report={'kind':'synthetic_streaming_leaf_import','rows':rows,'platform':platform.platform(),
            'python':sys.version,'processor':platform.processor(),'steps_seconds':{},
            'real_deposit_validation':False,'physical_windows_validation':False,'gpu_fps_measured':False}
    def measure(name,operation):
        start=time.perf_counter();result=operation();report['steps_seconds'][name]=round(time.perf_counter()-start,6);return result
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder)/'blocks.csv';database=Path(folder)/'blocks.rmdb';output=Path(folder)/'export.csv'
        def generate():
            with source.open('w',encoding='utf-8',newline='') as stream:
                stream.write('x,y,z,dx,dy,dz,grade,density\n')
                for i in range(rows):
                    grade='' if i%100003==0 else '2'
                    stream.write(f'{500000+(i%200+.5)*10},{5300000+((i//200)%200+.5)*10},{1000+(i//40000+.5)*10},10,10,10,{grade},2.7\n')
        measure('generate_csv',generate)
        mapping={k:k for k in ('x','y','z','dx','dy','dz','grade','density')}
        report['import']=measure('stream_import',lambda:import_disk_csv(source,database,mapping,'EPSG:32648','%'))
        with DiskModel(database) as store:
            totals=measure('aggregate',store.totals);unknown=math.ceil(rows/100003)
            assert totals['blocks']==rows and totals['unestimated_blocks']==unknown
            assert math.isclose(totals['tonnes'],rows*1000*2.7,rel_tol=1e-10)
            assert math.isclose(totals['contained_metal_tonnes'],(rows-unknown)*1000*2.7*.02,rel_tol=1e-10)
            measure('edit_one_block',lambda:store.edit(0,1.5,2.7,'test'))
            assert measure('undo',store.undo);assert measure('redo',lambda:store.undo(True));assert store.undo()
            assert store.totals()==totals
            payload=measure('preview_sample',lambda:store.preview(50000))
            poly,_=measure('vtk_buffers',lambda:preview_polydata(payload));assert poly.GetNumberOfPoints()<=50000
            report['preview_points']=poly.GetNumberOfPoints()
            measure('stream_export',lambda:store.export_csv(output))
            report['totals']=totals
        with DiskModel(database) as store:assert store.totals()==totals
        with source.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==report['import']['source_sha256']
        with output.open('rb') as stream:assert sum(1 for _ in stream)==rows+1
        report['database_bytes']=database.stat().st_size;report['source_bytes']=source.stat().st_size;report['export_bytes']=output.stat().st_size
    report['process_peak_rss_mib']=peak_memory_mib();report['analytic_checks_passed']=True
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rows',type=int,default=1000000);parser.add_argument('--output',required=True);args=parser.parse_args()
    if not 1<=args.rows<=20000000:parser.error('rows: 1..20000000')
    result=run(args.rows);path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
