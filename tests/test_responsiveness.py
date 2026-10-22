"""Regression checks for dialog cursors, cheap dispatch and real worker delivery."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import threading
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEventLoop,QTimer,Qt
from PySide6.QtWidgets import QApplication


class ResponsiveMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def window(self):
        from tests.test_workspace import WorkspaceLayoutTests
        return WorkspaceLayoutTests.make_window(self)

    def test_dialog_dispatch_does_not_copy_compare_or_serialize_project(self):
        window=self.window();observed=[]
        def inspect_dialog():
            dialog=self.app.activeModalWidget()
            observed.append((dialog is not None,QApplication.overrideCursor()))
            if dialog:dialog.reject()
        QTimer.singleShot(0,inspect_dialog)
        with patch('rainymine.workbench.deepcopy',side_effect=AssertionError('Unnecessary project copy')),patch.object(type(window.project),'__eq__',side_effect=AssertionError('Unnecessary deep comparison')),patch.object(window.history,'apply',side_effect=AssertionError('Unnecessary history snapshot')):
            result=window.guard(lambda:window.params('Dialog',{'Value':1}))
        self.assertIsNone(result);self.assertEqual(observed,[(True,None)])

    def test_guard_preserves_cursor_owned_by_another_operation(self):
        window=self.window();QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
        try:
            self.assertEqual(window.guard(lambda:QApplication.overrideCursor().shape()),Qt.CursorShape.CrossCursor)
            with patch('rainymine.ui.QMessageBox.critical'):
                self.assertFalse(window.guard(lambda:(_ for _ in ()).throw(ValueError('expected'))))
            self.assertEqual(QApplication.overrideCursor().shape(),Qt.CursorShape.CrossCursor)
        finally:QApplication.restoreOverrideCursor()

    def test_nested_guard_records_one_undo_step(self):
        window=self.window();before=window.project.name;candidate=deepcopy(window.project);candidate.name='Edited'
        with patch.object(window.history,'apply',wraps=window.history.apply) as record:
            window.guard(lambda:window.guard(lambda:window.commit(candidate)))
            self.assertEqual(record.call_count,1)
        window.undo();self.assertEqual(window.project.name,before)
        window.redo();self.assertEqual(window.project.name,'Edited')

    def test_failure_restores_project_dirty_flag_and_nested_history(self):
        window=self.window();original=window.project;dirty=window.dirty;candidate=deepcopy(original);candidate.name='Rejected'
        def fail():
            window.guard(lambda:window.commit(candidate))
            raise ValueError('after commit')
        with patch('rainymine.ui.QMessageBox.critical'):
            self.assertFalse(window.guard(fail))
        self.assertIs(window.project,original);self.assertEqual(window.dirty,dirty);self.assertFalse(window.history.undo_items)

    def run_block_job(self,cancel=False):
        window=self.window();original=window.project;model=deepcopy(original.workspace['block_model']);release=threading.Event();observed=[]
        settings={**{f'{p} {a}':str(v) for p,values in [('Min',[0,0,0]),('Max',[10,10,10]),('Size',[10,10,10])] for a,v in zip('XYZ',values)},'Grid azimuth':'90','Grid dip':'0','Grid roll':'0','Sub-block levels':'0','Домэйн':'Бүх талбай'}
        def estimate(project,bounds,size,params,domain,cancel=None,progress=None):
            if not release.wait(2):raise RuntimeError('Test heartbeat did not run')
            if cancel and cancel():raise RuntimeError('Cancelled')
            if progress:progress(1,2)
            return model
        with patch.object(window,'estimator_params',return_value={'method':'idw'}),patch.object(window,'params',return_value=settings),patch('rainymine.workbench.estimate_model',side_effect=estimate),patch('rainymine.workbench.QMessageBox.information'):
            window.block_dialog();self.assertEqual(len(window._engineering_tasks),1)
            task=window._engineering_tasks[0];loop=QEventLoop();task.worker.finished.connect(loop.quit)
            def heartbeat():
                observed.append((window.project is original,QApplication.overrideCursor()))
                if cancel:task.cancel.set()
                release.set()
            QTimer.singleShot(20,heartbeat);QTimer.singleShot(3000,loop.quit);loop.exec();self.app.processEvents()
        self.assertEqual(observed,[(True,None)]);self.assertFalse(window._engineering_tasks)
        self.assertEqual(window.project is original,cancel)
        self.assertEqual(len(window.history.undo_items),0 if cancel else 1)
    def test_block_estimation_keeps_event_loop_alive_and_applies_once(self):self.run_block_job()
    def test_block_cancellation_never_changes_project(self):self.run_block_job(cancel=True)

    def test_progress_and_cancel_do_not_set_global_wait_cursor(self):
        from rainymine.background import Task
        window=self.window();release=threading.Event();received=[];observed=[]
        def work(cancel,progress):
            progress(1,2);release.wait(2);return 42
        task=Task(window,'Progress',work,received.append,with_progress=True);loop=QEventLoop();task.worker.finished.connect(loop.quit)
        def heartbeat():
            if task.progress.maximum()!=2:
                QTimer.singleShot(5,heartbeat);return
            observed.append((task.progress.maximum(),task.progress.value(),QApplication.overrideCursor()))
            task.cancel.set();release.set()
        QTimer.singleShot(30,heartbeat);QTimer.singleShot(3000,loop.quit);loop.exec();self.app.processEvents()
        self.assertEqual(observed,[(2,1,None)]);self.assertFalse(received);self.assertFalse(window._engineering_tasks)

    def test_selected_block_numbers_are_readable_without_changing_data(self):
        window=self.window();block={'x':1,'y':2,'z':3,'grade':.264466558,'variance':None}
        text=window.block_selection_text(1,block)
        self.assertIn('0.264',text);self.assertNotIn('None',text);self.assertNotIn('0.264466558',text);self.assertEqual(block['grade'],.264466558)

    def test_rbf_has_cooperative_cancellation(self):
        from rainymine.implicit import implicit_surface
        samples=[{'xyz':[x,y,z],'grade':x} for x in (0,1) for y in (0,1) for z in (0,1)]
        with self.assertRaises(RuntimeError):implicit_surface(samples,[0,0,0,1,1,1],.5,5,neighbors=4,cancel=lambda:True)

    def test_large_report_only_fetches_requested_rows(self):
        from rainymine.results_table import ResultTableModel,ResultsDialog
        class Rows:
            def __len__(self):return 50000
            def __getitem__(self,index):return {'grade':index,'missing':None}
            def __iter__(self):raise AssertionError('Eager report materialization')
        rows=Rows();model=ResultTableModel(['grade','missing'],rows);self.assertIs(model.rows,rows)
        self.assertEqual(model.rowCount(),50000);self.assertEqual(model.data(model.index(49999,0)),'49999');self.assertEqual(model.data(model.index(0,1)),'')
        dialog=ResultsDialog(None,['grade','missing'],rows,'Report');self.addCleanup(dialog.close)
        self.assertEqual(dialog.table.model().rowCount(),50000)

    def test_cross_validation_reports_progress_and_can_cancel(self):
        from rainymine.estimation import cross_validate
        samples=[{'xyz':[i,0,0],'grade':1,'hole_id':str(i)} for i in range(4)]
        params={'method':'nearest','minimum':1,'neighbors':4};progress=[]
        result=cross_validate(samples,params,progress=lambda i,n:progress.append((i,n)))
        self.assertEqual(result['attempted'],4);self.assertEqual(progress[-1],(4,4))
        with self.assertRaises(RuntimeError):cross_validate(samples,params,cancel=lambda:True)
