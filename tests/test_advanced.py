import math
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from rainymine.core import *
from rainymine.geometry import *
from rainymine.data_tools import *
from rainymine.estimation import *
from rainymine.planning import *

class DataPreparation(unittest.TestCase):
    def test_mapped_import_reports_rejected_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'m.csv';p.write_text('Нэр;Гүн;Зүг;Налуу\nА;0;45;-60\nБ;bad;0;-90',encoding='utf-8')
            headers,preview,delimiter=csv_preview(p);self.assertEqual(delimiter,';')
            rows,report=mapped_import(p,'surveys',dict(zip(SCHEMAS['surveys'],headers)),delimiter)
            self.assertEqual(report['accepted'],1);self.assertEqual(report['rejected'],1);self.assertEqual(report['issues'][0]['row'],3)
            self.assertEqual(rows_to_values('surveys',rows)[0].hole_id,'А')
    def test_mapping_profile_roundtrip_and_missing_columns(self):
        mapping=dict(zip(SCHEMAS['surveys'],['Нэр','Гүн','Зүг','Налуу']))
        original=Project()
        updated=save_mapping_profile(original,'Лаборатори','surveys',mapping)
        self.assertNotIn('mapping_profiles',original.workspace)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'profiles.rmine';save_project(path,updated)
            restored=load_project(path)
            self.assertEqual(mapping_profile(restored,'Лаборатори','surveys',list(mapping.values())),mapping)
            with self.assertRaises(ValueError):mapping_profile(restored,'Лаборатори','surveys',['Нэр'])
        history=History();history.apply(original,updated,'profile')
        self.assertNotIn('mapping_profiles',history.undo(updated).workspace)
        self.assertEqual(mapping_profile(history.redo(original),'Лаборатори','surveys',list(mapping.values())),mapping)
        for invalid in ('', 'x'*81):
            with self.assertRaises(ValueError):save_mapping_profile(original,invalid,'surveys',mapping)
        with self.assertRaises(ValueError):save_mapping_profile(original,'bad','surveys',dict.fromkeys(SCHEMAS['surveys'],'same'))

    def test_csv_structural_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.csv'
            path.write_text('hole_id,depth,azimuth,dip\nA,0,0,-90,EXTRA\nB,0,0\nC,0,0,-90\n')
            rows,report=mapped_import(path,'surveys',{k:k for k in SCHEMAS['surveys']})
            self.assertEqual(report['accepted'],1)
            self.assertEqual([r['row'] for r in report['issues']],[2,3])
            for header in ('hole_id,depth,azimuth,dip,dip', 'hole_id,depth,azimuth,dip,'):
                path.write_text(header+'\nA,0,0,-90,1\n')
                with self.assertRaises(ValueError):csv_preview(path)
                with self.assertRaises(ValueError):mapped_import(path,'surveys',{k:k for k in SCHEMAS['surveys']})

    def test_history_is_transactional(self):
        old=Project();new=Project(name='Шинэ');history=History();history.apply(old,new,'rename')
        self.assertEqual(history.undo(new).name,old.name);self.assertEqual(history.redo(old).name,new.name)
        with self.assertRaises(ValueError):history.apply(new,Project(name=''),'bad')
        self.assertEqual(len(history.undo_items),1)
    def test_lithology_overlap_and_migration(self):
        p=Project(collars=[Collar('A',0,0,0,100)],lithology=[Lithology('A',0,50,'Granite'),Lithology('A',50,100,'Ore')]);p.validate()
        old=p.to_dict();old['version']=1;old.pop('lithology');old.pop('workspace');old.pop('crs_code');self.assertEqual(Project.from_dict(old).lithology,[])
        p.lithology.append(Lithology('A',40,60,'Bad'))
        with self.assertRaises(ValueError):p.validate()
    def test_crs_independent_control_point(self):
        p=Project(collars=[Collar('A',105,0,123,100,0,-90)])
        out=transform_project(p,'EPSG:4326','EPSG:32648')
        self.assertAlmostEqual(out.collars[0].x,500000,places=5);self.assertAlmostEqual(out.collars[0].y,0,places=5);self.assertEqual(out.collars[0].z,123)
        self.assertEqual(p.collars[0].x,105)
        with self.assertRaises(ValueError):transform_project(p,'EPSG:32648','EPSG:4326')
    def test_crs_roundtrip_projected(self):
        p=Project(collars=[Collar('A',500100,5300100,1400,100,45,-60)],surveys=[Survey('A',0,45,-60),Survey('A',100,55,-70)])
        out=transform_project(transform_project(p,'EPSG:32648','EPSG:32649'),'EPSG:32649','EPSG:32648')
        self.assertAlmostEqual(out.collars[0].x,p.collars[0].x,places=5);self.assertAlmostEqual(out.collars[0].y,p.collars[0].y,places=5);self.assertAlmostEqual(out.collars[0].azimuth,45,places=3)
    def test_qaqc_controls_and_gaps(self):
        rows=[{'type':'standard','measured':13,'expected':10,'sd':1},{'type':'blank','measured':.2},{'type':'duplicate','measured':2,'expected':4}]
        out=evaluate_controls(rows);self.assertTrue(out[0]['passed']);self.assertFalse(out[1]['passed']);self.assertFalse(out[2]['passed'])
        p=Project(collars=[Collar('A',0,0,0,100)],assays=[Assay('A',10,90,1)])
        self.assertEqual([(r['from_m'],r['to_m']) for r in qaqc_assays(p)],[(0,10),(90,100)])

