import itertools
import tempfile
import unittest
from pathlib import Path
import numpy as np
from rainymine.core import Project, Collar, save_project, load_project
from rainymine.implicit import implicit_surface
from rainymine.optimization import maximum_closure, economic_pit, pit_mesh
from rainymine.estimation import make_blocks
from rainymine.geometry import mesh_report
from rainymine.exchange import xlsx_to_csv, read_stl, write_stl, database_snapshot, VIEW_NAMES


class ModellingTests(unittest.TestCase):
    def test_rbf_symmetric_plane_large_coordinates(self):
        samples=[{'xyz':[500000+x,5300000+y,100+z],'grade':float(x)}
                 for x in (0,10) for y in (0,10) for z in (0,10)]
        mesh,meta=implicit_surface(samples,[500000,5300000,100,500010,5300010,110],5,11)
        self.assertTrue(mesh['faces'])
        self.assertLess(max(abs(p[0]-500005) for p in mesh['vertices']),1e-4)
        self.assertFalse(meta['geological_review'])
        self.assertGreater(meta['mesh_report']['open_edges'],0)
        self.assertEqual(meta['mesh_report']['degenerate_faces'],0)
        p=Project();p.workspace['meshes']=[mesh]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'RBF.rmine';save_project(path,p);self.assertEqual(load_project(path).workspace['meshes'],[mesh])
            write_stl(Path(d)/'RBF.stl',mesh)
    def test_rbf_rejects_duplicates_cutoff_and_resolution(self):
        samples=[{'xyz':[0,0,0],'grade':0}]*4
        with self.assertRaises(ValueError):implicit_surface(samples,[0,0,0,10,10,10],.5)
        with self.assertRaises(ValueError):implicit_surface(samples,[0,0,0,10,10,10],.5,100)
    def test_maximum_closure_against_exhaustive_enumeration(self):
        rng=np.random.default_rng(56)
        for _ in range(12):
            values=rng.integers(-20,21,7).tolist();edges=[(i,j) for i in range(7) for j in range(i+1,7) if rng.random()<.3]
            reference=max(sum(v*b for v,b in zip(values,bits)) for bits in itertools.product((0,1),repeat=7)
                          if all(bits[c]<=bits[p] for c,p in edges))
            result=maximum_closure(values,edges)
            self.assertAlmostEqual(result['net_value'],reference)
            self.assertTrue(result['optimal'])
    def model(self):
        blocks=make_blocks([0,0,0,10,10,20],[10,10,10])
        blocks[0]['grade']=10;blocks[1]['grade']=0
        return {'blocks':blocks}
    def test_pit_must_pay_stripping_and_empty_optimum(self):
        model=self.model();r=economic_pit(model,1,1,1,2,1)
        self.assertEqual(r['selected_indices'],[0,1])
        self.assertAlmostEqual(r['net_value'],5000)
        mesh=pit_mesh(model,r['selected_indices']);report=mesh_report(mesh)
        self.assertEqual(report['open_edges'],0)
        self.assertAlmostEqual(report['signed_volume_m3'],2000)
        self.assertEqual(economic_pit(model,1,1,1,20,1)['selected_indices'],[])
    def test_pit_rejects_missing_grade_subblocks_and_geometry(self):
        model=self.model();model['blocks'][0]['grade']=None
        with self.assertRaises(ValueError):economic_pit(model,1,1,1,2,1)
        model=self.model();model['blocks'][1]['dz']=2
        with self.assertRaises(ValueError):economic_pit(model,1,1,1,2,1)
        model=self.model();model['blocks'][1]['x']=1
        with self.assertRaises(ValueError):economic_pit(model,1,1,1,2,1)
    def test_lateral_slope_precedence(self):
        blocks=make_blocks([0,0,0,30,30,20],[10,10,10])
        for b in blocks:b['grade']=100 if (b['i'],b['j'],b['k'])==(1,1,0) else 0
        r=economic_pit({'blocks':blocks},1,1,1,1,0)
        selected=[blocks[i] for i in r['selected_indices']]
        self.assertEqual(len(selected),10)
        self.assertEqual(sum(b['k']==1 for b in selected),9)


