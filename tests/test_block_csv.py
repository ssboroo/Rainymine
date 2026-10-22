import tempfile
import unittest
from pathlib import Path
from rainymine.block_csv import read_block_csv, KEYS
from rainymine.core import Project, save_project, load_project


class BlockCsvTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'blocks.csv'
        self.mapping={k:k for k in KEYS}

    def read(self,text,**kwargs):
        self.path.write_text(text,encoding='utf-8-sig')
        return read_block_csv(self.path,self.mapping,'EPSG:32648','ppm',**kwargs)

    def test_roundtrip_world_coordinates_zero_and_null(self):
        model,report=self.read('x,y,z,dx,dy,dz,grade,rock\n500005,5300005,1005,10,10,10,0,ore\n500015,5300005,1005,10,10,10,NULL,waste\n')
        self.assertEqual(report['null_grades'],1);self.assertEqual(report['extra_columns'],['rock'])
        self.assertEqual(model['blocks'][0]['grade'],0)
        self.assertEqual(model['blocks'][1]['i'],1)
        self.assertEqual(model['bounds'],[500000,5300000,1000,500020,5300010,1010])
        p=Project();p.workspace['block_model']=model
        out=Path(self.tmp.name)/'saved.rmine';save_project(out,p)
        self.assertEqual(load_project(out).workspace['block_model'],model)
        self.assertEqual(len(report['sha256']),64)

    def test_rejects_invalid_geometry_and_grades(self):
        header='x,y,z,dx,dy,dz,grade\n'
        for rows in ['0,0,0,1,1,1,1\n0,0,0,1,1,1,2\n',
                     '0,0,0,1,1,1,1\n0.5,0,0,1,1,1,2\n',
                     '0,0,0,1,1,1,1\n1,0,0,2,1,1,2\n',
                     '0,0,0,0,1,1,1\n','0,0,0,1,1,1,-999\n',
                     'nan,0,0,1,1,1,1\n','0,0,0,1,1,1,<0.1\n',
                     '0,0,0,1,1,1,1,extra\n']:
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.read(header+rows)

    def test_limits_cancellation_and_schema(self):
        text='x,y,z,dx,dy,dz,grade\n0,0,0,1,1,1,1\n1,0,0,1,1,1,2\n'
        with self.assertRaises(ValueError):self.read(text,maximum=1)
        with self.assertRaises(RuntimeError):self.read(text,cancel=lambda:True)
        with self.assertRaises(ValueError):self.read('x,x,z,dx,dy,dz,grade\n')
        self.read(text)
        with self.assertRaises(ValueError):read_block_csv(self.path,self.mapping,'EPSG:4326','ppm')
        with self.assertRaises(ValueError):read_block_csv(self.path,self.mapping,'EPSG:32648','')

    def test_explicit_column_mapping(self):
        self.path.write_text('E,N,RL,SX,SY,SZ,AU\n5,5,5,10,10,10,1.2\n')
        mapping=dict(zip(KEYS,['E','N','RL','SX','SY','SZ','AU']))
        model,_=read_block_csv(self.path,mapping,'EPSG:32648','g/t')
        self.assertEqual(model['blocks'][0]['grade'],1.2)

    def test_reject_rotation_and_nonmetre_crs(self):
        with self.assertRaises(ValueError):
            self.read('x,y,z,dx,dy,dz,grade,grid_azimuth\n0,0,0,1,1,1,1,45\n')
        self.path.write_text('x,y,z,dx,dy,dz,grade\n0,0,0,1,1,1,1\n')
        with self.assertRaises(ValueError):read_block_csv(self.path,self.mapping,'EPSG:2263','ppm')

    def test_volume_tonnage_cutoff_oracle(self):
        from rainymine.estimation import tonnage_grade
        model,_=self.read('x,y,z,dx,dy,dz,grade\n5,5,5,10,10,10,0\n15,5,5,10,10,10,2\n25,5,5,10,10,10,NULL\n')
        rows=tonnage_grade(model,2.5,[0,1,3])
        self.assertEqual(rows[0]['total_volume_m3'],3000)
        self.assertEqual(rows[0]['unestimated_volume_m3'],1000)
        self.assertEqual(rows[0]['tonnes'],5000)
        self.assertEqual(rows[0]['mean_grade'],1)
        self.assertEqual(rows[1]['tonnes'],2500)
        self.assertEqual(rows[1]['mean_grade'],2)
        self.assertIsNone(rows[2]['mean_grade'])

    def rotated_csv(self,leaves,angles=(37,18,-11)):
        import numpy as np
        from rainymine.spatial import search_basis
        self.geometry={'origin':[500000,5300000,1000],'parent_size':[10,10,10],'angles':list(angles)}
        basis=search_basis(*angles);origin=np.array(self.geometry['origin'])
        import csv
        with self.path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(KEYS)
            for local,dims,grade in leaves:
                writer.writerow(list(origin+np.array(local)@basis.T)+list(dims)+[grade])
        return read_block_csv(self.path,self.mapping,'EPSG:32648','ppm',geometry=self.geometry)

    def test_rotated_subblocks_preserve_geometry_mass_and_save(self):
        import numpy as np
        from rainymine.estimation import tonnage_grade
        from rainymine.spatial import model_basis
        model,report=self.rotated_csv([([2.5,5,5],[5,10,10],1),([7.5,5,5],[5,10,10],3),([15,5,5],[10,10,10],'NULL')])
        self.assertEqual(report['subblocks'],2)
        self.assertEqual(model['bounds'],[500000,5300000,1000,500020,5300010,1010])
        np.testing.assert_allclose((np.array([model['blocks'][0][k] for k in 'xyz'])-model['grid_origin'])@model_basis(model),[2.5,5,5],atol=1e-8)
        self.assertEqual(model['blocks'][0]['parent_id'],'0:0:0')
        self.assertEqual(model['blocks'][2]['parent_id'],'1:0:0')
        self.assertEqual(tonnage_grade(model,2.5,[0])[0]['tonnes'],2500)
        self.assertEqual(tonnage_grade(model,2.5,[0])[0]['mean_grade'],2)
        project=Project();project.workspace['block_model']=model
        target=Path(self.tmp.name)/'rotated.rmine';save_project(target,project)
        self.assertEqual(load_project(target).workspace['block_model'],model)

    def test_subblock_overlap_boundary_and_negative_origin_rejected(self):
        cases=[ [([5,5,5],[10,10,10],1),([2.5,5,5],[5,10,10],1)],
                [([9,5,5],[4,10,10],1)], [([-5,5,5],[10,10,10],1)],
                [([5,5,5],[10,10,10],1),([5,5,5],[10,10,10],2)]]
        for leaves in cases:
            with self.subTest(leaves=leaves),self.assertRaises(ValueError):self.rotated_csv(leaves)

    def test_explicit_skip_metadata_and_consistent_rotation(self):
        self.path.write_text('x,y,z,dx,dy,dz,grade\nN,N,N,N,N,N,N\n0,10,0,10,0,10,CENTRE\n5,5,5,10,10,10,2\n')
        model,report=read_block_csv(self.path,self.mapping,'EPSG:32648','ppm',skip_rows=2)
        self.assertEqual(len(model['blocks']),1);self.assertEqual(report['skipped_metadata_rows'],2)
        with self.assertRaises(ValueError):read_block_csv(self.path,self.mapping,'EPSG:32648','ppm',skip_rows=4)

    def test_imported_rotated_leaves_vtk_geometry_and_ids(self):
        import numpy as np
        from rainymine.scene import Scene
        from tests.test_scene import NoRenderWindow
        from rainymine.spatial import model_basis
        from rainymine.core import demo
        model,_=self.rotated_csv([([2.5,5,5],[5,10,10],1),([7.5,5,5],[5,10,10],2)])
        p=Project();p.workspace['block_model']=model;p.workspace['block_display']='blocks'
        scene=Scene(NoRenderWindow());scene.load(p);poly=scene.sources['blocks']
        self.assertEqual(poly.GetNumberOfCells(),12)
        self.assertEqual(scene.grade_max,2)
        self.assertEqual(scene.actors['blocks'].GetMapper().GetScalarRange(),(0,2))
        self.assertLess(max(abs(x) for x in poly.GetBounds()),20)
        ids=poly.GetCellData().GetArray('block_index')
        self.assertEqual({int(ids.GetValue(i)) for i in range(ids.GetNumberOfTuples())},{0,1})
        pivot=np.array(model['grid_origin']);local=[]
        for i in range(poly.GetNumberOfPoints()):local.append((np.array(poly.GetPoint(i))+scene.origin-pivot)@model_basis(model))
        np.testing.assert_allclose(np.min(local,axis=0),[0,0,0],atol=1e-7)
        np.testing.assert_allclose(np.max(local,axis=0),[10,10,10],atol=1e-7)

    def test_skipped_ragged_metadata_is_serializable(self):
        self.path.write_text('x,y,z,dx,dy,dz,grade\nN,N,N,N,N,N,N,uninterpreted\n5,5,5,10,10,10,2\n')
        model,report=read_block_csv(self.path,self.mapping,'EPSG:32648','ppm',skip_rows=1)
        self.assertEqual(report['metadata_rows_uninterpreted'][0]['extra'],['uninterpreted'])
        import json
        json.dumps(model,sort_keys=True,allow_nan=False)
