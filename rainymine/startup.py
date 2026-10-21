"""Show project artwork before importing the heavy Qt/VTK workbench."""
from pathlib import Path
import sys
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QFont,QPixmap
from PySide6.QtWidgets import QApplication,QSplashScreen
from . import __version__


class StartupScreen(QSplashScreen):
    def __init__(self):
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPainter
        image=QPixmap(1200,660);image.fill(Qt.GlobalColor.transparent)
        renderer=QSvgRenderer(str(root/'assets'/'splash.svg'))
        painter=QPainter(image);renderer.render(painter);painter.end()
        self.artwork_loaded=renderer.isValid()
        if image.isNull():image=QPixmap(960,540);image.fill(QColor('#152937'))
        screen=QApplication.primaryScreen().availableGeometry()
        width=min(960,int(screen.width()*.82))
        image=image.scaledToWidth(width,Qt.TransformationMode.SmoothTransformation)
        self.stage='Программ эхэлж байна…'
        super().__init__(image,Qt.WindowType.WindowStaysOnTopHint)
        self.pulse=0;self.timer=QTimer(self);self.timer.setInterval(35);self.timer.timeout.connect(self.advance)
        self.setAccessibleName('RAINYMINE эхэлж байна')
    def advance(self):self.pulse=(self.pulse+5)%max(1,self.width()//2);self.update()
    def showEvent(self,event):super().showEvent(event);self.timer.start()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def set_stage(self,text):
        from .i18n import tr
        self.stage=tr(text);self.repaint();QApplication.processEvents()
    def drawContents(self,painter):
        w,h=self.width(),self.height()
        painter.fillRect(0,h-80,w,80,QColor(9,25,37,150))
        painter.setFont(QFont('Segoe UI',9));painter.setPen(QColor('#d4e9eb'))
        painter.drawText(0,h-40,w,24,Qt.AlignmentFlag.AlignCenter,self.stage)
        x=w//4;length=w//2
        painter.setPen(QColor('#087a84'));painter.setBrush(QColor('#082d3b'));painter.drawRoundedRect(QRectF(x,h-54,length,7),3,3)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#00c5be'))
        position=self.pulse%(length+length//4)-length//4
        left=max(0,position);right=min(length,position+length//4)
        if right>left:painter.drawRoundedRect(QRectF(x+left,h-54,right-left,7),3,3)
        painter.setFont(QFont('Segoe UI',8));painter.setPen(QColor('#8caab8'));painter.drawText(w-80,h-10,'v'+__version__)


def launch():
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion')
    app.setApplicationName('RAINYMINE');app.setOrganizationName('Rainy Studio')
    splash=StartupScreen();splash.show();splash.set_stage('3D дүрслэлийн модулиудыг ачаалж байна…')
    try:
        from .ui import main
        return main(app=app,splash=splash)
    finally:splash.close()
