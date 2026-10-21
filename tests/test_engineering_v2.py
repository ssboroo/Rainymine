import math
import tempfile
from pathlib import Path
from copy import deepcopy
import unittest
import numpy as np
from rainymine.engineering import rtc_buffer,morton_codes,oriented_core,density_composites
from rainymine.core import displacement,direction
from rainymine.estimation import Estimator,gamma_model,make_blocks
from rainymine.block_store import write_block_parquet,read_block_model,scan_block_batches
from rainymine.validation import validate_tables,parse_assay_tag


class PrecisionTests(unittest.TestCase):
    def test_utm_rtc_preserves_millimetres(self):
        world=np.array([[500000,5300000,1400],[500000.001,5300000.001,1400.001]])
        self.assertEqual(world.astype(np.float32)[1,1],world.astype(np.float32)[0,1])
        local=rtc_buffer(world,world[0]);self.assertEqual(local.dtype,np.float32)
        np.testing.assert_allclose(local[1],[.001]*3,atol=1e-9)
        np.testing.assert_allclose(local.astype(float)+world[0],world,atol=1e-8,rtol=0)
    def test_morton_axes_and_21_bit_boundaries(self):
        np.testing.assert_array_equal(morton_codes([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,1,1]]),[0,1,2,4,7])
        self.assertEqual(int(morton_codes([[2**21-1]*3])[0]),2**63-1)
        for bad in ([[-1,0,0]],[[2**21,0,0]],[[.5,0,0]]):
            with self.assertRaises(ValueError):morton_codes(bad)
    def test_nearly_parallel_curvature(self):
        result=displacement(30,direction(0,-60),direction(.000001,-60))
        self.assertAlmostEqual(math.dist([0,0,0],result),30,places=10)
    def test_oriented_core_analytic_and_hemisphere(self):
        self.assertAlmostEqual(oriented_core(0,-90,0,0)['dip'],90)
        self.assertAlmostEqual(oriented_core(0,-90,90,0)['dip'],0)
        self.assertIsNone(oriented_core(0,-90,90,0)['dip_direction'])
        a=oriented_core(0,-90,45,0);b=oriented_core(90,-90,45,0)
        self.assertAlmostEqual((b['dip_direction']-a['dip_direction'])%360,90)
        self.assertGreaterEqual(a['normal'][2],0)
    def test_density_weight_and_gap(self):
        rows=density_composites([{'from_m':0,'to_m':1,'grade':1,'density':2},
                                {'from_m':2,'to_m':3,'grade':3,'density':4}],3)
        self.assertAlmostEqual(rows[0]['grade'],14/6);self.assertAlmostEqual(rows[0]['coverage'],2/3)


class KrigingDiagnostics(unittest.TestCase):
    def test_covariance_diagnostics_analytic(self):
        samples=[{'hole_id':'A','xyz':[-1,0,0],'grade':1}, {'hole_id':'B','xyz':[1,0,0],'grade':3}]
        for family in ('spherical','exponential','gaussian'):
            result=Estimator(samples,{'method':'kriging','minimum':2,'neighbors':2,'range_m':10,'variogram_model':family}).predict([0,0,0])
            g1=float(gamma_model(1,0,1,10,family));g2=float(gamma_model(2,0,1,10,family))
            var=2*g1-.5*g2
            self.assertAlmostEqual(result['variance'],var)
            self.assertAlmostEqual(result['kriging_efficiency'],1-var)
            self.assertAlmostEqual(result['slope_of_regression'],(1-g1)/(1-.5*g2))
        self.assertEqual(float(gamma_model(0,.1,1,10,'exponential')),0)
        self.assertAlmostEqual(float(gamma_model(10,0,1,10,'gaussian')),1-math.exp(-3))


class ParquetStoreTests(unittest.TestCase):
    def model(self):
        blocks=make_blocks([500000,5300000,1400,500030,5300020,1410],[10,10,10])
        for i,b in enumerate(blocks):b.update(grade=None if i==2 else i*.25,variance=.1,block_id=str(i),domain='A')
        return {'blocks':blocks,'bounds':[500000,5300000,1400,500030,5300020,1410],
                'grid_origin':[500000,5300000,1400],'grid_angles':[90,0,0],'size':[10,10,10]}
    def test_roundtrip_nulls_ids_rotation_and_filters(self):
        import pyarrow.parquet as pq
        model=self.model();before=deepcopy(model)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Монгол.parquet';write_block_parquet(path,model,'EPSG:32648','g/t')
            restored,meta=read_block_model(path)
            self.assertEqual(restored,model);self.assertEqual(meta['grade_unit'],'g/t')
            table=pq.read_table(path);self.assertEqual(str(table.schema.field('morton_id').type),'uint64')
            self.assertEqual(pq.ParquetFile(path).metadata.row_group(0).column(0).compression,'ZSTD')
            codes=table['morton_id'].to_numpy();self.assertTrue(np.all(codes[:-1]<=codes[1:]))
            batches=list(scan_block_batches(path,[500000,5300000,1400,500010,5300020,1410],columns=['row_id','grade'],batch_size=1))
            self.assertEqual(sum(b.num_rows for b in batches),2)
            self.assertTrue(all(b.num_rows<=1 for b in batches))
            with self.assertRaises(ValueError):read_block_model(path,maximum=1)
        self.assertEqual(model,before)
    def test_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.parquet';path.write_bytes(b'preserve')
            model=self.model();model['blocks'][0]['dx']=-1
            with self.assertRaises(ValueError):write_block_parquet(path,model)
            self.assertEqual(path.read_bytes(),b'preserve')


