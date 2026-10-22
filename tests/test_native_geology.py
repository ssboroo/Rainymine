import itertools
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
from rainymine.fault_network import FaultNetwork,fault_mesh
from rainymine.estimation import Estimator

try:
 import rainymine_core
 NATIVE=True
except ImportError:
 NATIVE=False
 if os.environ.get('RAINYMINE_REQUIRE_NATIVE')=='1':raise


def curved():
 controls=[]
 for x in (-10.,0.,10.):
  for y in (-10.,0.,10.):
   for d in (-5.,0.,5.):controls.append(dict(x=x,y=y,z=.02*x*x+d,value=d))
 return dict(name='curved',kind='rbf',constraints=controls,ranges=[10,10,10],neighbors=27)


class FaultNetworkTests(unittest.TestCase):
 def test_signed_controls_and_curvature(self):
  f=curved();network=FaultNetwork([f]);points=[[r[a] for a in 'xyz'] for r in f['constraints']]
  actual=network.signed(0,points);np.testing.assert_allclose(actual,[r['value'] for r in f['constraints']],atol=1e-9)
  self.assertEqual(network.classify([[0,0,-4],[0,0,4],[10,0,-3],[10,0,7]]).tolist(),[0,1,0,1])
  mesh=fault_mesh(network,0,[-10,-10,-8,10,10,8],11)
  self.assertGreater(len(mesh['faces']),0);self.assertFalse(mesh['geological_review'])

 def test_dag_scope_inactive_regions_and_cycle(self):
  child=curved();child['active_if']={'parent':1}
  parent=dict(name='parent',point=[0,0,0],normal=[1,0,0])
  network=FaultNetwork([child,parent]);self.assertEqual(network.order,[1,0])
  a,b,c=network.classify([[-5,0,-4],[5,0,-4],[5,0,7]])
  self.assertNotEqual(a,b);self.assertNotEqual(b,c)
  parent['active_if']={'curved':1}
  with self.assertRaises(ValueError):FaultNetwork([child,parent])
  child['active_if']={'missing':1}
  with self.assertRaises(ValueError):FaultNetwork([child])

 def test_explicit_restoration_no_inferred_throw(self):
  f=dict(name='P',point=[0,0,0],normal=[1,0,0],slip=[0,0,3])
  points=np.array([[-1.,0,5],[1.,0,5]])
  np.testing.assert_allclose(FaultNetwork([f]).restore(points),[[-1,0,5],[1,0,2]])
  self.assertEqual(points[1,2],5)
  with self.assertRaises(RuntimeError):FaultNetwork([curved()]).classify(points,cancel=lambda:True)

 def test_curved_barrier_prevents_cross_fault_estimation(self):
  samples=[dict(xyz=[0,0,-4],grade=1.,hole_id='A'),dict(xyz=[0,0,4],grade=99.,hole_id='B')]
  estimator=Estimator(samples,dict(method='nearest',minimum=1,neighbors=2,radii=[100]*3,faults=[curved()]))
  self.assertEqual(estimator.predict([0,0,-.1])['grade'],1.)
  self.assertEqual(estimator.predict([0,0,.1])['grade'],99.)


