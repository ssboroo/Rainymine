import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from rainymine.core import Project
from rainymine.ebmz_report import build_tables, export_pack, plane_blocks, safe_cell


def project(unit='%'):
    p = Project(name='Туршилтын орд', grade_unit=unit)
    p.workspace['block_model'] = {'blocks':[
        dict(x=5,y=5,z=5,dx=10,dy=10,dz=10,grade=1,density=2,domain='D1'),
        dict(x=15,y=5,z=5,dx=10,dy=10,dz=10,grade=3,density=4,domain='D1')], 'grid_angles':[90,0,0]}
    return p


class ReportTests(unittest.TestCase):
    def test_hand_calculated_mass_weighted_metal_and_total(self):
        rows,_ = build_tables(project(), {'cutoff':0})
        r = next(r for r in rows if r['Домэйн']=='D1')
        self.assertEqual(r['Эзлэхүүн м³'], 2000)
        self.assertEqual(r['Хүдэр т'], 6000)
        self.assertAlmostEqual(r['Агуулга %'], 14/6)
        self.assertEqual(r['Металл т'], 140)
        self.assertEqual(next(r for r in rows if r['Домэйн']=='НИЙТ')['Металл т'],140)

    def test_units_and_cutoff(self):
        for unit in ('g/t','ppm'):
            rows,_=build_tables(project(unit),{'cutoff':2})
            r=next(r for r in rows if r['Домэйн']=='D1')
            self.assertEqual(r['Хүдэр т'],4000)
            self.assertAlmostEqual(r['Металл т'],.012)

    def test_missing_density_never_reports_partial_tonnage(self):
        p=project();del p.workspace['block_model']['blocks'][0]['density']
        rows,warnings=build_tables(p,{})
        self.assertIsNone(rows[0]['Хүдэр т'])
        self.assertIsNone(rows[0]['Металл т'])
        rows,_=build_tables(p,{'density':2})
        self.assertEqual(rows[0]['Хүдэр т'],6000)
        self.assertTrue(any('нягтгүй блок: 1' in w for w in warnings))

    def test_plane_boundary_once_and_no_projection(self):
        blocks=project().workspace['block_model']['blocks']
        self.assertEqual(len(plane_blocks(blocks,'x',10)),1)
        self.assertEqual(plane_blocks(blocks,'x',10)[0]['x'],15)
        self.assertEqual(plane_blocks(blocks,'y',20),[])

    def test_invalid_inputs_and_rotated_grid(self):
        for settings in ({'density':-1},{'cutoff':float('nan')},{'cutoff':-1}):
            with self.assertRaises(ValueError):build_tables(project(),settings)
        p=project();p.workspace['block_model']['grid_angles']=[45,0,0]
        with self.assertRaises(ValueError):build_tables(p,{})
        p=project();p.workspace['block_model']['blocks'][0]['grade']=float('inf')
        with self.assertRaises(ValueError):build_tables(p,{})

    def test_formula_labels_escaped(self):
        self.assertEqual(safe_cell(' =1+1'),"' =1+1")
        self.assertEqual(safe_cell(2.5),2.5)

    def test_export_and_atomic_failure(self):
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'pack'
            export_pack(project(),{},target)
            manifest=json.loads((target/'manifest.json').read_text())
            self.assertEqual(manifest['status'],'DRAFT_REVIEW_REQUIRED')
            self.assertEqual(len(manifest['files_sha256']),9)
            for name,digest in manifest['files_sha256'].items():
                self.assertEqual(hashlib.sha256((target/name).read_bytes()).hexdigest(),digest)
            self.assertTrue((target/'sections-A3.pdf').read_bytes().startswith(b'%PDF'))
            self.assertTrue((target/'report.pdf').read_bytes().startswith(b'%PDF'))
            with self.assertRaises(ValueError):export_pack(project(),{},target)
            with self.assertRaises(ValueError):export_pack(project(),{'scale':1},Path(folder)/'bad')
            self.assertFalse((Path(folder)/'bad').exists())
            self.assertFalse(list(Path(folder).glob('.ebmz-*')))
            with self.assertRaises(InterruptedError):export_pack(project(),{},Path(folder)/'cancelled',lambda:True)
            self.assertFalse((Path(folder)/'cancelled').exists())

    def test_one_click_runs_real_export_in_background(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QEventLoop,QTimer
        from unittest.mock import patch
        from tests.test_workspace import WorkspaceLayoutTests
        app=QApplication.instance() or QApplication([])
        window=WorkspaceLayoutTests.make_window(self)
        with tempfile.TemporaryDirectory() as folder:
            window.project.workspace['ebmz_report']={'output_root':folder,'cutoff':0,'scale':'auto'}
            observed=[]
            with patch('rainymine.ebmz_ui.QMessageBox.information') as message, patch('rainymine.background.QMessageBox.warning') as failure:
                window.ebmz_export()
                self.assertEqual(len(window._engineering_tasks),1)
                loop=QEventLoop();window._engineering_tasks[0].worker.finished.connect(loop.quit)
                QTimer.singleShot(0,lambda:observed.append(True));QTimer.singleShot(10000,loop.quit);loop.exec();app.processEvents()
                self.assertTrue(observed)
                failure.assert_not_called();message.assert_called_once()
            outputs=list(Path(folder).glob('RAINYMINE-EBMZ-*'))
            self.assertEqual(len(outputs),1)
            self.assertTrue((outputs[0]/'sections-A3.pdf').exists())
            self.assertFalse(window._engineering_tasks)
        window.dirty=False;window.close()


if __name__=='__main__':unittest.main()
