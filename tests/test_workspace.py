import unittest
from PySide6.QtCore import Qt, QModelIndex
from rainymine.workspace import BlockTableModel


class WorkspaceDataTests(unittest.TestCase):
    def test_real_coordinates_grades_and_missing_fields(self):
        model = BlockTableModel()
        blocks = [{'x': 612320., 'y': 7581420., 'z': 420., 'grade': .62}]
        model.set_blocks(blocks, '%', 1)
        self.assertIs(model.blocks, blocks)
        self.assertEqual(model.data(model.index(0, 1)), '612,320.000')
        self.assertEqual(model.data(model.index(0, 4)), '0.620')
        self.assertEqual(model.data(model.index(0, 5)), '—')
        self.assertEqual(model.data(model.index(0, 6)), '—')
        self.assertEqual(model.headerData(4, Qt.Orientation.Horizontal), 'Агуулга (%)')

    def test_reset_empty_and_parent_boundaries(self):
        model = BlockTableModel()
        model.set_blocks([{'grade': None}], 'g/t')
        self.assertEqual(model.data(model.index(0, 4)), '—')
        self.assertIsNone(model.data(QModelIndex()))
        self.assertEqual(model.rowCount(model.index(0, 0)), 0)
        model.set_blocks([], '%')
        self.assertEqual(model.rowCount(), 0)

    def test_grade_colour_does_not_replace_data(self):
        model = BlockTableModel()
        model.set_blocks([{'grade': 100.}, {'grade': -1.}], '%', 1.)
        self.assertTrue(model.data(model.index(0, 4), Qt.ItemDataRole.BackgroundRole).isValid())
        self.assertEqual(model.data(model.index(1, 4)), '-1.000')


class WorkspaceLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        # Layout/data integration is tested without requiring a GPU/display server.
        # Windows smoke tests exercise the real QVTK widget and rendered pixels.
        from unittest.mock import patch
        from PySide6.QtWidgets import QWidget
        import vtk
        class View(QWidget):
            def __init__(inner, *args, **kwargs):
                super().__init__(*args, **kwargs)
                inner.window = vtk.vtkRenderWindow()
                inner.window.Render = lambda: None
            def GetRenderWindow(inner): return inner.window
            def SetInteractorStyle(inner, *args): pass
            def AddObserver(inner, *args): pass
            def Initialize(inner): pass
            def Finalize(inner): pass
        from rainymine.workspace import WorkspaceWorkbench
        with patch('rainymine.ui.QVTKRenderWindowInteractor', View), patch('rainymine.workbench.QVTKRenderWindowInteractor', View):
            window = WorkspaceWorkbench()
        def close():
            window.dirty = False
            window.close()
        self.addCleanup(close)
        return window

    def test_reference_layout_retains_real_data_and_help(self):
        window = self.make_window()
        self.assertEqual([window.ribbon.tabText(i) for i in range(window.ribbon.count())],
                         ['Төсөл', 'Өрөмдлөг', 'Геологи', 'Блок загвар', 'Уурхайн төлөвлөлт', 'Харагдац'])
        self.assertEqual(window.project_pages.count(), 3)
        self.assertEqual(window.block_model.rowCount(), len(window.project.workspace['block_model']['blocks']))
        self.assertIs(window.block_model.blocks, window.project.workspace['block_model']['blocks'])
        self.assertEqual(window.layer_list.topLevelItemCount(), 4)
        self.assertFalse(window.support.isHidden())
        self.assertIs(window.table, window.data_tabs.widget(1))
        self.assertIn('90220101', window.project_summary.text())

    def test_view_modes_groups_and_table_selection(self):
        window = self.make_window()
        window.change_workspace_view('section')
        self.assertTrue(window.slab.isChecked())
        window.change_workspace_view('top')
        self.assertFalse(window.slab.isChecked())
        window.layer_selected(window.layer_list.topLevelItem(0))
        window.block_row_selected(window.block_model.index(0, 0))
        self.assertEqual(window.active_layer, 'blocks')
        self.assertIn('Блок #1', window.picked_info.text())
        window.focus_search()
        self.assertEqual(window.project_pages.currentIndex(), 1)

    def test_brand_controls_preserve_panel_visibility(self):
        window = self.make_window()
        self.assertEqual(window.assistant_tabs.count(), 4)
        self.assertEqual(window.brand_project.text(), window.project.name)
        self.assertFalse(window.windowIcon().isNull())
        window.support.hide()
        window.focus_workspace()
        self.assertTrue(window.layer_dock.isHidden())
        self.assertTrue(window.data_tabs.isHidden())
        window.focus_workspace()
        self.assertFalse(window.layer_dock.isHidden())
        self.assertFalse(window.data_tabs.isHidden())
        self.assertTrue(window.support.isHidden())
        expanded = window.ribbon.height()
        window.collapse_ribbon()
        self.assertLess(window.ribbon.height(), expanded)
        self.assertGreaterEqual(window.ribbon.height(), window.ribbon.tabBar().sizeHint().height())
        window.collapse_ribbon()
        self.assertEqual(window.ribbon.height(), expanded)

    def test_labels_toggle_matches_scene_and_section(self):
        window = self.make_window()
        window.toggle_labels(True)
        self.assertTrue(window.labels_visible)
        for label in window.scene.labels:
            self.assertEqual(bool(label.GetVisibility()),
                             bool(window.scene.actors['holes'].GetVisibility()))
        window.change_workspace_view('section')
        for label in window.scene.labels:
            self.assertFalse(label.GetVisibility())
        window.change_workspace_view('iso')
        window.toggle_labels(False)
        for label in window.scene.labels:
            if label.GetInput() != window.scene.selected_hole:
                self.assertFalse(label.GetVisibility())
