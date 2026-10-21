import csv
import itertools
import tempfile
import unittest
from pathlib import Path
from rainymine.domains import adaptive_blocks,validate_faults,fault_zone,fault_patch
from rainymine.estimation import make_blocks,Estimator,estimate_model,experimental_variogram
from rainymine.core import demo,save_project,load_project
from rainymine.planning import haul_route,haul_capacity,optimize_schedule,economic_tasks,tasks_from_blocks
from rainymine.benchmark import compare_reference

FAULT={'name':'F','point':[0,0,0],'normal':[1,0,0]}

class GeologicalExtensions(unittest.TestCase):
    def test_subblocks_conserve_volume_and_coalesce(self):
        bounds=[-1,-1,-1,1,1,1];parents=make_blocks(bounds,[2,2,2])
        refined=adaptive_blocks(parents,bounds,[90,0,0],None,[FAULT],2)
        self.assertEqual(len(refined),8)
        self.assertEqual({b['subblock_level'] for b in refined},{1})
        self.assertEqual(len({b['block_id'] for b in refined}),8)
        self.assertAlmostEqual(sum(b['dx']*b['dy']*b['dz'] for b in refined),8)
        self.assertEqual({b['fault_zone'] for b in refined},{0,1})
        uniform=adaptive_blocks(parents,bounds,[90,0,0],None,[],2)
        self.assertEqual(len(uniform),1);self.assertEqual(uniform[0]['subblock_level'],0)
        polygon={'points':[[-1,-1,0],[0,-1,0],[0,1,0],[-1,1,0]]}
        clipped=adaptive_blocks(parents,bounds,[90,0,0],polygon,[],2)
        self.assertAlmostEqual(sum(b['dx']*b['dy']*b['dz'] for b in clipped),4)
        with self.assertRaises(ValueError):adaptive_blocks(parents,bounds,[90,0,0],None,[],4)

    def test_fault_barrier_prevents_grade_leakage(self):
        samples=[{'hole_id':'A','xyz':[-2,0,0],'grade':1},{'hole_id':'B','xyz':[1,0,0],'grade':100}]
        e=Estimator(samples,{'minimum':1,'neighbors':2,'faults':[FAULT]})
        self.assertEqual(e.predict([-1,0,0])['grade'],1)
        self.assertEqual(e.predict([2,0,0])['grade'],100)
        self.assertIsNone(e.predict([-1,0,0],exclude_hole='A')['grade'])
        self.assertEqual(experimental_variogram(samples,10,1,faults=[FAULT])['pair_count'],0)
        self.assertEqual(fault_zone([0,0,0],[FAULT]),1)
        self.assertEqual(len(fault_patch(FAULT,10)['vertices']),4)
        with self.assertRaises(ValueError):validate_faults([dict(FAULT,normal=[0,0,0])])

    def test_fault_subblock_project_roundtrip(self):
        p=demo();p.workspace['faults']=[dict(FAULT,point=[500020,5300000,1200])]
        params={'minimum':1,'neighbors':4,'radii':[1000]*3,'composite_length':20,'subblock_levels':1}
        m=estimate_model(p,[500000,5300000,1200,500040,5300040,1240],[40]*3,params)
        self.assertEqual(len(m['blocks']),8);self.assertEqual(m['faults'],p.workspace['faults'])
        p.workspace['block_model']=m
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fault.rmine';save_project(path,p);self.assertEqual(load_project(path).workspace,p.workspace)
        with self.assertRaises(ValueError):tasks_from_blocks(m,2.5,.5)

