from pathlib import Path
import tempfile
import unittest
from rainymine.block_csv import read_block_csv,KEYS
from rainymine.core import Project,save_project,load_project
from rainymine.estimation import tonnage_grade
from rainymine.project_pack import export_project_pack,import_project_pack


class V1WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/'vendor.csv'
        self.path.write_text('x,y,z,dx,dy,dz,grade,rho,rock,Au2,ID,valid\n5,5,5,10,10,10,0,2.5,ORE,1.2,0007,true\n15,5,5,10,10,10,2,2.7,,NULL,0012,false\n',encoding='utf-8')
        self.attributes={'density':{'column':'rho','kind':'number','unit':'t/m3'},'domain':{'column':'rock','kind':'text','unit':''},'Au2':{'column':'Au2','kind':'number','unit':'ppm'},'sample_id':{'column':'ID','kind':'text','unit':''},'valid':{'column':'valid','kind':'boolean','unit':''}}

    def test_csv_attributes_weighted_report_and_portable_reopen(self):
        model,report=read_block_csv(self.path,dict(zip(KEYS,KEYS)),'EPSG:32648','ppm',attributes=self.attributes)
        self.assertEqual(report['extra_columns'],[])
        self.assertEqual(model['blocks'][0]['attributes'],{'Au2':1.2,'sample_id':'0007','valid':True})
        self.assertEqual(model['blocks'][1]['attributes']['Au2'],None)
        self.assertEqual(model['blocks'][1]['domain'],'')
        rows=tonnage_grade(model,9,[0,1])
        self.assertEqual(rows[0]['tonnes'],5200);self.assertAlmostEqual(rows[0]['mean_grade'],5400/5200)
        self.assertEqual(rows[1]['tonnes'],2700);self.assertEqual(rows[1]['mean_grade'],2)
        project=Project(crs_code='EPSG:32648',grade_unit='ppm');project.workspace['block_model']=model
        save_project(self.root/'work.rmine',project)
        export_project_pack(self.root/'work.rmpack',load_project(self.root/'work.rmine'))
        restored,path,_=import_project_pack(self.root/'work.rmpack',self.root/'OtherPC')
        self.assertEqual(restored.workspace['block_model'],model)
        self.assertEqual(tonnage_grade(restored.workspace['block_model'],9,[0]),rows[:1])

    def test_bad_attributes_and_percent_grade_reject_atomically(self):
        bad=dict(self.attributes);bad['density']={'column':'rho','kind':'text','unit':'t/m3'}
        with self.assertRaises(ValueError):read_block_csv(self.path,dict(zip(KEYS,KEYS)),'EPSG:32648','ppm',attributes=bad)
        self.path.write_text('x,y,z,dx,dy,dz,grade\n5,5,5,10,10,10,101\n')
        with self.assertRaises(ValueError):read_block_csv(self.path,dict(zip(KEYS,KEYS)),'EPSG:32648','%')
        with self.assertRaises(ValueError):tonnage_grade({'blocks':[dict(x=0,y=0,z=0,dx=1,dy=1,dz=1,grade=1,density=-1)]},2,[0])

    def test_import_rejects_unsavable_candidate_before_replacing_project(self):
        from unittest.mock import patch
        from rainymine.pro_tools import ProTools
        from PySide6.QtWidgets import QMessageBox
        class Harness(ProTools):
            def __init__(self):
                self.project=Project(crs_code='EPSG:32648',grade_unit='ppm');self.commits=0
                self.answers=iter([{'Geometry':'World-axis uniform parents','Metadata rows after header':'0'},dict(zip(KEYS,KEYS)),{'Нягтын багана':'rho','Домэйны багана':'rock','Бусад багана':'Текстээр хадгалах'}])
            def params(self,*args):return next(self.answers)
            def launch_task(self,title,operation,apply):apply(operation(lambda:False))
            def commit(self,p):self.commits+=1;self.project=p
        window=Harness();old=window.project
        with patch('rainymine.pro_tools.QFileDialog.getOpenFileName',return_value=(str(self.path),'')),patch('rainymine.pro_tools.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),patch('rainymine.core.MAX_FILE',1):
            with self.assertRaises(ValueError):window.block_csv_import()
        self.assertEqual(window.commits,0);self.assertIs(window.project,old)