class GeometryExchange(unittest.TestCase):
    def tetra(self):return {'name':'Tetra','vertices':[[0,0,0],[1,0,0],[0,1,0],[0,0,1]],'faces':[[0,2,1],[0,1,3],[1,2,3],[2,0,3]]}
    def test_mesh_volume_topology(self):
        r=mesh_report(self.tetra());self.assertTrue(r['closed_oriented_topology']);self.assertAlmostEqual(abs(r['signed_volume_m3']),1/6);self.assertFalse(r['self_intersections_checked'])
        m=self.tetra();m['faces'].pop();self.assertFalse(mesh_report(m)['closed_oriented_topology'])
    def test_obj_and_dxf_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tetra.obj';write_obj(p,self.tetra());self.assertEqual(read_obj(p)['faces'],self.tetra()['faces'])
            s={'name':'Polygon','points':[[0,0,0],[2,0,0],[2,2,0],[0,2,0]],'closed':True};p=Path(d)/'geometry.dxf';write_dxf(p,{'strings':[s],'meshes':[self.tetra()]});out,unsupported=read_dxf(p)
            self.assertEqual(len(out['strings']),1);self.assertTrue(mesh_report(out['meshes'][0])['closed_oriented_topology']);self.assertFalse(unsupported)
    def test_polygon_self_crossing_and_domain(self):
        p=[[500000,5300000,0],[500010,5300000,0],[500010,5300010,0],[500000,5300010,0]]
        self.assertAlmostEqual(validate_polygon(p),100);self.assertTrue(inside_polygon(500005,5300005,p));self.assertFalse(inside_polygon(500020,5300005,p))
        with self.assertRaises(ValueError):validate_polygon([p[0],p[2],p[1],p[3]])
    def test_constrained_tin_requires_diagonal(self):
        s=[[0,0,0],[10,0,0],[10,10,1],[0,10,0]];line={'points':[s[0],s[2]],'closed':False}
        out=constrained_tin(s,[line]);self.assertEqual(len(out['faces']),2)
        with self.assertRaises(ValueError):constrained_tin(s,[line,{'points':[s[1],s[3]],'closed':False}])
    def test_underground_box_volume(self):
        mesh,report=underground_drive([0,0,0],[10,0,0],4,3);r=mesh_report(mesh)
        self.assertTrue(r['closed_oriented_topology']);self.assertAlmostEqual(abs(r['signed_volume_m3']),120);self.assertEqual(report['gradient_percent'],0)
    def test_bench_constraints(self):
        mesh,strings,report=pit_benches([0,0],100,0,10,3,60,5,16)
        self.assertEqual(len(strings),7);self.assertLess(report['overall_slope_deg'],60);self.assertFalse(report['ramp_included'])
        with self.assertRaises(ValueError):pit_benches([0,0],100,0,10,3,95,5)

