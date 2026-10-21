"""Mongolian evaluation/activation dialog. Expiry never deletes user projects."""
from datetime import datetime, timezone
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox


class LicenseDialog(QDialog):
    def __init__(self, manager, parent=None, save_callback=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle('RAINYMINE — Лиценз')
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        title = QLabel('RAINYMINE · 7 хоногийн туршилт')
        layout.addWidget(title)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message)
        layout.addWidget(QLabel('Төхөөрөмжийн дугаар — лиценз авахдаа хуулж илгээнэ:'))
        device = QLineEdit(manager.device)
        device.setReadOnly(True)
        layout.addWidget(device)
        note = QLabel('Туршилт эхлүүлснээс хойш 168 цаг үргэлжилнэ. Хугацаа дуусахад лиценз шаардлагатай.\nТөслийн файл устахгүй. Интернэт болон төлбөрийн мэдээлэл шаардахгүй.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.start = QPushButton('7 хоногийн туршилтыг эхлүүлэх')
        self.start.clicked.connect(self.start_trial)
        layout.addWidget(self.start)
        activate = QPushButton('Лицензийн файл сонгож идэвхжүүлэх…')
        activate.clicked.connect(self.activate)
        layout.addWidget(activate)
        self.proceed = QPushButton('Үргэлжлүүлэх')
        self.proceed.clicked.connect(self.accept)
        layout.addWidget(self.proceed)
        if save_callback:
            save = QPushButton('Одоогийн төслөө хадгалах…')
            save.clicked.connect(save_callback)
            layout.addWidget(save)
        close = QPushButton('Хаах')
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(10000)

    def refresh(self):
        status = self.manager.status()
        text = status.message
        if status.expires is not None:
            text += '\nДуусах хугацаа (UTC): ' + datetime.fromtimestamp(status.expires, timezone.utc).strftime('%Y-%m-%d %H:%M')
        self.message.setText(text)
        self.start.setVisible(status.kind == 'not_started')
        self.proceed.setEnabled(status.allowed)

    def start_trial(self):
        self.manager.status(start_trial=True)
        self.refresh()

    def activate(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Лиценз сонгох', '', 'RAINYMINE лиценз (*.rainylic)')
        if not path:
            return
        try:
            self.manager.activate(path)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, 'Идэвхжүүлэх боломжгүй', str(exc))
        self.refresh()

    def accept(self):
        if self.manager.status().allowed:
            super().accept()


def attach_licensing(window, manager):
    menu = window.menuBar().addMenu('Лиценз')
    action = menu.addAction('Хугацаа ба идэвхжүүлэлт…')
    action.triggered.connect(lambda: LicenseDialog(manager, window, window.save).exec())
    label = QLabel()
    window.statusBar().addPermanentWidget(label)
    window._license_locked = False

    def check():
        if window._license_locked:
            return
        status = manager.status()
        label.setText(status.message)
        if not status.allowed:
            window._license_locked = True
            # A modal dialog blocks editing while keeping explicit save available.
            while not manager.status().allowed:
                dialog = LicenseDialog(manager, window, window.save)
                dialog.exec()
                if manager.status().allowed:
                    break
                if window.may_discard():
                    window.dirty = False
                    window.close()
                    break
            window._license_locked = False
    timer = QTimer(window)
    timer.timeout.connect(check)
    timer.start(30000)
    window._license_timer = timer
    check()
