import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QEventLoop,QTimer
from PySide6.QtWidgets import QApplication,QWidget
from rainymine.background import Task


class BackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def window(self):
        w=QWidget();w.project=object();w._engineering_tasks=[];w.guard=lambda callback:callback();self.addCleanup(w.close);return w
    def run_task(self,window,apply,cancel=False,stale=False):
        task=Task(window,'Test',lambda stopped:42,apply);loop=QEventLoop();task.worker.finished.connect(loop.quit)
        if cancel:task.cancel.set()
        if stale:window.project=object()
        QTimer.singleShot(2000,loop.quit);loop.exec();self.app.processEvents()
        self.assertEqual(window._engineering_tasks,[])
    def test_worker_applies_on_ui_thread(self):
        from PySide6.QtCore import QThread
        seen=[];w=self.window();self.run_task(w,lambda value:seen.append((value,QThread.currentThread()==self.app.thread())))
        self.assertEqual(seen,[(42,True)])
    def test_cancelled_result_is_never_applied(self):
        seen=[];self.run_task(self.window(),seen.append,cancel=True);self.assertEqual(seen,[])
    def test_stale_project_is_never_overwritten(self):
        seen=[]
        with patch('rainymine.background.QMessageBox.information') as notice:
            self.run_task(self.window(),seen.append,stale=True);self.assertTrue(notice.called)
        self.assertEqual(seen,[])
