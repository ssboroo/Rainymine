import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from rainymine.chronology import Chronology,apply_chronology,ScalarField
from rainymine.orientation import source_orientation,basis_angles
from rainymine.spatial import search_basis
from rainymine.disk_import import import_disk_csv
from rainymine.disk_model import DiskModel
from rainymine.core import Project,Collar
from rainymine.cp_validation import create_validation_pack


def plane(axis,position):
    point=[0,0,0];normal=[0,0,0];point[axis]=position;normal[axis]=1
    return {'kind':'plane','point':point,'normal':normal}


def recipe():
    return {'version':1,'events':[
        {'name':'Basement','kind':'intrusion','field':plane(2,-100)},
        {'name':'Layer','kind':'stratigraphy','lower':plane(2,0),'upper':plane(2,10)},
        {'name':'Vein','kind':'vein','lower':plane(0,1),'upper':plane(0,2)},
        {'name':'Young','kind':'intrusion','field':plane(0,5)},
        {'name':'Erosion','kind':'erosion','field':plane(2,8)}]}


class ChronologyTests(unittest.TestCase):
    def test_analytic_contacts_exclusive_youngest_and_erosion(self):
        r=recipe();engine=Chronology(r)
        np.testing.assert_array_equal(engine.classify([[-10,0,-20],[0,0,5],[1.5,0,5],[6,0,5],[6,0,9]]),[1,2,3,4,0])
        r['events'][1],r['events'][3]=r['events'][3],r['events'][1]
        self.assertEqual(int(Chronology(r).classify([[6,0,5]])[0]),4)

    def test_fault_frame_explicit_and_model_invalidates_grades(self):
        r=recipe();r['faults']=[{'name':'F','point':[0,0,0],'normal':[0,1,0],'slip':[5,0,0]}]
        np.testing.assert_array_equal(Chronology(r).classify([[6,1,5],[6,-1,5]]),[3,4])
        original={'blocks':[dict(x=6,y=1,z=5,grade=2,variance=.2,estimation_pass=1)],'run_sha256':'stale'}
        model,report=apply_chronology(original,r)
        self.assertEqual(original['blocks'][0]['grade'],2)
        self.assertIsNone(model['blocks'][0]['grade']);self.assertNotIn('run_sha256',model)
        self.assertEqual(model['blocks'][0]['domain'],'Vein');self.assertFalse(report['watertight_mesh_verified'])
        with self.assertRaises(RuntimeError):Chronology(r).classify([[0,0,0]],lambda:True)

    def test_local_rbf_exact_controls_and_validation(self):
        controls=[{'x':x,'y':y,'z':z,'value':x} for x in (-1,1) for y in (-1,1) for z in (-1,1)]
        field=ScalarField({'kind':'rbf','constraints':controls,'ranges':[1,1,1],'neighbors':8})
        np.testing.assert_allclose(field(np.array([[c[k] for k in 'xyz'] for c in controls])),[c['value'] for c in controls],atol=1e-12)
        with self.assertRaises(ValueError):ScalarField({'kind':'rbf','constraints':controls+controls})
        bad=recipe();bad['events'][1]['name']='Basement'
        with self.assertRaises(ValueError):Chronology(bad)


class OrientationTests(unittest.TestCase):
    def test_matrix_roundtrip_including_vertical_axes(self):
        for a in ([90,0,0],[0,30,45],[37,90,123],[230,-90,-44],[155,-48,177]):
            matrix=search_basis(*a)
            np.testing.assert_allclose(search_basis(*basis_angles(matrix)),matrix,atol=1e-8)
        with self.assertRaises(ValueError):basis_angles(np.diag([1,1,-1]))

    def test_exported_axes_and_explicit_euler_keep_provenance(self):
        result=source_orientation({'source_software':'Micromine exported axes','representation':'axes_azimuth_plunge','axes':[[90,0],[0,0]]})
        np.testing.assert_allclose(result['matrix_enu'],np.eye(3),atol=1e-8)
        self.assertFalse(result['verified_against_vendor_fixture'])
        r=source_orientation({'source_software':'Explicit fixture','representation':'euler_explicit','sequence':'zxy','angles':[90,0,0]})
        np.testing.assert_allclose(r['matrix_enu'],[[0,-1,0],[1,0,0],[0,0,1]],atol=1e-8)
        with self.assertRaises(ValueError):source_orientation({'representation':'axes_azimuth_plunge','axes':[[90,0],[90,0]]})


