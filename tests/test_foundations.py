import csv
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from rainymine.core import Project,demo,save_project,load_project
from rainymine.recovery import RecoveryStore
from rainymine.data_tools import History
from rainymine.disk_model import DiskModel
from rainymine.benchmark import compare_reference,write_comparison_report
from rainymine.acceptance_tools import restore_planar_slip,classify_stratigraphy,estimate_stratigraphy,stockpile_ledger,segment_haul


class RecoveryTests(unittest.TestCase):
    def test_unsaved_unicode_project_survives_restart_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'original.rmine';source.write_text('unchanged')
            store=RecoveryStore(root/'recovery','first');project=demo();project.name='Хадгалаагүй төсөл'
            path=store.write(project,source)
            restarted=RecoveryStore(root/'recovery','second');candidate=restarted.candidates()[0]
            restored,meta=restarted.read(candidate['path'])
            self.assertEqual(restored.to_dict(),project.to_dict());self.assertEqual(meta['original_path'],str(source));self.assertEqual(source.read_text(),'unchanged')
            store.clear();self.assertFalse(path.exists())
    def test_failed_snapshot_keeps_previous_and_corruption_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RecoveryStore(directory,'one');path=store.write(demo());before=path.read_bytes()
            with patch('rainymine.recovery.atomic_write',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):store.write(Project())
            self.assertEqual(path.read_bytes(),before)
            bad=Path(directory)/'bad.recovery';bad.write_text('{broken')
            self.assertEqual(len(RecoveryStore(directory,'two').candidates()),1);self.assertTrue(bad.exists())
            with self.assertRaises(ValueError):store.read(Path(directory)/'other.txt')
    def test_legacy_project_versions_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            for version in (1,2,3):
                data=demo().to_dict();data['version']=version
                if version==1:
                    for key in ('lithology','workspace','structure','geotech','crs_code'):data.pop(key,None)
                path=Path(directory)/f'v{version}.rmine';path.write_text(json.dumps(data))
                project=load_project(path);save_project(path,project);self.assertEqual(load_project(path).to_dict(),project.to_dict())


class HistoryBudget(unittest.TestCase):
    def test_budget_roundtrip_and_branch(self):
        a=demo();b=deepcopy(a);b.name='edited';history=History(max_bytes=1000000)
        history.apply(a,b,'edit');self.assertIsInstance(history.undo_items[0][1],bytes)
        self.assertEqual(history.undo(b).to_dict(),a.to_dict());self.assertEqual(history.redo(a).to_dict(),b.to_dict())
        tiny=History(max_bytes=1);tiny.apply(a,b,'edit');self.assertEqual(tiny.retained_bytes,0);self.assertIs(tiny.undo(b),b)
    def test_redo_discarded_on_branch(self):
        a=Project();b=Project(name='B');c=Project(name='C');h=History()
        h.apply(a,b,'b');h.undo(b);h.apply(a,c,'c');self.assertIs(h.redo(c),c)


class DiskModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'model.rmdb'
        DiskModel.create(self.path,[500000,5300000,100],[4,2,2],[10,10,10],'EPSG:32648','%',2.7)
    def test_reopen_edit_persistent_undo_redo_and_branch(self):
        with DiskModel(self.path) as store:
            store.edit(0,2.,2.5,'ore');self.assertEqual(store.totals()['contained_metal_tonnes'],50.)
        with DiskModel(self.path) as store:
            self.assertTrue(store.undo());self.assertEqual(store.totals()['unestimated_blocks'],16)
            self.assertTrue(store.undo(True));store.undo();store.edit(1,1.,2.7,None);self.assertFalse(store.undo(True))
    def test_idw_symmetry_and_export_all_rows(self):
        with DiskModel(self.path) as store:
            result=store.estimate_idw([[500005,5300005,105,1],[500035,5300015,115,3]],100,2,1)
            self.assertEqual(result['estimated'],16);self.assertAlmostEqual(store.totals()['contained_metal_tonnes'],16*1000*2.7*.02)
            output=Path(self.temp.name)/'all.csv';store.export_csv(output)
            with output.open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),16);self.assertEqual(float(rows[0]['grade']),1.)
            self.assertTrue(store.undo());self.assertEqual(store.totals()['unestimated_blocks'],16)
            self.assertTrue(store.undo(True));self.assertEqual(store.totals()['unestimated_blocks'],0)
            from rainymine.large_view import preview_polydata
            payload=store.preview(5);poly,_=preview_polydata(payload);self.assertLessEqual(poly.GetNumberOfPoints(),5)
    def test_cancelled_estimation_and_export_are_atomic(self):
        with DiskModel(self.path) as store:
            store.edit(0,2,2.7,'old');before=store.totals()
            with self.assertRaises(RuntimeError):store.estimate_idw([[500005,5300005,105,1]],100,1,1,cancel=lambda:True)
            self.assertEqual(store.totals(),before);self.assertTrue(store.undo());self.assertEqual(store.totals()['unestimated_blocks'],16)
            output=Path(self.temp.name)/'old.csv';output.write_text('old')
            with self.assertRaises(RuntimeError):store.export_csv(output,cancel=lambda:True)
            self.assertEqual(output.read_text(),'old')
    def test_cancelled_grid_keeps_previous_store(self):
        before=self.path.read_bytes()
        with self.assertRaises(RuntimeError):DiskModel.create(self.path,[0]*3,[2]*3,[1]*3,'EPSG:32648','%',cancel=lambda:True)
        self.assertEqual(self.path.read_bytes(),before)
    def test_bundle_metadata_hash_and_null_contract(self):
        import zipfile,hashlib
        output=Path(self.temp.name)/'blocks.zip'
        with DiskModel(self.path) as store:
            store.edit(0,0.,2.7,'');store.export_bundle(output)
        with zipfile.ZipFile(output) as archive:
            manifest=json.loads(archive.read('manifest.json'));raw=archive.read('blocks.csv')
            self.assertEqual(manifest['sha256']['blocks.csv'],hashlib.sha256(raw).hexdigest());self.assertEqual(manifest['grade_unit'],'%')
            rows=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()));self.assertEqual(rows[0]['grade'],'0.0');self.assertEqual(rows[1]['grade'],'');self.assertEqual(rows[0]['domain'],'')
    def test_invalid_samples_units_and_density_rejected(self):
        with DiskModel(self.path) as store:
            for samples in ([[0,0,0,1],[0,0,0,2]],[[0,0,0,101]]):
                with self.assertRaises(ValueError):store.estimate_idw(samples)
            with self.assertRaises(ValueError):store.edit(0,1,-1,None)
            with self.assertRaises(ValueError):store.edit(100,1,2.7,None)
        with self.assertRaises(ValueError):DiskModel.create(self.path,[0]*3,[2]*3,[1]*3,'EPSG:4326','%')


