"""UI interaction tests with actual VTK data pipelines, without native GL rendering.
The Windows smoke separately exercises the real QVTK widget and framebuffer.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen') if os.name!='nt' else None
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import Qt
from tests.test_scene import NoRenderWindow


class HeadlessWindow(NoRenderWindow):
    def SetMultiSamples(self,n):pass


class HeadlessVTK(QWidget):
    def __init__(self,parent=None):super().__init__(parent);self.window=HeadlessWindow()
    def GetRenderWindow(self):return self.window
    def SetInteractorStyle(self,style):pass
    def AddObserver(self,*args):pass
    def Initialize(self):pass
    def Finalize(self):pass


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion')
        from rainymine.presentation import PresentationWorkbench
        with patch('rainymine.ui.QVTKRenderWindowInteractor',HeadlessVTK),patch('rainymine.workbench.QVTKRenderWindowInteractor',HeadlessVTK):
            cls.window=PresentationWorkbench()
        cls.window.resize(1280,850);cls.window.show();cls.app.processEvents()
    @classmethod
    def tearDownClass(cls):cls.window.dirty=False;cls.window.close();cls.app.processEvents()
    def test_palette_filters_and_runs_real_callback(self):
        from rainymine.presentation import CommandPalette
        called=[];palette=CommandPalette(self.window,[('Блок модель',lambda:called.append(True),True),('Импорт',lambda:None,False)])
        palette.search.setText('блок');self.assertEqual(palette.results.count(),1)
        palette.launch();self.app.processEvents();self.assertEqual(called,[True])
        palette.search.setText('импорт');self.assertEqual(palette.results.count(),0);palette.close()
    def test_focus_and_ribbon_restore(self):
        w=self.window;old=[d.isHidden() for d in (w.project_dock,w.section_dock,w.layer_dock,w.data_dock)]
        w.focus_workspace();self.assertTrue(w.focus_active);self.assertTrue(w.layer_dock.isHidden())
        w.focus_workspace();self.assertFalse(w.focus_active)
        self.assertEqual([d.isHidden() for d in (w.project_dock,w.section_dock,w.layer_dock,w.data_dock)],old)
        w.collapse_ribbon();self.assertEqual(w.ribbon.height(),36)
        w.collapse_ribbon();self.assertEqual(w.ribbon.height(),134)
    def test_label_toggle_and_project_data_unchanged(self):
        from copy import deepcopy
        w=self.window;before=deepcopy(w.project);w.toggle_labels(True)
        self.assertTrue(all(label.GetVisibility() for label in w.scene.labels))
        w.toggle_labels(False);self.assertFalse(any(label.GetVisibility() for label in w.scene.labels))
        self.assertEqual(w.project,before)
    def test_startup_artwork_is_available(self):
        from rainymine.startup import StartupScreen
        splash=StartupScreen();self.assertTrue(splash.artwork_loaded)
        splash.set_stage('Модуль ачаалж байна…');self.assertGreater(splash.pixmap().width(),500);splash.close()
    def test_decorating_grouped_layers_never_records_data_changes(self):
        w=self.window;before=len(w.history.undo_items)
        w.refresh_layers();w.refresh_layers()
        self.assertEqual(len(w.history.undo_items),before)
        self.assertGreater(w.layer_list.topLevelItem(0).childCount(),0)
    def test_block_table_paging_preserves_source_ids(self):
        w=self.window;model=w.project.workspace['block_model'];original=model['blocks']
        try:
            model['blocks']=original+original;w.render_block_page(1)
            self.assertEqual(w.block_table.item(0,0).text(),'1000')
            self.assertLessEqual(w.block_table.rowCount(),1000)
            self.assertTrue(w.previous_page.isEnabled())
        finally:model['blocks']=original;w.render_block_page(0)
    def test_local_ai_ui_is_preserved_in_guide_tab(self):
        w=self.window;w.show_ai_guide();self.assertEqual(w.guide_tabs.currentIndex(),2)
        w.support.question.setText('Өнөөдөр цаг агаар ямар вэ?');w.support.ask()
        self.assertIn('Rainymine',w.support.chat.toPlainText())
        self.assertIsNone(w.support.engine);w.support.clear();w.guide_tabs.setCurrentIndex(0)
