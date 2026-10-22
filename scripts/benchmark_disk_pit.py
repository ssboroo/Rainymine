"""Analytic constant-grade disk pit workflow; solver difficulty is intentionally low."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rainymine.disk_model import DiskModel
from rainymine.disk_pit import optimize_disk_pit
from benchmark_disk_workflow import peak_memory_mib


def run(side=100):
 n=side**3;timings={}
 def measure(name,operation):
  started=time.perf_counter();value=operation();timings[name]=round(time.perf_counter()-started,6);return value
 def digest(path):
  with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'model.rmdb';output=Path(directory)/'pit.csv'
  measure('create_grid',lambda:DiskModel.create(path,[500000,5300000,1000],[side]*3,[10]*3,'EPSG:32648','%',2.7))
  with DiskModel(path) as store:
   store.db.execute('UPDATE blocks SET grade=2.0');store.db.commit()
  before=digest(path)
  report=measure('read_validate_pseudoflow_export',lambda:optimize_disk_pit(path,output,100,.9,3,12,2.7))
  expected=n*2700*165
  if report['selected_blocks']!=n or abs(report['net_value']-expected)>expected*1e-12:raise AssertionError('Analytic disk pit mismatch')
  if before!=digest(path):raise AssertionError('Optimizer modified source')
  with open(output,encoding='utf-8') as stream:rows=sum(1 for _ in stream)-1
  if rows!=n or digest(output)!=report['output_sha256']:raise AssertionError('Incomplete/corrupt CSV')
  return dict(synthetic=True,fixture='constant grade 2; all profitable; analytically all selected; easy graph',platform=platform.platform(),python=platform.python_version(),blocks=n,timings_seconds=timings,peak_memory_mib=round(peak_memory_mib(),3),expected_net_value=expected,source_unchanged=True,export_rows=rows,report=report,independent_deposit_validation=False)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--side',type=int,default=100);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if not 2<=args.side<=100:parser.error('side must be 2–100')
 report=run(args.side);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