class DiskImportTests(unittest.TestCase):
    def fixture(self,folder):
        source=Path(folder)/'source.csv';source.write_text('x,y,z,dx,dy,dz,grade,density,domain\n5,5,5,10,10,10,2,2,ore\n12.5,5,5,5,10,10,NULL,4,waste\n',encoding='utf-8')
        return source,{k:k for k in ('x','y','z','dx','dy','dz','grade','density','domain')}

    def test_variable_leaf_sizes_nulls_hash_and_persistent_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            source,mapping=self.fixture(folder);dest=Path(folder)/'model.rmdb'
            report=import_disk_csv(source,dest,mapping,'EPSG:32648','%',batch_size=1)
            self.assertEqual(report['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            with DiskModel(dest) as store:
                self.assertEqual(store.totals()['tonnes'],4000);self.assertEqual(store.totals()['contained_metal_tonnes'],40)
                payload=store.preview(10);self.assertEqual(payload['kind'],'blocks');self.assertTrue(np.isnan(payload['grade'][1]))
                np.testing.assert_array_equal(payload['sizes'],[[10,10,10],[5,10,10]])
                from rainymine.large_view import preview_polydata
                poly,_=preview_polydata(payload);self.assertEqual(poly.GetNumberOfPoints(),2)
                store.edit(1,1,4,'changed');self.assertTrue(store.undo());self.assertEqual(store.totals()['unestimated_blocks'],1)
            with self.assertRaises(ValueError):import_disk_csv(source,dest,mapping,'EPSG:32648','%')

    def test_cancel_invalid_and_rotation_leave_no_store(self):
        with tempfile.TemporaryDirectory() as folder:
            source,mapping=self.fixture(folder);dest=Path(folder)/'bad.rmdb';calls=[]
            def cancel():calls.append(1);return len(calls)>1
            with self.assertRaises(RuntimeError):import_disk_csv(source,dest,mapping,'EPSG:32648','%',batch_size=1,cancel=cancel)
            self.assertFalse(dest.exists());self.assertFalse(list(Path(folder).glob('.rainymine-import-*')))
            source.write_text(source.read_text(encoding='utf-8').replace('2,2,ore','Infinity,2,ore'))
            with self.assertRaises(ValueError):import_disk_csv(source,dest,mapping,'EPSG:32648','%')
            self.assertFalse(dest.exists())
            with self.assertRaises(ValueError):import_disk_csv(source,dest,mapping,'EPSG:4326','%')


class ValidationTests(unittest.TestCase):
    def test_text_null_grade_and_density_are_not_zero(self):
        from rainymine.benchmark import compare_reference
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'nulls.csv';path.write_text('x,y,z,dx,dy,dz,grade,density\n1,2,3,1,1,1,NULL,NULL\n')
            model={'blocks':[dict(x=1,y=2,z=3,dx=1,dy=1,dz=1,grade=None,density=None)]}
            self.assertTrue(compare_reference(model,path,grade_unit='%')['numerical_pass'])
            model['blocks'][0]['grade']=0
            self.assertFalse(compare_reference(model,path,grade_unit='%')['numerical_pass'])

    def fixture(self,folder):
        root=Path(folder);p=Project(name='Analytic review fixture',crs_code='EPSG:32648',collars=[Collar('A',500000,5300000,100,100)])
        p.workspace['block_model']={'params':{'method':'ok','radii':[20,20,20]},'blocks':[
            dict(x=500005.,y=5300005.,z=95.,dx=10.,dy=10.,dz=10.,grade=1.,density=2.),
            dict(x=500015.,y=5300005.,z=95.,dx=10.,dy=10.,dz=10.,grade=3.,density=4.)]}
        blocks=root/'blocks.csv';blocks.write_text('x,y,z,dx,dy,dz,grade,density\n500005,5300005,95,10,10,10,1,2\n500015,5300005,95,10,10,10,3,4\n')
        traces=root/'trajectory.csv';traces.write_text('hole_id,depth,x,y,z\nA,0,500000,5300000,100\nA,50,500000,5300000,50\nA,100,500000,5300000,0\n')
        metadata=root/'meta.json';metadata.write_text(json.dumps({'crs':p.crs_code,'grade_unit':'%',
            'reference_sha256':hashlib.sha256(blocks.read_bytes()).hexdigest(),
            'trajectory_sha256':hashlib.sha256(traces.read_bytes()).hexdigest(),
            'estimation_parameters':p.workspace['block_model']['params'],'grid_angles':[90,0,0],
            'authorized_for_validation':True,'source_software':'hand-calculated analytic fixture','source_version':'1'}))
        return p,blocks,traces,metadata

    def test_equal_analytic_reference_never_self_certifies(self):
        with tempfile.TemporaryDirectory() as folder:
            p,b,t,m=self.fixture(folder);dest=Path(folder)/'pack'
            result=create_validation_pack(p,b,t,m,dest,{'cutoffs':[0,2,4]})
            self.assertTrue(all(result['gates'].values()));self.assertFalse(result['independent_review_verified'])
            data=json.loads((dest/'validation.json').read_text(encoding='utf-8'));self.assertEqual(data['trajectory']['reviewed_holes'],1)
            self.assertEqual(data['block_comparison']['total_differences']['contained_metal_tonnes'],0)
            self.assertIn('<svg',(dest/'review.html').read_text(encoding='utf-8'));self.assertTrue((dest/'review-checklist.csv').exists())

    def test_changed_grade_provenance_and_null_mismatches_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            p,b,t,m=self.fixture(folder);p.workspace['block_model']['blocks'][0]['grade']=None
            result=create_validation_pack(p,b,t,m,Path(folder)/'pack',{'cutoffs':[0]})
            self.assertFalse(result['gates']['block_geometry_null_grade']);self.assertFalse(result['gates']['grade_tonnage'])
            with self.assertRaises(RuntimeError):create_validation_pack(p,b,t,m,Path(folder)/'cancel',{},lambda:True)
            self.assertFalse((Path(folder)/'cancel').exists())


class FloatingStopeTests(unittest.TestCase):
    def test_mass_weighted_internal_dilution_changes_selection(self):
        from rainymine.estimation import make_blocks
        from rainymine.mine_design import stope_boxes
        blocks=make_blocks([0,0,0,20,10,10],[10,10,10]);blocks[0].update(grade=4,density=1);blocks[1].update(grade=0,density=3)
        model={'blocks':blocks}
        accepted=stope_boxes(model,[2,1,1],2,10,1,cutoff=1,maximum_internal_dilution=.8)
        self.assertEqual(len(accepted['selected']),1);self.assertEqual(accepted['selected'][0]['mean_grade'],1)
        self.assertEqual(accepted['selected'][0]['internal_dilution_fraction'],.75)
        rejected=stope_boxes(model,[2,1,1],2,10,1,cutoff=1,maximum_internal_dilution=.5)
        self.assertFalse(rejected['selected'])
        multiple=stope_boxes(model,[2,1,1],2,10,1,shapes=[[1,1,1]],cutoff=1,maximum_internal_dilution=.5)
        self.assertEqual(multiple['selected'][0]['block_indices'],[0])
        self.assertFalse(multiple['commercial_mso_equivalence'])
        blocks[1]['x']+=1
        with self.assertRaises(ValueError):stope_boxes(model,[2,1,1],2,10,1)


class LargePreviewTests(unittest.TestCase):
    def test_null_geometry_preserved_and_admission_budget_enforced(self):
        from rainymine.block_store import write_block_parquet
        from rainymine.large_view import parquet_preview,preview_polydata
        model={'blocks':[dict(x=5,y=5,z=5,dx=10,dy=10,dz=10,grade=None),dict(x=15,y=5,z=5,dx=10,dy=10,dz=10,grade=2)]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'blocks.parquet';write_block_parquet(path,model,'EPSG:32648','%')
            payload=parquet_preview(path,maximum=2);self.assertEqual(len(payload['xyz']),2)
            self.assertEqual(np.isnan(payload['grade']).sum(),1);self.assertEqual(preview_polydata(payload)[0].GetNumberOfPoints(),2)
            self.assertEqual(len(parquet_preview(path,maximum=2,cutoff=0)['xyz']),1)
            with self.assertRaises(ValueError):parquet_preview(path,maximum=2,memory_budget_mib=.00001)


if __name__=='__main__':unittest.main()
