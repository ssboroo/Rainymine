import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from rainymine.estimation import Estimator,make_blocks
from rainymine.geostat_tools import cap_analysis,cell_decluster,propose_classes
from rainymine.daily_tools import tin_cut_fill,survey_pattern,ore_control_polygons,stereonet
from rainymine.copilot_tools import validate_plan,parse_query,model_query,disk_query
from rainymine.core import Project,Collar,Assay,Lithology


class GeostatTests(unittest.TestCase):
    def test_distance_cap_global_cap_and_native_ok_parity(self):
        samples=[dict(xyz=[-10,0,0],grade=150.,hole_id='A'),dict(xyz=[10,0,0],grade=1.,hole_id='B')]
        params={'method':'nearest','minimum':1,'neighbors':2,'radii':[100]*3,'high_grade_restriction':{'threshold':10,'radius_m':15}}
        estimator=Estimator(samples,params)
        self.assertEqual(estimator.predict([-10,0,0])['grade'],150)
        self.assertEqual(estimator.predict([-30,0,0])['grade'],10)
        self.assertEqual(Estimator(samples,{**params,'top_cut':20}).predict([-10,0,0])['grade'],20)
        try:import rainymine_core
        except ImportError:self.skipTest('Native extension required for parity check')
        from rainymine.native_engine import rust_predictions
        e=Estimator(samples,{**params,'method':'kriging','nugget':.1,'partial_sill':1,'range_m':100})
        points=[[-10,0,0],[0,0,0],[20,0,0],[40,0,0]];native=rust_predictions(e,points)
        for p,r in zip(points,native):
            expected=e.predict(p);self.assertAlmostEqual(r['grade'],expected['grade'],places=9);self.assertAlmostEqual(r['variance'],expected['variance'],places=9)
        with self.assertRaises(ValueError):rainymine_core.ok_batch(np.array([s['xyz'] for s in samples],float),np.array([150.,1.]),np.array([[0.,0,0]]),np.array([[0,1]],np.int64),0.,1.,100.,np.zeros((2,2)))

    def test_dynamic_search_selects_local_not_fixed_direction(self):
        samples=[dict(xyz=xyz,grade=g,hole_id=str(i)) for i,(xyz,g) in enumerate([([20,0,0],5),([0,20,0],10),([120,0,0],50),([100,20,0],100)])]
        params={'method':'nearest','minimum':1,'neighbors':1,'radii':[30,2,2],
                'dynamic_anisotropy':{'kind':'normal_controls','controls':[{'xyz':[0,0,0],'normal':[0,0,1]},{'xyz':[100,0,0],'normal':[1,0,0]}]}}
        e=Estimator(samples,params);self.assertEqual(e.predict([0,0,0])['grade'],5);self.assertEqual(e.predict([100,0,0])['grade'],100)
        self.assertEqual(e.predict([100,0,0])['distinct_holes'],1);self.assertEqual(e.predict([100,0,0])['nearest_sample_distance_m'],20)

    def test_declustering_analytic_and_cap_zero_log_handling(self):
        samples=[dict(xyz=[x,0,0],grade=g) for x,g in [(0,1),(.1,1),(10,9)]]
        result=cell_decluster(samples,[1,1,1],[[0,0,0]])
        np.testing.assert_allclose(result['weights'],[.25,.25,.5]);self.assertEqual(result['declustered_mean'],5)
        stats=cap_analysis([dict(xyz=[i,0,0],grade=g) for i,g in enumerate([0,1,150])],10)
        self.assertEqual(stats['capped_samples'],1);self.assertEqual(stats['nonpositive_excluded_from_log_plot'],1)
        self.assertAlmostEqual(stats['capped_mean'],11/3);self.assertEqual(sum(b['support_m'] for b in stats['histogram']),3)

    def test_proposal_does_not_overwrite_approved_labels_or_invent_diagnostics(self):
        source={'blocks':[dict(grade=2,resource_class='A',slope_of_regression=.9,distinct_holes=3),dict(grade=2)]}
        result,report=propose_classes(source,[{'name':'Measured','minimum_sor':.8,'minimum_holes':3}])
        self.assertEqual(result['blocks'][0]['resource_class'],'A');self.assertEqual(result['blocks'][0]['classification_proposal']['proposed_class'],'Measured')
        self.assertEqual(result['blocks'][1]['classification_proposal']['proposed_class'],'Unclassified');self.assertFalse(report['approval'])
        self.assertNotIn('classification_proposal',source['blocks'][0])


