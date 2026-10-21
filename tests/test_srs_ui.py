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
