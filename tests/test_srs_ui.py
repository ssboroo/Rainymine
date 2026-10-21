"""Exercise readonly command wiring and the real Qt chart without a native GPU."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog
from tests import test_workspace


class SrsMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_workspace.WorkspaceLayoutTests.setUpClass.__func__(cls)

    def test_commands_and_chart_preserve_project(self):
        window=test_workspace.WorkspaceLayoutTests.make_window(self);before=deepcopy(window.project)
        menu=next(a.menu() for a in window.menuBar().actions() if a.text()=='Шинжилгээ / SRS')
        self.assertEqual(len(menu.actions()),14)
        with patch.object(window,'params',return_value={'Урт, м':5}),patch.object(window,'show_rows') as show:
            window.lithology_composite_report();self.assertTrue(show.call_args.args[1])
        with patch.object(window,'params',return_value={'Босго, градус / 30 м':10}),patch.object(window,'show_rows') as show:
            window.survey_dogleg_report();self.assertTrue(show.call_args.args[1])
        def close_chart():
            for w in QApplication.topLevelWidgets():
                if isinstance(w,QDialog) and w.windowTitle()=='Swath X':w.accept()
        QTimer.singleShot(100,close_chart)
        window.swath_chart([{'from_m':0,'to_m':10,'sample_grade':1,'block_grade':2},
                            {'from_m':10,'to_m':20,'sample_grade':None,'block_grade':None},
                            {'from_m':20,'to_m':30,'sample_grade':3,'block_grade':4}],'X')
        self.assertEqual(window.project,before)

    def test_edit_structure_text_and_nullable_geotech(self):
        from rainymine.core import Structure,Geotech
        from rainymine.data_tools import SCHEMAS
        from rainymine.workbench import GridDialog
        window=test_workspace.WorkspaceLayoutTests.make_window(self)
        hole=window.project.collars[0].hole_id
        window.project.structure=[Structure(hole,10,45,30,'JOINT')]
        window.project.geotech=[Geotech(hole,0,10,80,90)]
        def edit(dialog):
            if 'structure' in dialog.windowTitle():dialog.table.item(0,4).setText('FAULT')
            dialog.box.accepted.emit()
            return QDialog.DialogCode.Accepted
        with patch.object(GridDialog,'exec',edit),patch('rainymine.ui.QMessageBox.critical',side_effect=AssertionError('grid validation failed')):
            with patch.object(window,'choose',return_value=list(SCHEMAS).index('structure')):window.edit_grid()
            with patch.object(window,'choose',return_value=list(SCHEMAS).index('geotech')):window.edit_grid()
        self.assertEqual(window.project.structure[0].feature_type,'FAULT')
        self.assertIsNone(window.project.geotech[0].ucs_mpa)