def square(z,diagonal=False,offset=0):
    xy=[[0+offset,0],[1+offset,0],[1+offset,1],[0+offset,1]]
    return {'name':'TIN','vertices':[[x,y,z(x,y)] for x,y in xy], 'faces':[[0,1,3],[1,2,3]] if diagonal else [[0,1,2],[0,2,3]]}


class DailyTests(unittest.TestCase):
    def test_crossing_tins_exact_cut_fill_and_partial_coverage(self):
        report=tin_cut_fill(square(lambda x,y:0),square(lambda x,y:x-.5,True),2)
        self.assertAlmostEqual(report['cut_m3'],.125);self.assertAlmostEqual(report['fill_m3'],.125);self.assertAlmostEqual(report['cut_tonnes'],.25)
        partial=tin_cut_fill(square(lambda x,y:0),square(lambda x,y:1,True,.5))
        self.assertAlmostEqual(partial['common_area_m2'],.5);self.assertAlmostEqual(partial['fill_m3'],.5);self.assertIsNone(partial['fill_tonnes'])
        with self.assertRaises(RuntimeError):tin_cut_fill(square(lambda x,y:0),square(lambda x,y:1),cancel=lambda:True)

    def test_rectangular_and_staggered_sample_grid(self):
        polygon=[[0,0,0],[20,0,0],[20,20,0],[0,20,0]]
        self.assertEqual(len(survey_pattern(polygon,10,10,100,95)),9)
        rows=survey_pattern(polygon,10,10,100,95,True);self.assertEqual(len(rows),8);self.assertTrue(all(r['depth']==5 for r in rows));self.assertFalse(any('charge' in r for r in rows))

    def test_ore_unknown_hole_preserved_in_dxf_and_shapefile(self):
        from rainymine.daily_export import export_diglines
        import shapefile
        blocks=make_blocks([0,0,0,30,30,10],[10,10,10])
        for b in blocks:b['grade']=None if b['i']==b['j']==1 else 2
        rows=ore_control_polygons({'blocks':blocks},5,1);ore=next(r for r in rows if r['kind']=='ore')
        self.assertEqual(ore['area_m2'],800);self.assertEqual(len(ore['holes']),1)
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'dig';export_diglines(rows,target,'EPSG:32648');reader=shapefile.Reader(str(target/'diglines'))
            self.assertEqual(len(reader),2);self.assertTrue(any(len(s.parts)==2 for s in reader.shapes()));self.assertTrue((target/'diglines.dxf').exists());reader.close()

    def test_stereonet_projection_cardinals_and_screen(self):
        report=stereonet([{'dip_direction':0,'dip':0},{'dip_direction':0,'dip':90},{'dip_direction':0,'dip':45}],slope_direction=0,slope_dip=60,friction=30)
        self.assertAlmostEqual(report['poles'][0]['x'],0);self.assertAlmostEqual(report['poles'][0]['y'],0)
        self.assertAlmostEqual(math.hypot(report['poles'][1]['x'],report['poles'][1]['y']),1)
        self.assertTrue(report['plane_checks'][2]['planar_screen'])
        self.assertFalse(report['plane_checks'][1]['planar_screen'])


