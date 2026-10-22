"""Synthetic native kernels and end-to-end kriging; not deposit certification."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from rainymine.native_engine import grid_pseudoflow,rust_predictions,engine
from rainymine.estimation import Estimator
from benchmark_disk_workflow import peak_memory_mib


def run(side=100,targets=1000):
 report=dict(synthetic=True,platform=platform.platform(),processor=platform.processor(),logical_cpus=os.cpu_count(),python=platform.python_version(),engine=engine().ENGINE_VERSION,mineflow_commit=engine().MINEFLOW_COMMIT,blocks=side**3,timings_seconds={},independent_deposit_validation=False)
 def measure(name,operation):
  t=time.perf_counter();result=operation();report['timings_seconds'][name]=round(time.perf_counter()-t,6);return result
 zz,yy,xx=np.indices((side,side,side));values=np.full(side**3,-1.,dtype=float)
 ore=((xx-side/2)**2+(yy-side/2)**2<(side/5)**2)&(zz<side*.6)
 values[ore.ravel()]=30.
 mask,pit=measure('pseudoflow_implicit_grid',lambda:grid_pseudoflow(values,[side]*3,[10]*3))
 report['pit']=pit
 if pit['net_value']<=0:raise AssertionError('Synthetic ore must yield positive value')
 rng=np.random.default_rng(121)
 samples=[dict(xyz=point,grade=float(rng.uniform(0,5)),hole_id=str(i//3)) for i,point in enumerate(rng.uniform(-100,100,(200,3)))]
 estimator=Estimator(samples,dict(method='kriging',neighbors=16,minimum=4,radii=[150]*3,nugget=.1,partial_sill=1.5,range_m=100))
 points=rng.uniform(-50,50,(targets,3))
 reference=measure('python_kriging_full_pipeline',lambda:[estimator.predict(p) for p in points])
 actual=measure('rust_kriging_full_pipeline',lambda:rust_predictions(estimator,points))
 errors=[]
 for a,b in zip(reference,actual):
  if a['status']!=b['status']:raise AssertionError('Kriging status mismatch')
  if a['grade'] is not None:
   for key in ('grade','variance','kriging_efficiency','slope_of_regression'):
    if a[key] is not None:errors.append(abs(a[key]-b[key]))
 report.update(kriging_targets=targets,maximum_reference_absolute_error=max(errors,default=0),peak_memory_mib=round(peak_memory_mib(),3),kriging_support='ordinary / spherical / point; full neighborhood assembly included')
 if report['maximum_reference_absolute_error']>1e-8:raise AssertionError('Numerical parity tolerance exceeded')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--side',type=int,default=100);parser.add_argument('--targets',type=int,default=1000);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 if not 2<=args.side<=150 or not 1<=args.targets<=10000:parser.error('Benchmark size out of bounds')
 result=run(args.side,args.targets);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
