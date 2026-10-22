import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from rainymine.core import Project,load_project
from rainymine.disk_model import DiskModel
from rainymine.project_pack import export_project_pack,import_project_pack


class ProjectPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.pack=self.root/'Монгол.rmpack'
        self.project=Project(name='Монгол төсөл',crs_code='EPSG:32648',grade_unit='ppm')
        self.db=self.root/'source.rmdb'
        DiskModel.create(self.db,[500000,5300000,1000],[2,1,1],[10]*3,'EPSG:32648','ppm',2.5)
        with DiskModel(self.db) as store:store.edit(0,0,2.5,'ore');store.edit(1,2,2.7,None)
        self.project.workspace['disk_block_stores']=[str(self.db)]

    def test_portable_roundtrip_preserves_db_history_and_relinks(self):
        before=hashlib.sha256(self.db.read_bytes()).hexdigest()
        manifest=export_project_pack(self.pack,self.project)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),before)
        self.assertEqual(self.project.workspace['disk_block_stores'],[str(self.db)])
        project,path,report=import_project_pack(self.pack,self.root/'Restored')
        self.assertEqual(load_project(path),project)
        self.assertEqual(project.workspace['disk_block_stores'],[str(self.root/'Restored/stores/0.rmdb')])
        with DiskModel(project.workspace['disk_block_stores'][0]) as store:
            self.assertEqual(store.count(),2);self.assertAlmostEqual(store.totals()['contained_metal_tonnes'],.0054)
            self.assertTrue(store.undo());self.assertTrue(store.undo(True))
        self.assertEqual(manifest,report)

    def test_missing_source_and_cancel_preserve_previous_archive(self):
        self.pack.write_bytes(b'previous')
        with self.assertRaises(RuntimeError):export_project_pack(self.pack,self.project,lambda:True)
        self.assertEqual(self.pack.read_bytes(),b'previous')
        self.project.workspace['disk_block_stores']=[str(self.root/'missing.rmdb')]
        with self.assertRaises(FileNotFoundError):export_project_pack(self.pack,self.project)
        self.assertEqual(self.pack.read_bytes(),b'previous')

    def test_hash_mismatch_traversal_and_cancel_leave_no_destination(self):
        export_project_pack(self.pack,self.project)
        with zipfile.ZipFile(self.pack) as archive:files={n:archive.read(n) for n in archive.namelist()}
        files['project.rmine']=b'['+files['project.rmine'][1:]
        bad=self.root/'bad.rmpack'
        with zipfile.ZipFile(bad,'w') as archive:
            for name,data in files.items():archive.writestr(name,data)
        dest=self.root/'Bad'
        with self.assertRaisesRegex(ValueError,'SHA256'):import_project_pack(bad,dest)
        self.assertFalse(dest.exists())
        with zipfile.ZipFile(bad,'a') as archive:archive.writestr('../escape',b'no')
        with self.assertRaises(ValueError):import_project_pack(bad,dest)
        self.assertFalse((self.root/'escape').exists())
        with self.assertRaises(RuntimeError):import_project_pack(self.pack,dest,lambda:True)
        self.assertFalse(dest.exists())

    def test_empty_project_and_existing_destination(self):
        export_project_pack(self.pack,Project(name='Empty'))
        project,path,_=import_project_pack(self.pack,self.root/'Empty')
        self.assertEqual(project.name,'Empty')
        with self.assertRaises(ValueError):import_project_pack(self.pack,self.root/'Empty')

    def test_wrong_units_and_duplicate_links_rejected(self):
        self.project.grade_unit='%'
        with self.assertRaises(ValueError):export_project_pack(self.pack,self.project)
        self.project.grade_unit='ppm';self.project.workspace['disk_block_stores']*=2
        with self.assertRaises(ValueError):export_project_pack(self.pack,self.project)
