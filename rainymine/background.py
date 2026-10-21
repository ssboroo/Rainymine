"""Owned, cancellable-result worker for new CPU/file tasks; Qt apply stays on UI thread."""
import threading
from PySide6.QtCore import QObject,QThread,Signal,Slot,Qt
from PySide6.QtWidgets import QProgressDialog,QMessageBox


class Worker(QThread):
    result=Signal(object);failed=Signal(str)
    def __init__(self,operation,cancel,parent):super().__init__(parent);self.operation=operation;self.cancel=cancel
    def run(self):
        try:
            result=self.operation(self.cancel.is_set)
            if not self.cancel.is_set():self.result.emit(result)
        except Exception as error:
            if not self.cancel.is_set():self.failed.emit(type(error).__name__+': '+str(error))


class Task(QObject):
    def __init__(self,window,title,operation,apply):
        super().__init__(window);self.window=window;self.source=window.project;self.apply=apply;self.cancel=threading.Event()
        self.progress=QProgressDialog(title,'Цуцлах',0,0,window);self.progress.setWindowModality(Qt.WindowModality.NonModal);self.progress.setMinimumDuration(0);self.progress.canceled.connect(self.cancel.set)
        self.worker=Worker(operation,self.cancel,self);self.worker.result.connect(self.done);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.finished)
        window._engineering_tasks.append(self);self.progress.show();self.worker.start()
    @Slot(object)
    def done(self,result):
        self.progress.hide()
        if self.cancel.is_set():return
        if self.source is not self.window.project:
            QMessageBox.information(self.window,'Үр дүн хэрэгжээгүй','Тооцоо явж байх хооронд төсөл өөрчлөгдсөн. Шинэ өгөгдөл дээр дахин ажиллуулна уу.');return
        self.window.guard(lambda:self.apply(result))
    @Slot(str)
    def failed(self,message):self.progress.hide();QMessageBox.warning(self.window,'Ажиллагаа амжилтгүй',message)
    @Slot()
    def finished(self):
        self.progress.hide();self.progress.deleteLater()
        if self in self.window._engineering_tasks:self.window._engineering_tasks.remove(self)
        self.worker.deleteLater();self.deleteLater()