class CopilotWorkflowTests(unittest.TestCase):
    def test_bound_sql_and_in_memory_totals_match_without_mutation(self):
        from rainymine.disk_import import import_disk_csv
        plan=parse_query('Оксид бүс, агуулга > 0.5 болон Z > 1200',['Оксид','Сульфид'])
        blocks=[dict(x=1,y=2,z=1300,dx=10,dy=10,dz=10,grade=1,density=2,domain='Оксид'),dict(x=2,y=2,z=1100,dx=10,dy=10,dz=10,grade=2,density=3,domain='Оксид')]
        model=model_query({'blocks':blocks},plan,'%');self.assertEqual(model['totals']['tonnes'],2000)
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'blocks.csv';columns=list(blocks[0])
            import csv
            with source.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(blocks)
            db=Path(folder)/'blocks.rmdb';import_disk_csv(source,db,{k:k for k in columns},'EPSG:32648','%')
            actual=disk_query(db,plan);self.assertEqual(actual['totals']['tonnes'],2000);self.assertEqual(actual['totals']['mean_grade'],1)
            injection={'tool':'filter_blocks','conditions':[{'field':'domain','op':'=','value':"Оксид' OR 1=1 --"}]}
            self.assertEqual(disk_query(db,injection)['totals']['blocks'],0)
        with self.assertRaises(ValueError):validate_plan({'tool':'sql','query':'DROP TABLE blocks'})
        with self.assertRaises(ValueError):parse_query('Au > 0.5',['Оксид'])
        with self.assertRaises(ValueError):parse_query('grade > 1 OR Z > 10')
        with self.assertRaises(ValueError):parse_query('Оксид бүс grade > 1',[])
        with self.assertRaises(RuntimeError):model_query({'blocks':blocks},plan,'%',cancel=lambda:True)

    def test_workflow_allowlist_and_atomic_failure(self):
        from rainymine.workflow import run_workflow,validate_recipe
        from rainymine.core import demo
        p=demo();before=p.to_dict()
        recipe={'version':1,'steps':[{'tool':'validate','params':{}},{'tool':'cap_analysis','params':{'cap':1}}]}
        candidate,log=run_workflow(p,recipe);self.assertEqual(p.to_dict(),before);self.assertEqual(len(log),2)
        with self.assertRaises(ValueError):validate_recipe({'version':1,'steps':[{'tool':'python','params':{'code':'x'}}]})
        with self.assertRaises(RuntimeError):run_workflow(p,recipe,cancel=lambda:True)
        self.assertEqual(p.to_dict(),before)

    def test_qaqc_uses_actual_batch_and_certified_sd(self):
        from rainymine.data_tools import evaluate_controls
        from rainymine.quality_advisor import quality_advice
        rows=evaluate_controls([dict(type='standard',measured=1.4,expected=1,sd=.1,batch='B3',lab='L3')])
        report=quality_advice(rows);self.assertEqual(len(report['issues']),1);self.assertIn('L3',report['text']);self.assertIn('B3',report['text'])


class MapTests(unittest.TestCase):
    def test_rotated_cube_plane_and_three_vector_papers(self):
        from rainymine.map_composer import block_section,export_map
        from rainymine.spatial import search_basis
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        b=dict(x=0,y=0,z=0,dx=2,dy=2,dz=2,grade=1,density=2)
        poly=block_section(b,search_basis(45,0,0),(0,1,2),0)
        area=abs(sum(a[0]*c[1]-c[0]*a[1] for a,c in zip(poly,poly[1:]+poly[:1])))/2;self.assertAlmostEqual(area,4)
        p=Project(name='Vector analytic fixture',crs_code='EPSG:32648',collars=[Collar('H1',0,0,10,10)],assays=[Assay('H1',0,10,2)],lithology=[Lithology('H1',0,10,'Хүдэр')])
        p.workspace['block_model']={'blocks':[{**b,'z':5,'dz':10}]}
        with tempfile.TemporaryDirectory() as folder:
            for paper in ('A3','A1','A0'):
                target=Path(folder)/paper;export_map(p,{'view':'XZ','position':0,'paper':paper,'scale':'auto','slab_width':10},target)
                self.assertTrue((target/'map.pdf').read_bytes().startswith(b'%PDF'));self.assertIn('<svg',(target/'map.svg').read_text(encoding='utf-8'));self.assertEqual(json.loads((target/'layout.json').read_text(encoding='utf-8'))['paper'],paper)


if __name__=='__main__':unittest.main()