class EstimationTests(unittest.TestCase):
    def samples(self):return [{'hole_id':'A','xyz':[-1.,0.,0.],'grade':0.},{'hole_id':'B','xyz':[1.,0.,0.],'grade':2.}]
    def test_idw_symmetry_and_exact(self):
        e=Estimator(self.samples(),{'minimum':2,'neighbors':2,'radii':[10,10,10]})
        self.assertAlmostEqual(e.predict([0,0,0])['grade'],1);self.assertEqual(e.predict([1,0,0])['grade'],2)
        self.assertIsNone(e.predict([100,0,0])['grade'])
    def test_kriging_constant_and_symmetry(self):
        params={'method':'kriging','minimum':2,'neighbors':2,'radii':[10,10,10],'range_m':10,'partial_sill':1}
        r=Estimator(self.samples(),params).predict([0,0,0]);self.assertAlmostEqual(r['grade'],1);self.assertGreaterEqual(r['variance'],0)
        samples=self.samples()
        for s in samples:s['grade']=5
        self.assertAlmostEqual(Estimator(samples,params).predict([0,.5,0])['grade'],5)
    def test_spherical_variogram_analytic(self):
        self.assertAlmostEqual(float(gamma_spherical(5,.2,2,10)),.2+2*(1.5*.5-.5*.5**3))
        self.assertEqual(float(gamma_spherical(0,.2,2,10)),0);self.assertEqual(float(gamma_spherical(20,.2,2,10)),2.2)
    def test_holdout_holes_no_leakage(self):
        samples=[{'hole_id':h,'xyz':[x,y,0],'grade':4} for h,x in [('A',0),('B',10)] for y in (0,1)]
        r=cross_validate(samples,{'minimum':2,'neighbors':4,'radii':[100,100,100]});self.assertEqual(r['predicted'],4);self.assertEqual(r['rmse'],0)
        for s in samples:s['hole_id']='A'
        self.assertEqual(cross_validate(samples,{'minimum':1,'neighbors':4})['predicted'],0)
    def test_search_basis_and_rotated_selection(self):
        import numpy as np
        self.assertTrue(np.allclose(search_basis(),np.eye(3)))
        basis=search_basis(35,-40,20)
        self.assertTrue(np.allclose(basis.T@basis,np.eye(3)))
        self.assertAlmostEqual(np.linalg.det(basis),1.)
        samples=[{'hole_id':'E','xyz':[8,0,0],'grade':1},
                 {'hole_id':'N','xyz':[0,8,0],'grade':9}]
        params={'minimum':1,'neighbors':1,'radii':[10,2,2]}
        self.assertEqual(Estimator(samples,params).predict([0,0,0])['grade'],1)
        self.assertEqual(Estimator(samples,dict(params,search_angles=[0,0,0])).predict([0,0,0])['grade'],9)
        local=[{'hole_id':str(i),'xyz':xyz,'grade':grade} for i,xyz,grade in
               [(0,[4,0,0],2),(1,[6,1,0],8),(2,[-5,0,0],5)]]
        rotated=[dict(row,xyz=(np.array(row['xyz'])@basis.T+[500000,5300000,1400]).tolist()) for row in local]
        for method in ('idw','kriging'):
            settings=dict(params,method=method,minimum=2,neighbors=3)
            expected=Estimator(local,settings).predict([0,0,0])
            actual=Estimator(rotated,dict(settings,search_angles=[35,-40,20])).predict([500000,5300000,1400])
            self.assertAlmostEqual(actual['grade'],expected['grade'],places=8)
            if method=='kriging':self.assertAlmostEqual(actual['variance'],expected['variance'],places=8)
        with self.assertRaises(ValueError):search_basis(0,91,0)

    def test_directional_variogram_axes_bandwidth_and_symmetry(self):
        samples=[{'xyz':[0,0,0],'grade':0},{'xyz':[10,0,0],'grade':2},
                 {'xyz':[0,10,0],'grade':10}]
        east={'azimuth':90,'dip':0,'tolerance':5,'bandwidth':2}
        north=dict(east,azimuth=0)
        e=experimental_variogram(samples,20,1,east)
        n=experimental_variogram(samples,20,1,north)
        self.assertEqual(e['pair_count'],1);self.assertEqual(e['rows'][0]['semivariance'],2)
        self.assertEqual(n['rows'][0]['semivariance'],50)
        self.assertFalse(e['isotropic']);self.assertEqual(e['direction'],east)
        reverse=experimental_variogram(samples,20,1,dict(east,azimuth=270))
        self.assertEqual(reverse['rows'],e['rows'])
        diagonal=[{'xyz':[0,0,0],'grade':0},{'xyz':[10,1,0],'grade':2}]
        self.assertEqual(experimental_variogram(diagonal,20,1,dict(east,tolerance=15,bandwidth=.5))['pair_count'],0)
        for bad in (dict(east,tolerance=0),dict(east,bandwidth=-1),dict(east,dip=100)):
            with self.assertRaises(ValueError):experimental_variogram(samples,20,1,bad)

    def test_block_volume_and_tonnage(self):
        blocks=make_blocks([0,0,0,2.5,2,2],[1,1,1]);self.assertAlmostEqual(sum(b['dx']*b['dy']*b['dz'] for b in blocks),10)
        for b in blocks:b['grade']=2
        rows=tonnage_grade({'blocks':blocks},3,[1,3]);self.assertEqual(rows[0]['tonnes'],30);self.assertEqual(rows[0]['mean_grade'],2);self.assertEqual(rows[1]['tonnes'],0)
    def test_variogram_pairs(self):
        r=experimental_variogram(self.samples(),3,1);self.assertEqual(r['rows'][0]['pairs'],1);self.assertEqual(r['rows'][0]['semivariance'],2)
    def test_estimation_project_roundtrip_and_domain(self):
        p=demo();domain={'name':'test','closed':True,'points':[[499900,5299900,0],[500500,5299900,0],[500500,5300500,0],[499900,5300500,0]]}
        model=estimate_model(p,[499900,5299900,1100,500500,5300500,1500],[100,100,100],{'minimum':2,'neighbors':8,'radii':[300,300,200],'composite_length':10},domain)
        self.assertTrue(any(b['grade'] is not None for b in model['blocks']))
        p.workspace['block_model']=model
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'model.rmine';save_project(f,p);out=load_project(f)
            self.assertEqual(out.workspace['block_model']['input_sha256'],model['input_sha256'])
            self.assertEqual(len(out.workspace['block_model']['blocks']),len(model['blocks']))
    def test_duplicate_support_and_invalid_search(self):
        samples=self.samples();samples[1]['xyz']=samples[0]['xyz']
        with self.assertRaises(ValueError):Estimator(samples,{})
        with self.assertRaises(ValueError):Estimator(self.samples(),{'radii':[0,1,1]})

class SchedulingTests(unittest.TestCase):
    def test_precedence_capacity_and_reconciliation(self):
        tasks=[{'id':'A','tonnes':10,'process_tonnes':5,'value':10,'predecessors':[]},{'id':'B','tonnes':10,'process_tonnes':5,'value':20,'predecessors':['A']}]
        r=schedule(tasks,10,5,2);self.assertTrue(r['feasible_complete']);self.assertEqual([t['id'] for t in r['rows']],['A','B']);self.assertEqual(sum(t['tonnes'] for t in r['rows']),20)
        self.assertFalse(schedule(tasks,9,5,2)['feasible_complete'])
    def test_cycle_rejected(self):
        tasks=[{'id':'A','tonnes':1,'process_tonnes':0,'value':0,'predecessors':['B']},{'id':'B','tonnes':1,'process_tonnes':0,'value':0,'predecessors':['A']}]
        with self.assertRaises(ValueError):schedule(tasks,10,10,2)

if __name__=='__main__':unittest.main()
