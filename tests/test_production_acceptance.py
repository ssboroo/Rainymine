import csv
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from rainymine.benchmark import compare_block_geometry
from rainymine.schedule_audit import audit_blend_schedule
from rainymine.advanced_estimation import blend_schedule


class GeometryAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'external.csv'
        self.blocks=[dict(x=500000,y=5300000,z=1000,dx=5,dy=10,dz=10,grade=0),dict(x=500005,y=5300000,z=1000,dx=5,dy=10,dz=10,grade=None)]
        self.model={'blocks':self.blocks,'grid_angles':[37,18,-11]}
        self.write(self.blocks)

    def write(self,blocks):
        with self.path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['x','y','z','dx','dy','dz','grade']);writer.writeheader();writer.writerows(blocks)

    def test_complete_geometry_null_and_volume(self):
        report=compare_block_geometry(self.model,self.path,[37,18,-11])
        self.assertTrue(report['numerical_pass']);self.assertEqual(report['reference_volume_m3'],1000)
        self.assertFalse(report['independent_review_verified'])
        self.assertFalse(compare_block_geometry(self.model,self.path,[90,0,0])['numerical_pass'])

    def test_same_centres_wrong_size_and_null_zero_fail(self):
        rows=deepcopy(self.blocks);rows[0]['dx']=6;self.write(rows)
        self.assertFalse(compare_block_geometry(self.model,self.path,[37,18,-11])['numerical_pass'])
        rows=deepcopy(self.blocks);rows[1]['grade']=0;self.write(rows)
        self.assertFalse(compare_block_geometry(self.model,self.path,[37,18,-11])['numerical_pass'])

    def test_coverage_duplicates_and_cancel(self):
        self.write(self.blocks[:1]);self.assertFalse(compare_block_geometry(self.model,self.path,[37,18,-11])['complete_coverage'])
        self.write([self.blocks[0],self.blocks[0]])
        with self.assertRaises(ValueError):compare_block_geometry(self.model,self.path,[37,18,-11])
        with self.assertRaises(RuntimeError):compare_block_geometry(self.model,self.path,[37,18,-11],cancel=lambda:True)


class ScheduleAudit(unittest.TestCase):
    def setUp(self):
        self.tasks=[{'id':'waste','tonnes':10,'process_tonnes':0,'grade':0,'value':-1},
                    {'id':'ore','tonnes':10,'process_tonnes':10,'grade':2,'value':100,'predecessors':['waste']}]
        self.rows=[{**self.tasks[0],'period':1},{**self.tasks[1],'period':2}]

    def audit(self,rows,**changes):
        params=dict(mining_capacity=10,processing_capacity=10,periods=2,minimum_grade=1,maximum_grade=3,discount=.1)
        params.update(changes)
        return audit_blend_schedule(self.tasks,rows,**params)

    def test_valid_and_discount(self):
        report=self.audit(self.rows);self.assertTrue(report['passed'])
        self.assertAlmostEqual(report['npv'],-1+100/1.1)
        self.assertIsNone(report['periods'][0]['feed_grade'])
        self.assertFalse(report['independent_engineering_review'])

    def test_reject_violations(self):
        cases=[]
        rows=deepcopy(self.rows);rows[1]['period']=1;cases.append((rows,{},'precedence_violation'))
        rows=deepcopy(self.rows);rows[1]['tonnes']=1;cases.append((rows,{},'task_values_changed'))
        cases.extend([(self.rows,{'mining_capacity':9},'mining_capacity'),(self.rows,{'processing_capacity':9},'processing_capacity'),
                      (self.rows,{'maximum_grade':1.5},'feed_grade'),(self.rows+self.rows[:1],{},'duplicate_task')])
        for rows,kwargs,error in cases:
            with self.subTest(error=error):self.assertIn(error,self.audit(rows,**kwargs)['violations'])

    def test_solver_includes_separate_row_audit_and_reserved_period(self):
        self.tasks[0]['period']=99
        result=blend_schedule(self.tasks,10,10,2,1,3)
        self.assertTrue(result['feasibility_audit']['passed'])
        self.assertEqual([r['period'] for r in result['rows']],[1,2])


class BlockImportUiFlow(unittest.TestCase):
    def test_rotated_selection_applies_model_and_clears_stale_slices(self):
        from unittest.mock import patch
        from rainymine.pro_tools import ProTools
        from rainymine.core import Project
        from rainymine.block_csv import KEYS
        from PySide6.QtWidgets import QMessageBox
        class Harness(ProTools):
            def __init__(self):
                self.project=Project();self.project.crs_code='EPSG:32648';self.project.grade_unit='ppm'
                self.project.workspace['block_slice_positions']=[999,999,999]
                self.project.workspace['schedule']={'stale':True}
                self.answers=iter([{'Geometry':'Explicit rotated / sub-block grid','Metadata rows after header':'0'},
                    {'Origin X':'0','Origin Y':'0','Origin Z':'0','Parent X':'10','Parent Y':'10','Parent Z':'10','Azimuth':'90','Dip':'0','Roll':'0'},dict(zip(KEYS,KEYS))])
            def params(self,*args):return next(self.answers)
            def launch_task(self,title,operation,apply):apply(operation(lambda:False))
            def commit(self,project):project.validate();self.project=project
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'blocks.csv';path.write_text('x,y,z,dx,dy,dz,grade\n2.5,5,5,5,10,10,0\n7.5,5,5,5,10,10,NULL\n')
            h=Harness()
            with patch('rainymine.pro_tools.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch('rainymine.pro_tools.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),patch('rainymine.pro_tools.QMessageBox.information'):
                h.block_csv_import()
            self.assertEqual(h.project.workspace['block_model']['import_report']['subblocks'],2)
            self.assertNotIn('block_slice_positions',h.project.workspace)
            self.assertNotIn('schedule',h.project.workspace)
            self.assertEqual(h.project.workspace['block_display'],'blocks')
