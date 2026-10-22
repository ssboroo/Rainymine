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