class PlanningExtensions(unittest.TestCase):
    def test_route_grade_and_fleet_hand_calculation(self):
        route=haul_route([[0,0,0],[1000,0,0]],10,10)
        r=haul_capacity(route,40,2,20,30,3,1,1,8,.8)
        self.assertEqual(r['cycle_minutes'],10)
        self.assertAlmostEqual(r['fleet_tonnes_per_shift'],3072)
        steep=haul_route([[0,0,0],[100,0,20]],10,10)
        self.assertFalse(steep['within_gradient_limit'])
        with self.assertRaises(ValueError):haul_capacity(steep,40,2,20,30,3,1,1,8,.8)
        with self.assertRaises(ValueError):haul_route([[0,0,0],[0,0,10]],10)

    def test_milp_matches_exhaustive_optional_schedule(self):
        tasks=[{'id':'A','tonnes':1,'process_tonnes':0,'value':-2,'predecessors':[]},
               {'id':'B','tonnes':1,'process_tonnes':1,'value':20,'predecessors':['A']},
               {'id':'C','tonnes':1,'process_tonnes':1,'value':9,'predecessors':[]}]
        discount=.1;best=0
        for choices in itertools.product((0,1,2),repeat=3):
            if choices[1] and not 0<choices[0]<choices[1]:continue
            if any(sum(t['tonnes'] for t,p in zip(tasks,choices) if p==period)>1 for period in (1,2)):continue
            objective=sum(t['value']/(1+discount)**(p-1) for t,p in zip(tasks,choices) if p)
            best=max(best,objective)
        r=optimize_schedule(tasks,1,1,2,discount)
        self.assertTrue(r['optimal']);self.assertAlmostEqual(r['discounted_objective'],best)
        self.assertEqual([(x['id'],x['period']) for x in r['rows']],[('A',1),('B',2)])
        negative=optimize_schedule([dict(tasks[0],predecessors=[])],1,1,1)
        self.assertEqual(negative['rows'],[])
        with self.assertRaises(ValueError):optimize_schedule([dict(tasks[0],predecessors=['A'])],1,1,1)

    def test_economics_grade_unit_conversion(self):
        b=make_blocks([0,0,0,1,1,1],[1,1,1])[0];b['grade']=1
        tasks=economic_tasks({'blocks':[b]},2,.5,'%',1000,1,2,.5,1)
        self.assertAlmostEqual(tasks[0]['value'],2) # 10 revenue - 4 mining/haul - 4 processing
        b['grade']=10000
        converted=economic_tasks({'blocks':[b]},2,.5,'ppm',1000,1,2,.5,1)
        self.assertEqual(converted[0]['value'],tasks[0]['value'])

class ReferenceComparison(unittest.TestCase):
    def test_complete_comparison_never_self_certifies(self):
        model={'blocks':[{'x':1,'y':2,'z':3,'grade':1.01},{'x':4,'y':5,'z':6,'grade':2}], 'run_sha256':'fixture'}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'external.csv';path.write_text('x,y,z,grade\n1,2,3,1\n4,5,6,2\n')
            r=compare_reference(model,path,grade_absolute=.02,grade_relative=0)
            self.assertTrue(r['numerical_pass']);self.assertFalse(r['independent_review_verified'])
            self.assertEqual(len(r['reference_sha256']),64)
            path.write_text('x,y,z,grade\n1,2,3,1\n');self.assertFalse(compare_reference(model,path)['numerical_pass'])
            path.write_text('x,y,z,grade\n1,2,3,1\n1,2,3,1\n')
            with self.assertRaises(ValueError):compare_reference(model,path)

class BenchmarkCLI(unittest.TestCase):
    def test_cli_reports_numerical_pass_without_certification(self):
        import subprocess,json,sys
        p=demo();b=make_blocks([0,0,0,2,2,2],[2,2,2])[0];b['grade']=1
        p.workspace['block_model']={'blocks':[b]}
        with tempfile.TemporaryDirectory() as d:
            project=Path(d)/'p.rmine';save_project(project,p)
            reference=Path(d)/'r.csv';reference.write_text('x,y,z,grade\n1,1,1,1\n')
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts'/'compare_reference.py'),str(project),str(reference)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(json.loads(result.stdout)['independent_review_verified'])
