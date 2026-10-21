"""Native local support dock; background setup/inference and reviewed help rendering."""
import threading
from PySide6.QtCore import Qt,QThread,Signal,QSettings
from PySide6.QtWidgets import QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTextEdit,QLineEdit,QFileDialog,QComboBox
from .local_engine import LocalEngine,default_paths,install_assets
from .local_support import answer,candidates,OUT_OF_SCOPE
from .support_knowledge import TOPICS
from .i18n import language
from .local_support import out_of_scope


class SupportWorker(QThread):
    result=Signal(object)
    failure=Signal(str)
    progress=Signal(str)
    def __init__(self,callback,parent=None):
        super().__init__(parent);self.callback=callback;self.cancelled=threading.Event()
    def run(self):
        try:self.result.emit(self.callback(self))
        except Exception as exc:self.failure.emit(str(exc))


class SupportDock(QDockWidget):
    def __init__(self,parent):
        super().__init__('ХИЙМЭЛ ОЮУНЫ ТУСЛАХ',parent);self.worker=None;self.engine=None;self.previous=None;self._conversation_started=False
        self.settings=QSettings();engine,model=default_paths()
        self.engine_path=self.settings.value('local_ai/engine',str(engine));self.model_path=self.settings.value('local_ai/model',str(model))
        panel=QWidget();layout=QVBoxLayout(panel);self.setWidget(panel);self.setMinimumWidth(340)
        note=QLabel('Зөвхөн Rainymine ашиглах, тохируулах, алдаа засах туслах.\nТөслийн өгөгдөл болон чатын түүх үүлэн үйлчилгээ рүү илгээхгүй.');note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();self.setup_button=QPushButton('Анх тохируулах · 1.28 GB');self.setup_button.clicked.connect(self.setup)
        self.files_button=QPushButton('Файл сонгох');self.files_button.clicked.connect(self.choose_files);row.addWidget(self.setup_button);row.addWidget(self.files_button);layout.addLayout(row)
        self.status=QLabel('Локал загвар бэлэн бол асуултаа бичнэ. Анх татахад интернэт хэрэгтэй.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.chat=QTextEdit();self.chat.setReadOnly(True);self.chat.setAcceptRichText(False);layout.addWidget(self.chat,1)
        self.question=QLineEdit();self.question.setMaxLength(2000);self.question.setPlaceholderText('Жишээ: CSV импортын алдааг яаж засах вэ?');self.question.returnPressed.connect(self.ask);layout.addWidget(self.question)
        row=QHBoxLayout();self.ask_button=QPushButton('Асуух');self.ask_button.clicked.connect(self.ask);self.cancel_button=QPushButton('Зогсоох / Санах ой чөлөөлөх');self.cancel_button.clicked.connect(self.cancel);row.addWidget(self.ask_button);row.addWidget(self.cancel_button);layout.addLayout(row)
        self.manual=QComboBox();self.manual.addItem('Зааврыг шууд үзэх — модель шаардахгүй');self.manual.addItems([t['title'] for t in TOPICS]);self.manual.activated.connect(self.show_manual);layout.addWidget(self.manual)
        clear=QPushButton('Чат цэвэрлэх');clear.clicked.connect(self.clear);layout.addWidget(clear)
    def append(self,who,text):
        self._conversation_started=True
        self.chat.append('')
        cursor=self.chat.textCursor();cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(who+'\n'+text+'\n');self.chat.setTextCursor(cursor)
    def clear(self):self.chat.clear();self.previous=None;self._conversation_started=False
    def busy(self):return self.worker is not None and self.worker.isRunning()
    def start_worker(self,callback,on_result):
        if self.busy():return
        self.setup_button.setEnabled(False);self.files_button.setEnabled(False);self.ask_button.setEnabled(False)
        worker=SupportWorker(callback,self);self.worker=worker
        worker.progress.connect(self.status.setText);worker.result.connect(on_result);worker.failure.connect(self.failed)
        worker.finished.connect(self.finished);worker.start()
    def finished(self):
        self.setup_button.setEnabled(True);self.files_button.setEnabled(True);self.ask_button.setEnabled(True)
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
    def failed(self,message):
        self.status.setText('Local AI: '+message);self.append('Тусламж',message+'\nДоорх жагсаалтаас зааврыг шууд үзэж болно.')
    def setup(self):
        def run(worker):
            def progress(done,total):worker.progress.emit(f'AI файл татаж байна: {done/1e6:.0f} / {total/1e6:.0f} MB')
            return install_assets(progress,worker.cancelled.is_set)
        def done(paths):
            self.save_paths(*paths);self.status.setText('Engine ба model татагдаж шалгагдлаа. Одоо оффлайн асууж болно.')
        self.status.setText('Engine/model бэлтгэж байна…');self.start_worker(run,done)
    def save_paths(self,engine,model):
        if self.engine:self.engine.stop();self.engine=None
        self.engine_path=engine;self.model_path=model
        self.settings.setValue('local_ai/engine',engine);self.settings.setValue('local_ai/model',model)
    def choose_files(self):
        engine,_=QFileDialog.getOpenFileName(self,'Локал хөдөлгүүрийн файл',self.engine_path,'Engine (*)')
        if not engine:return
        model,_=QFileDialog.getOpenFileName(self,'GGUF загвар',self.model_path,'GGUF (*.gguf)')
        if model:self.save_paths(engine,model);self.status.setText('Локал файлууд сонгогдлоо. Асуух үед модель ачаална.')
    def show_manual(self,index):
        if not index:return
        from .local_support import render_selection
        import json
        topic=TOPICS[index-1];text,self.previous=render_selection(json.dumps({'topic_ids':[topic['id']]}),[topic],language())
        self.append('Rainymine заавар',text)
    def ask(self):
        if self.busy():return
        question=self.question.text().strip()
        if not question:return
        self.question.clear();self.append('Та',question)
        if not candidates(question,self.previous):self.append('Assistant' if language()=='en' else 'Туслах',out_of_scope(language()));return
        if self.engine is None:self.engine=LocalEngine(self.engine_path,self.model_path)
        engine=self.engine;previous=self.previous;locale=language()
        def run(worker):
            worker.progress.emit('Local model ачаалж байна…');engine.start(worker.cancelled.is_set)
            if worker.cancelled.is_set():raise RuntimeError('AI асуултыг цуцаллаа.')
            worker.progress.emit('Rainymine-ийн тохирох зааврыг сонгож байна…')
            return answer(question,engine,previous,locale)
        def done(result):
            text,self.previous=result;self.append('Local AI туслах',text);self.status.setText('Local model ажиллаж байна. Зогсоох товч RAM чөлөөлнө.')
        self.start_worker(run,done)
    def cancel(self):
        if self.worker:self.worker.cancelled.set()
        if self.engine:self.engine.stop();self.engine=None
        self.status.setText('Local AI зогсоолоо. Таталт явж байсан бол цуцлагдаж дуусахыг хүлээнэ.')
    def shutdown(self):self.cancel()