class ExchangeTests(unittest.TestCase):
    def test_excel_values_and_formula_rejection(self):
        from openpyxl import Workbook
        from rainymine.data_tools import mapped_import,SCHEMAS
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'data.xlsx';target=Path(d)/'data.csv';wb=Workbook();ws=wb.active;ws.title='Амсар'
            ws.append(list(SCHEMAS['collars']));ws.append(['MN-01',500000,5300000,1000,10,0,-90]);wb.save(source)
            xlsx_to_csv(source,target,'Амсар');rows,report=mapped_import(target,'collars',{k:k for k in SCHEMAS['collars']})
            self.assertEqual(rows[0]['hole_id'],'MN-01');self.assertEqual(report['rejected'],0)
            ws['B2']='=1+2';wb.save(source)
            with self.assertRaises(ValueError):xlsx_to_csv(source,target,'Амсар')
    def test_corrupt_excel_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.xlsx';path.write_bytes(b'not a spreadsheet')
            with self.assertRaises(ValueError):xlsx_to_csv(path,Path(d)/'out.csv','Sheet1')
    def test_ascii_stl_double_precision_roundtrip(self):
        mesh={'vertices':[[500000.123456,5300000,100],[500010,5300000,100],[500000,5300010,100]],'faces':[[0,1,2]]}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.stl';write_stl(path,mesh);read=read_stl(path)
            self.assertEqual(read['vertices'],mesh['vertices']);self.assertEqual(read['faces'],mesh['faces'])
            path.write_bytes(b'not STL')
            with self.assertRaises(ValueError):read_stl(path)
    def test_binary_stl(self):
        import struct
        record=struct.pack('<12fH',0,0,1,0,0,0,10,0,0,0,10,0,0)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'binary.stl';path.write_bytes(b'\0'*80+struct.pack('<I',1)+record)
            self.assertEqual(len(read_stl(path)['faces']),1)


class FakeConnection:
    def __init__(self,rows):self.rows=rows;self.sql=[];self.rolled_back=False;self.closed=False
    def cursor(self):return self
    def execute(self,sql):self.sql.append(sql);return self
    def fetchmany(self,n):
        return next(rows for name,rows in self.rows.items() if '['+name+']' in self.sql[-1])
    def rollback(self):self.rolled_back=True
    def close(self):self.closed=True


class DatabaseTests(unittest.TestCase):
    def rows(self):return {'RainymineCollars':[('A',1,2,3,10,0,-90)],'RainymineSurveys':[],
                          'RainymineAssays':[('A',0,10,2)],'RainymineLithology':[('A',0,10,'Хүдэр')]}
    def test_snapshot_is_atomic_and_read_only(self):
        old=Project(collars=[Collar('OLD',0,0,0,10)])
        connection=FakeConnection(self.rows())
        def connect(string,**kwargs):
            self.assertEqual(string,'DSN=Geobank;Trusted_Connection=yes;');return connection
        new=database_snapshot(old,'Geobank',connector=connect)
        self.assertEqual(new.collars[0].hole_id,'A');self.assertEqual(old.collars[0].hole_id,'OLD')
        self.assertTrue(connection.rolled_back and connection.closed)
        self.assertTrue(all(s.startswith(('SELECT ','SET TRANSACTION ','BEGIN TRANSACTION')) for s in connection.sql))
        self.assertNotIn('Geobank',str(new.workspace))
    def test_validation_failure_closes_connection_and_preserves_project(self):
        old=Project();rows=self.rows();rows['RainymineAssays']=[('UNKNOWN',0,10,2)];connection=FakeConnection(rows)
        with self.assertRaises(ValueError):database_snapshot(old,'Geobank',connector=lambda *a,**kw:connection)
        self.assertEqual(old.collars,[]);self.assertTrue(connection.rolled_back and connection.closed)
    def test_connection_input_and_error_do_not_leak_secrets(self):
        with self.assertRaises(ValueError):database_snapshot(Project(),'DSN;PWD=secret')
        def fail(*a,**kw):raise RuntimeError('PWD=secret')
        with self.assertRaises(ValueError) as cm:database_snapshot(Project(),'Geobank',connector=fail)
        self.assertNotIn('secret',str(cm.exception))