class ExpandedReference(unittest.TestCase):
    def test_geometry_density_domain_and_metal_mismatch(self):
        model={'blocks':[dict(x=1,y=2,z=3,dx=10,dy=10,dz=10,grade=2,density=2.7,domain='ore')]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reference.csv';path.write_text('x,y,z,grade,dx,dy,dz,density,domain\n1,2,3,2,10,10,10,2.7,ore\n')
            result=compare_reference(model,path,grade_unit='%');self.assertTrue(result['numerical_pass']);self.assertEqual(result['totals']['model']['contained_metal_tonnes'],54.)
            model['blocks'][0]['dx']=20
            result=compare_reference(model,path,grade_unit='%');self.assertFalse(result['numerical_pass']);self.assertEqual(result['total_differences']['tonnes'],2700.)
            output=Path(directory)/'report.html';result['source_name']='<script>bad</script>';write_comparison_report(output,result)
            self.assertNotIn('<script>',output.read_text());self.assertIn('&lt;script&gt;',output.read_text())
    def test_null_is_not_zero_and_missing_geometry_not_invented(self):
        model={'blocks':[dict(x=1,y=2,z=3,grade=None)]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'r.csv';path.write_text('x,y,z,grade\n1,2,3,\n')
            result=compare_reference(model,path);self.assertTrue(result['numerical_pass']);self.assertIsNone(result['totals']['model']['tonnes'])
            path.write_text('x,y,z,grade\n1,2,3,0\n');self.assertFalse(compare_reference(model,path)['numerical_pass'])


class AnalyticEngineering(unittest.TestCase):
    def test_planar_shear_and_layer_classification(self):
        faults=[{'point':[0,0,0],'normal':[1,0,0],'slip':[0,0,10]}]
        np.testing.assert_allclose(restore_planar_slip([[-1,0,15],[1,0,25]],faults),[[-1,0,15],[1,0,15]])
        model={'blocks':[{'x':-1,'y':0,'z':15,'grade':1},{'x':1,'y':0,'z':25,'grade':2}],'run_sha256':'old'}
        result,report=classify_stratigraphy(model,[0,0,1],[0,0,0],[20],['lower','upper'],faults)
        self.assertEqual([b['domain'] for b in result['blocks']],['lower','lower']);self.assertTrue(all(b['grade'] is None for b in result['blocks']));self.assertNotIn('run_sha256',result);self.assertEqual(model['blocks'][0]['grade'],1)
        with self.assertRaises(ValueError):restore_planar_slip([[1,0,0]],[dict(faults[0],slip=[1,0,0])])
        with self.assertRaises(ValueError):classify_stratigraphy(model,[0,0,1],[0,0,0],[20,10],['a','b','c'])
    def test_layer_estimation_does_not_mix_adjacent_layers(self):
        from rainymine.core import Collar,Assay
        project=Project(collars=[Collar('lower',0,0,10,5),Collar('upper',0,0,30,5)],assays=[Assay('lower',0,5,1),Assay('upper',0,5,9)])
        model={'blocks':[dict(x=0,y=0,z=7.5,dx=1,dy=1,dz=1),dict(x=0,y=0,z=27.5,dx=1,dy=1,dz=1)]}
        classified,_=classify_stratigraphy(model,[0,0,1],[0,0,0],[20],['lower','upper'])
        result=estimate_stratigraphy(project,classified,dict(method='idw',radii=[100]*3,minimum=1,neighbors=2))
        self.assertEqual([b['grade'] for b in result['blocks']],[1,9]);self.assertEqual(len(result['run_sha256']),64)
        self.assertTrue(all(b.get('grade') is None for b in classified['blocks']))
        with self.assertRaises(RuntimeError):estimate_stratigraphy(project,classified,dict(minimum=1),cancel=lambda:True)
    def test_stockpile_perfect_mixing_and_conservation(self):
        rows=[dict(period=1,pile='A',received_t=100,received_grade=1,reclaimed_t=0,capacity_t=300),dict(period=2,pile='A',received_t=100,received_grade=3,reclaimed_t=50,capacity_t=300)]
        result=stockpile_ledger(rows,'%',100,200)
        self.assertEqual(result['closing_piles']['A']['tonnes'],150);self.assertEqual(result['closing_piles']['A']['contained_metal_t'],3);self.assertEqual(result['rows'][1]['feed_grade'],2)
        self.assertAlmostEqual(result['tonnage_balance_error'],0);self.assertAlmostEqual(result['metal_balance_error_t'],0)
        with self.assertRaises(ValueError):stockpile_ledger(rows,'%',40,200)
        with self.assertRaises(ValueError):stockpile_ledger([dict(rows[0],reclaimed_t=101)],'%',200,300)
        with self.assertRaises(ValueError):stockpile_ledger([dict(rows[0],capacity_t=90)],'%',200,300)
        with self.assertRaises(ValueError):stockpile_ledger([rows[0],rows[0]],'%',200,300)
    def test_signed_gradient_changes_return_speed(self):
        bands=[dict(min_gradient=-10,max_gradient=0,loaded_kmh=30,empty_kmh=40),dict(min_gradient=0,max_gradient=10,loaded_kmh=10,empty_kmh=20)]
        result=segment_haul([[0,0,0],[1000,0,50]],bands,90,2,8,.8,3,2,1)
        length=(1000**2+50**2)**.5/1000
        self.assertAlmostEqual(result['cycle_minutes'],length/10*60+length/40*60+6)
        with self.assertRaises(ValueError):segment_haul([[0,0,0],[1000,0,200]],bands,90,2,8,.8,3,2,1)


class ReleaseReadiness(unittest.TestCase):
    def test_unconfigured_release_fails_production_preflight(self):
        from scripts.check_release_readiness import check
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'release').mkdir();(root/'assets').mkdir()
            (root/'release/config.json').write_text('{}');(root/'assets/license-public-keys.json').write_text('{}')
            result=check(root);self.assertFalse(result['production_ready']);self.assertTrue(result['blockers'])


class FoundationUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def window(self):
        from tests.test_workspace import WorkspaceLayoutTests
        return WorkspaceLayoutTests.make_window(self)
    def test_unsaved_backup_restore_and_successful_save_clears_own_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            window=self.window();window.recovery=RecoveryStore(directory,'ui');window.path=None;window.project.name='Хадгалаагүй';window.dirty=True;window.backup()
            old=RecoveryStore(directory,'old');old.write(Project(name='Restored'))
            with patch('rainymine.ui.QInputDialog.getItem',side_effect=lambda *args:(args[3][0],True)),patch.object(window,'may_discard',return_value=True):window.recover_project()
            self.assertEqual(window.project.name,'Restored');self.assertIsNone(window.path);self.assertTrue(window.dirty)
            destination=Path(directory)/'saved.rmine'
            with patch('rainymine.ui.QFileDialog.getSaveFileName',return_value=(str(destination),'*.rmine')):self.assertTrue(window.save())
            self.assertFalse(window.recovery.path.exists());self.assertEqual(load_project(destination).name,'Restored');self.assertTrue(old.path.exists())
    def test_native_disk_commands_and_new_labels_are_reachable(self):
        from PySide6.QtGui import QAction
        from rainymine.i18n import tr
        window=self.window();texts=[a.text() for a in window.findChildren(QAction)]
        self.assertIn('Том блок сан үүсгэх…',texts);self.assertIn('Давхаргаар тусгаарласан IDW үнэлгээ…',texts)
        window.set_language('en',persist=False);self.assertEqual(tr('Том блок сан үүсгэх…'),'Create large block store…')
        window.set_language('mn',persist=False)