class ValidationTests(unittest.TestCase):
    def test_all_ten_rules_and_no_mutation(self):
        collars=[{'hole_id':str(i),'x':0,'y':0,'z':0,'depth':100} for i in range(20)]
        collars.append({'hole_id':'out','x':10000,'y':0,'z':0,'depth':100})
        tables={'collars':collars,'surveys':[{'hole_id':'0','depth':10,'azimuth':0,'dip':0}, {'hole_id':'0','depth':20,'azimuth':0,'dip':-90}],
                'assays':[{'hole_id':'missing','from_m':0,'to_m':1,'grade':'NS'},
                          {'hole_id':'0','from_m':0,'to_m':10,'grade':'<0.01','sample_id':'S'},
                          {'hole_id':'0','from_m':5,'to_m':8,'grade':1,'sample_id':'S'},
                          {'hole_id':'0','from_m':20,'to_m':19,'grade':1},
                          {'hole_id':'0','from_m':30,'to_m':101,'grade':1}]}
        before=deepcopy(tables);issues=validate_tables(tables)
        self.assertEqual({r['code'] for r in issues},{f'VAL-{i:02}' for i in range(1,11)})
        self.assertEqual(tables,before)
    def test_nested_overlap_and_explicit_detection_policy(self):
        t={'collars':[{'hole_id':'A','x':0,'y':0,'z':0,'depth':100}],
           'assays':[{'hole_id':'A','from_m':0,'to_m':50,'grade':1}, {'hole_id':'A','from_m':1,'to_m':2,'grade':1}, {'hole_id':'A','from_m':3,'to_m':4,'grade':1}]}
        self.assertEqual(sum(r['code']=='VAL-03' for r in validate_tables(t)),2)
        self.assertIsNone(parse_assay_tag('<0.01')['value'])
        self.assertEqual(parse_assay_tag('<0.01','half_detection')['value'],.005)
        with self.assertRaises(ValueError):parse_assay_tag('garbage')
        self.assertTrue(any(r['code']=='VAL-10' for r in validate_tables(t,elevation=lambda x,y:30)))

class ExposedFaceTests(unittest.TestCase):
    def test_surface_extraction_and_real_cell_ids(self):
        from rainymine.engineering import exposed_block_faces
        from rainymine.core import Project
        from rainymine.scene import Scene
        from tests.test_scene import NoRenderWindow
        blocks=make_blocks([500000,5300000,1400,500030,5300030,1430],[10,10,10])
        for b in blocks:b['grade']=1
        mask=exposed_block_faces(blocks)
        self.assertEqual(sum(map(len,mask)),54)
        project=Project(workspace={'block_model':{'blocks':blocks,'bounds':[500000,5300000,1400,500030,5300030,1430]},'block_display':'exposed'})
        scene=Scene(NoRenderWindow());scene.load(project);poly=scene.sources['blocks']
        self.assertEqual(poly.GetNumberOfCells(),54)
        self.assertGreater(scene.origin[1],5e6)
        self.assertLess(max(map(abs,poly.GetBounds())),100)
        ids=poly.GetCellData().GetArray('block_index')
        self.assertNotIn(13,{int(ids.GetValue(i)) for i in range(ids.GetNumberOfValues())})
        blocks[0]['subblock_level']=1
        with self.assertRaises(ValueError):exposed_block_faces(blocks)

class SixTableSchemaTests(unittest.TestCase):
    def test_structure_geotech_roundtrip_legacy_and_upward_holes(self):
        from rainymine.core import Project,Collar,Structure,Geotech,Trajectory
        p=Project(collars=[Collar('UP',500000,5300000,1400,100,0,90)],
                  structure=[Structure('UP',20,45,180)],geotech=[Geotech('UP',0,10,80,90,100,10)])
        p.validate();self.assertEqual(p.to_dict()['version'],3)
        self.assertEqual(Project.from_dict(p.to_dict()),p)
        self.assertAlmostEqual(Trajectory(p.collars[0],[]).at(100)[2],1500)
        old=p.to_dict();old['version']=2;old.pop('structure');old.pop('geotech')
        self.assertEqual(Project.from_dict(old).structure,[])
        p.geotech=[Geotech('UP',0,10,99,50)]
        with self.assertRaises(ValueError):p.validate()
    def test_new_csv_schemas_are_real_typed_rows(self):
        from rainymine.data_tools import mapped_import,rows_to_values,SCHEMAS
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'structure.csv';path.write_text('hole_id,depth,alpha,beta,feature_type\nA,10,45,20,FAULT\n')
            rows,report=mapped_import(path,'structure',{k:k for k in SCHEMAS['structure']})
            self.assertEqual(rows_to_values('structure',rows)[0].feature_type,'FAULT')
