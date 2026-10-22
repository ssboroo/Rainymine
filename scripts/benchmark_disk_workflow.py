"""Measured synthetic disk workflow; never a real-deposit or physical-GPU claim."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.disk_model import DiskModel


def peak_memory_mib():
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=wintypes.HANDLE
        api=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo;api.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD];api.restype=wintypes.BOOL
        if not api(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize/1024**2
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)


def run(side=100):
    from rainymine.large_view import preview_polydata
    report={'synthetic':True,'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'python':platform.python_version(),'sqlite':__import__('sqlite3').sqlite_version,'blocks':side**3,'physical_gpu_fps_measured':False,'cache':'single run, warm; no cold-cache comparison','timings_seconds':{}}
    def measure(name,operation):
        started=time.perf_counter();value=operation();report['timings_seconds'][name]=round(time.perf_counter()-started,6);return value
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);path=root/'million.rmdb';output=root/'million.csv'
        measure('create_grid',lambda:DiskModel.create(path,[500000,5300000,1000],[side]*3,[10.]*3,'EPSG:32648','%',2.7))
        with DiskModel(path) as store:
            samples=[[500000+x,5300000+y,1000+z,2.] for x in (0,side*10) for y in (0,side*10) for z in (0,side*10)]
            result=measure('estimate_idw',lambda:store.estimate_idw(samples,radius=side*100.,neighbors=8,minimum=3))
            if result['estimated']!=side**3:raise AssertionError('Incomplete estimation')
            measure('edit_one_block',lambda:store.edit(0,3.,2.7,'edited'))
            if not measure('undo_edit',store.undo):raise AssertionError('Undo failed')
            if not measure('redo_edit',lambda:store.undo(True)):raise AssertionError('Redo failed')
            store.undo()
            if not measure('undo_estimation',store.undo):raise AssertionError('Bulk undo failed')
            if store.totals()['unestimated_blocks']!=side**3:raise AssertionError('Bulk undo lost NULL values')
            if not measure('redo_estimation',lambda:store.undo(True)):raise AssertionError('Bulk redo failed')
            totals=measure('aggregate_all_blocks',store.totals)
            expected_tonnes=side**3*1000*2.7;expected_metal=expected_tonnes*.02
            if abs(totals['tonnes']-expected_tonnes)>expected_tonnes*1e-12 or abs(totals['contained_metal_tonnes']-expected_metal)>max(1e-6,expected_metal*1e-10):raise AssertionError('Analytic constant-grade mass balance mismatch')
            payload=measure('sample_preview',lambda:store.preview(100000))
            poly,origin=measure('vtk_preview_buffers',lambda:preview_polydata(payload))
            report['preview_blocks']=poly.GetNumberOfPoints();report['preview_origin']=origin.tolist()
            measure('export_all_blocks_csv',lambda:store.export_csv(output))
            report['totals']=totals
        with DiskModel(path) as reopened:
            if reopened.totals()!=totals:raise AssertionError('Reopen mismatch')
        with output.open('rb') as stream:report['export_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
        with output.open('rb') as stream:lines=sum(1 for _ in stream)
        if lines!=side**3+1:raise AssertionError('CSV row count mismatch')
        report['csv_rows']=lines-1;report['database_bytes']=path.stat().st_size;report['csv_bytes']=output.stat().st_size
        report['process_peak_rss_mib']=round(peak_memory_mib(),3)
        report['analytic_fixture_pass']=True;report['independent_deposit_validation']=False
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--side',type=int,default=100);parser.add_argument('--output',required=True);args=parser.parse_args()
    if not 1<=args.side<=200:parser.error('side must be 1..200')
    report=run(args.side);path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