@unittest.skipUnless(NATIVE,'Native extension must be built; mandatory on Windows CI')
class NativeKernelTests(unittest.TestCase):
 def test_pseudoflow_matches_exhaustive_dag(self):
  from rainymine.native_engine import pseudoflow
  rng=np.random.default_rng(712)
  for _ in range(25):
   values=rng.integers(-20,20,8).astype(float)
   edges=[(i,j) for i in range(8) for j in range(i+1,8) if rng.random()<.25]
   mask,report=pseudoflow(values,edges)
   reference=max(sum(values[i]*bits[i] for i in range(8)) for bits in itertools.product((0,1),repeat=8) if all(bits[c]<=bits[p] for c,p in edges))
   self.assertAlmostEqual(report['net_value'],reference);self.assertTrue(report['integer_optimum'])
   self.assertTrue(all(not mask[c] or mask[p] for c,p in edges))

 def test_implicit_stencil_matches_explicit(self):
  from rainymine.native_engine import grid_pseudoflow,pseudoflow
  nx,ny,nz=4,3,3;rng=np.random.default_rng(83);values=rng.integers(-100,100,nx*ny*nz)
  edges=[]
  for k in range(nz-1):
   for j in range(ny):
    for i in range(nx):
     for dx in (-1,0,1):
      for dy in (-1,0,1):
       if 0<=i+dx<nx and 0<=j+dy<ny:edges.append((i+nx*(j+ny*k),i+dx+nx*(j+dy+ny*(k+1))))
  a,ra=grid_pseudoflow(values,[nx,ny,nz],[10,10,10]);b,rb=pseudoflow(values,edges)
  self.assertEqual(ra['net_value'],rb['net_value'])

 def test_rounding_overflow_cancel_and_invalid_native_input(self):
  from rainymine.native_engine import pseudoflow
  _,r=pseudoflow([.0000014,-.0000006],[(0,1)],value_scale=1e6)
  self.assertLessEqual(abs(r['net_value']-.0000008),r['objective_loss_bound'])
  with self.assertRaises(ValueError):pseudoflow([1e20])
  with self.assertRaises(RuntimeError):pseudoflow([1],cancel=lambda:True)
  with self.assertRaises(ValueError):rainymine_core.closure(np.array([2**62],dtype=np.int64),np.empty((0,2),dtype=np.int64))
  with self.assertRaises(ValueError):rainymine_core.closure(np.array([1],dtype=np.int64),np.array([[0,2]],dtype=np.int64))

 def test_parallel_kriging_reference_and_diagnostics(self):
  from rainymine.native_engine import rust_predictions
  rng=np.random.default_rng(491)
  samples=[dict(xyz=p,grade=float(rng.uniform(0,5)),hole_id=str(i//2)) for i,p in enumerate(rng.uniform(-20,20,(30,3)))]
  params=dict(method='kriging',minimum=4,neighbors=12,radii=[30,25,20],max_per_hole=2,minimum_holes=3,nugget=.1,partial_sill=1.7,range_m=40)
  targets=rng.uniform(-10,10,(24,3))
  for extra in ({},{'variogram_ranges':[30,20,10],'variogram_angles':[70,20,0]}, {'faults':[dict(name='F',point=[0,0,0],normal=[1,0,0])]}, {'faults':[dict(name='F',point=[0,0,0],normal=[1,0,0],slip=[0,0,3])],'restore_fault_slip':True}):
   estimator=Estimator(samples,dict(params,**extra));rust=rust_predictions(estimator,targets)
   for point,actual in zip(targets,rust):
    expected=estimator.predict(point);self.assertEqual(actual['status'],expected['status']);self.assertEqual(actual['neighbors'],expected['neighbors'])
    for key in ('grade','variance','kriging_efficiency','slope_of_regression'):
     if expected.get(key) is None:self.assertIsNone(actual.get(key))
     else:self.assertAlmostEqual(actual[key],expected[key],places=9)
  with self.assertRaises(RuntimeError):rust_predictions(estimator,targets,cancel=lambda:True)

 def test_exact_sample_and_singular_system(self):
  from rainymine.native_engine import rust_predictions
  samples=[dict(xyz=[i,0,0],grade=2.,hole_id=str(i)) for i in range(4)]
  est=Estimator(samples,dict(method='kriging',minimum=1,neighbors=4))
  result=rust_predictions(est,[[0,0,0]])[0];self.assertEqual(result['status'],'exact_sample');self.assertEqual(result['variance'],0.)
  duplicate=np.zeros((2,3));targets=np.ones((1,3));ids=np.array([[0,1]],dtype=np.int64)
  result=rainymine_core.ok_batch(duplicate,np.ones(2),targets,ids,0.,1.,100.)
  self.assertEqual(result[0,4],2.)

 def test_estimate_model_native_route_and_frozen_smoke(self):
  from rainymine.core import Project,Collar,Assay
  from rainymine.estimation import estimate_model
  from rainymine.packaged_checks import verify_native_kernels
  project=Project(collars=[Collar(str(i),x,y,20,20) for i,(x,y) in enumerate(((0,0),(10,0),(0,10),(10,10)))],assays=[Assay(str(i),0,20,float(i+1)) for i in range(4)])
  params=dict(method='kriging',minimum=3,neighbors=8,radii=[100]*3,composite_length=10)
  reference=estimate_model(project,[0,0,0,10,10,10],[5,5,5],params)
  actual=estimate_model(project,[0,0,0,10,10,10],[5,5,5],dict(params,backend='rust'))
  self.assertEqual(actual['params']['backend'],'rust')
  np.testing.assert_allclose([b['grade'] for b in actual['blocks']],[b['grade'] for b in reference['blocks']],atol=1e-9)
  with self.assertRaises(ValueError):estimate_model(project,[0,0,0,10,10,10],[5,5,5],dict(params,backend='rust',discretization=[2,2,2]))
  verify_native_kernels()

 def test_disk_pit_reference_and_atomic_cancel(self):
  from rainymine.disk_model import DiskModel
  from rainymine.disk_pit import optimize_disk_pit
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'blocks.rmdb';output=Path(directory)/'pit.csv'
   DiskModel.create(path,[0,0,0],[1,1,2],[10,10,10],'EPSG:32648','%',density=1.)
   with DiskModel(path) as store:
    store.edit(0,10.,1.,None);store.edit(1,0.,1.,None)
   report=optimize_disk_pit(path,output,1,1,2,1,1)
   self.assertEqual(report['net_value'],5000);self.assertEqual(report['selected_blocks'],2)
   self.assertEqual(len(output.read_text(encoding='utf-8').splitlines()),3)
   original=output.read_bytes()
   with self.assertRaises(RuntimeError):optimize_disk_pit(path,output,1,1,2,1,1,cancel=lambda:True)
   self.assertEqual(output.read_bytes(),original)
   with self.assertRaises(ValueError):optimize_disk_pit(path,output,1,1,2,1,1,memory_budget_mib=.0001)

   with DiskModel(path) as store:
    store.db.execute('UPDATE blocks SET x=x+1 WHERE id=0');store.db.commit()
   with self.assertRaisesRegex(ValueError,'geometry'):optimize_disk_pit(path,output,1,1,2,1,1)
   self.assertEqual(output.read_bytes(),original)
