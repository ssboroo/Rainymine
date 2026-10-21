from copy import deepcopy
from pathlib import Path
import csv
import io
import math
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon, QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,
    QLabel,QPushButton,QFileDialog,QMessageBox,QDockWidget,QTreeWidget,QTreeWidgetItem,
    QTableWidget,QTableWidgetItem,QHeaderView,QToolBar,QDoubleSpinBox,QCheckBox,
    QFormLayout,QDialog,QDialogButtonBox,QLineEdit,QComboBox,QInputDialog,QAbstractItemView)
import vtkmodules.qt
vtkmodules.qt.PyQtImpl='PySide6'
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
from .core import (Project,Collar,demo,read_collars,read_surveys,read_assays,read_surface,
    load_project,save_project,export_trajectories,composite_assays,write_records,atomic_write,Trajectory)
from .scene import Scene
from . import __version__

STYLE='''
QMainWindow,QDialog,QWidget {background:#101827;color:#e1e9f5;font-family:"Segoe UI";font-size:12px;}
QMenuBar,QMenu,QToolBar {background:#172337;spacing:5px;}
QMenu::item:selected,QToolButton:hover {background:#285b62;}
QPushButton {background:#22344e;border:1px solid #32465f;border-radius:5px;padding:8px 12px;}
QPushButton:hover {background:#2c5e63;border-color:#4ed5b2;}
QTreeWidget,QTableWidget {background:#111c2d;alternate-background-color:#172337;gridline-color:#273851;border:1px solid #293a52;selection-background-color:#285e62;}
QHeaderView::section {background:#203149;color:#a9bcd2;padding:7px;border:0;}
QLineEdit,QDoubleSpinBox,QComboBox {background:#0e1828;border:1px solid #34475e;border-radius:4px;padding:6px;selection-background-color:#27746d;}
QDockWidget::title {background:#1c2c42;padding:8px;}
QStatusBar {background:#172337;color:#a8bdd1;}
QCheckBox {spacing:8px;padding:4px;}
QLabel#brand {font-size:22px;font-weight:700;color:#4ed5b2;}
QLabel#muted {color:#9bb0c8;}
QToolButton {padding:8px;}
QScrollBar:vertical {background:#152236;width:12px;}
QScrollBar::handle:vertical {background:#3c516b;min-height:30px;}
'''

class Window(QMainWindow):
    def __init__(self,empty=False):
        super().__init__();self.setWindowTitle(f'RAINYMINE {__version__} • Геологи ба 3D өрөмдлөг');self.resize(1440,900);self.setMinimumSize(1050,700)
        self.project=Project() if empty else demo();self.path=None;self.dirty=False;self.pick_points=[];self.measure_mode=False
        self.setStyleSheet(STYLE)
        self.build_ui();self.scene=Scene(self.vtk.GetRenderWindow())
        self.vtk.GetRenderWindow().SetMultiSamples(0)
        self.vtk.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.vtk.AddObserver('LeftButtonPressEvent',self.on_click)
        self.vtk.Initialize();self.refresh()
        self.autosave=QTimer(self);self.autosave.timeout.connect(self.backup);self.autosave.start(120000)

    def action(self,parent,label,callback,shortcut=None):
        a=QAction(label,self);a.triggered.connect(lambda checked=False:callback())
        if shortcut:a.setShortcut(QKeySequence(shortcut))
        parent.addAction(a);return a

    def build_ui(self):
        menu=self.menuBar().addMenu('Файл')
        for label,fn,key in [('Шинэ төсөл',self.new,'Ctrl+N'),('Төсөл нээх…',self.open,'Ctrl+O'),('Хадгалах',self.save,'Ctrl+S'),('Өөрөөр хадгалах…',lambda:self.save(True),'Ctrl+Shift+S')]:self.action(menu,label,fn,key)
        menu.addSeparator();self.action(menu,'Жишээ төсөл',self.open_demo);self.action(menu,'Төслийн тохиргоо',self.settings)
        imports=self.menuBar().addMenu('Өгөгдөл')
        for kind,label in [('collars','Цооногийн амсар'),('surveys','Замналын хэмжилт'),('assays','Сорьцын агуулга'),('surface','Гадаргын XYZ')]:
            self.action(imports,label+' CSV импорт…',lambda k=kind:self.import_data(k))
        self.action(imports,'Цооног гараар нэмэх…',self.add_hole)
        self.action(imports,'Өгөгдлийн шалгалт',self.validate_data)
        exports=self.menuBar().addMenu('Экспорт')
        self.action(exports,'Замналын координат CSV…',self.export_paths)
        self.action(exports,'Уртаар жигнэсэн композит CSV…',self.composites)
        self.action(exports,'3D зураг PNG…',self.export_png)
        self.action(exports,'Цооногийн геометр VTP…',self.export_vtp)
        self.action(exports,'Төслийн тайлан HTML…',self.report)
        self.action(self.menuBar().addMenu('Тусламж'),'Ашиглах заавар',self.help)
        toolbar=QToolBar('Үндсэн үйлдэл');toolbar.setMovable(False);self.addToolBar(toolbar)
        for label,fn in [('＋ Шинэ',self.new),('Нээх',self.open),('Хадгалах',self.save),('Цооног CSV',lambda:self.import_data('collars')),('Замнал CSV',lambda:self.import_data('surveys')),('Сорьц CSV',lambda:self.import_data('assays'))]:self.action(toolbar,label,fn)
        toolbar.addSeparator()
        for label,name in [('3D','iso'),('Дээрээс','top'),('Урдаас','north'),('Хажуугаас','east')]:self.action(toolbar,label,lambda n=name:self.scene.view(n))
        self.action(toolbar,'Төвлөрүүлэх',lambda:self.scene.reset())
        central=QWidget();layout=QVBoxLayout(central);layout.setContentsMargins(12,8,12,8)
        header=QHBoxLayout();brand=QLabel('◈  RAINYMINE');brand.setObjectName('brand');header.addWidget(brand)
        self.title_label=QLabel();self.title_label.setObjectName('muted');header.addWidget(self.title_label);header.addStretch();header.addWidget(QLabel('● ОФФЛАЙН  |  метр'))
        layout.addLayout(header)
        self.vtk=QVTKRenderWindowInteractor(central);layout.addWidget(self.vtk,1)
        footer=QLabel('Зүүн товч: эргүүлэх   •   Дугуй: томруулах   •   Shift + зүүн: зөөх   •   Хүснэгтээс цооног сонгоно');footer.setObjectName('muted');layout.addWidget(footer)
        self.setCentralWidget(central)
        left=QDockWidget('ТӨСЛИЙН ДАВХАРГУУД',self);left.setMinimumWidth(240)
        panel=QWidget();pl=QVBoxLayout(panel)
        self.stats=QLabel();self.stats.setWordWrap(True);pl.addWidget(self.stats)
        self.layer_checks={}
        for key,label in [('holes','Цооног ба сорьцын агуулга'),('collars','Цооногийн амсар'),('surface','Гадаргын TIN')]:
            check=QCheckBox(label);check.setChecked(True);check.toggled.connect(lambda value,k=key:self.scene.visible(k,value));pl.addWidget(check);self.layer_checks[key]=check
        self.search=QLineEdit();self.search.setPlaceholderText('Цооног хайх…');self.search.textChanged.connect(self.filter_holes);pl.addWidget(self.search)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['Цооног','Гүн, м']);self.tree.itemSelectionChanged.connect(self.select_hole);pl.addWidget(self.tree,1)
        self.info=QLabel('');self.info.setWordWrap(True);self.info.setTextFormat(Qt.TextFormat.PlainText);pl.addWidget(self.info)
        self.measure=QPushButton('Хоёр цэгийн зай хэмжих');self.measure.setCheckable(True);self.measure.toggled.connect(self.toggle_measure);pl.addWidget(self.measure)
        self.measure_label=QLabel('3D геометр дээр 2 цэг сонгоно.');self.measure_label.setWordWrap(True);pl.addWidget(self.measure_label)
        left.setWidget(panel);self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,left)
        right=QDockWidget('ОГТЛОЛЫН ТОХИРГОО',self);right.setMinimumWidth(220);rp=QWidget();form=QFormLayout(rp)
        self.slab=QCheckBox('Босоо зүсэлтийн шүүлтүүр');form.addRow(self.slab)
        self.angle=QDoubleSpinBox();self.angle.setRange(0,359.9);self.angle.setSuffix('°');self.angle.setSingleStep(5)
        self.offset=QDoubleSpinBox();self.offset.setRange(-100000,100000);self.offset.setSuffix(' м');self.offset.setSingleStep(10)
        self.width=QDoubleSpinBox();self.width.setRange(.1,200000);self.width.setValue(100);self.width.setSuffix(' м');self.width.setSingleStep(10)
        form.addRow('Нормалын азимут',self.angle);form.addRow('Төвөөс шилжилт',self.offset);form.addRow('Зүсэлтийн зузаан',self.width)
        note=QLabel('Шилжилт нь төслийн 3D эхээс хэмжигдэнэ. Нормал: хойноос цагийн зүүний дагуу. Сорьцгүй хэсэг саарал.');note.setWordWrap(True);note.setObjectName('muted');form.addRow(note)
        self.origin_label=QLabel();self.origin_label.setWordWrap(True);form.addRow(self.origin_label)
        for spin in (self.angle,self.offset,self.width):spin.valueChanged.connect(self.update_section)
        self.slab.toggled.connect(self.update_section)
        right.setWidget(rp);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,right)
        bottom=QDockWidget('ЦООНОГИЙН ӨГӨГДӨЛ',self)
        self.table=QTableWidget();self.table.setColumnCount(7);self.table.setHorizontalHeaderLabels(['Цооног','X / Зүүн, м','Y / Хойд, м','Z / Өндөр, м','Гүн, м','Азимут, °','Налуу, °'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setAlternatingRowColors(True);self.table.itemSelectionChanged.connect(self.select_table)
        bottom.setWidget(self.table);self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,bottom);self.resizeDocks([bottom],[170],Qt.Orientation.Vertical)

    def guard(self,callback):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:return callback()
        except (OSError,ValueError,TypeError,RuntimeError,KeyError,IndexError,OverflowError) as exc:
            QMessageBox.critical(self,'Үйлдэл амжилтгүй',str(exc));return False
        finally:QApplication.restoreOverrideCursor()

    def refresh(self):
        self.project.validate();self.title_label.setText(self.project.name)
        self.stats.setText(f'{len(self.project.collars):,} цооног\n{sum(h.depth for h in self.project.collars):,.1f} м өрөмдлөг\n{len(self.project.assays):,} сорьц • {len(self.project.surveys):,} хэмжилт')
        self.tree.blockSignals(True);self.tree.clear();self.table.blockSignals(True);self.table.setRowCount(len(self.project.collars))
        for i,h in enumerate(self.project.collars):
            self.tree.addTopLevelItem(QTreeWidgetItem([h.hole_id,f'{h.depth:,.1f}']))
            for j,value in enumerate((h.hole_id,h.x,h.y,h.z,h.depth,h.azimuth,h.dip)):
                self.table.setItem(i,j,QTableWidgetItem(value if isinstance(value,str) else f'{value:.2f}'))
        self.tree.blockSignals(False);self.table.blockSignals(False);self.info.setText('Цооног сонгож мэдээллийг харна уу.')
        self.scene.load(self.project);self.origin_label.setText('3D эх (м):\n'+ '\n'.join(f'{axis}: {value:,.2f}' for axis,value in zip('XYZ',self.scene.origin)))
        for k,c in self.layer_checks.items():self.scene.visible(k,c.isChecked())
        self.update_section();self.filter_holes(self.search.text());self.update_title()
        self.statusBar().showMessage(self.project.crs+' • Сургалтын / туршилтын хувилбар')

    def update_title(self):self.setWindowTitle(f'{"● " if self.dirty else ""}{self.project.name} — RAINYMINE {__version__}')
    def filter_holes(self,text):
        for i in range(self.tree.topLevelItemCount()):
            item=self.tree.topLevelItem(i);item.setHidden(text.casefold() not in item.text(0).casefold())
    def select_hole(self):
        items=self.tree.selectedItems()
        if not items:return
        name=items[0].text(0);self.show_hole(name)
    def select_table(self):
        row=self.table.currentRow()
        if row>=0 and self.table.item(row,0):self.show_hole(self.table.item(row,0).text())
    def show_hole(self,name):
        h=next(h for h in self.project.collars if h.hole_id==name);end=self.scene.paths[name].at(h.depth)
        self.info.setText(f'{h.hole_id}\nГүн: {h.depth:.2f} м\nАмсар Z: {h.z:.2f} м\nМөргөцөг Z: {end[2]:.2f} м\nСорьц: {sum(a.hole_id==name for a in self.project.assays)}\nЗамнал: '+('Minimum curvature' if any(s.hole_id==name for s in self.project.surveys) else 'Шулуун'))
        self.scene.select(name)
    def update_section(self,*args):
        if hasattr(self,'scene'):
            self.scene.set_section((self.angle.value(),self.offset.value(),self.width.value()) if self.slab.isChecked() else None)
    def toggle_measure(self,enabled):
        self.measure_mode=enabled;self.pick_points=[];self.measure_label.setText('Геометр дээр 2 цэг сонгоно.' if enabled else 'Хэмжилт зогссон.')
    def on_click(self,obj,event):
        if not self.measure_mode:return
        x,y=self.vtk.GetEventPosition();picker=vtk.vtkCellPicker();picker.SetTolerance(.008)
        if not picker.Pick(x,y,0,self.scene.renderer):return
        point=picker.GetPickPosition();self.pick_points.append(point)
        if len(self.pick_points)==2:
            a,b=self.pick_points;distance=math.dist(a,b);self.measure_label.setText(f'3D зай: {distance:,.3f} м\nΔZ: {b[2]-a[2]:,.3f} м');self.pick_points=[]
        else:self.measure_label.setText('Эхний цэг сонгогдлоо. Дараагийн цэгээ сонгоно уу.')

    def may_discard(self):
        if not self.dirty:return True
        result=QMessageBox.question(self,'Хадгалаагүй өөрчлөлт','Төслөө хадгалах уу?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if result==QMessageBox.StandardButton.Save:return bool(self.save())
        return result==QMessageBox.StandardButton.Discard
    def new(self):
        if self.may_discard():self.project=Project();self.path=None;self.dirty=False;self.refresh()
    def open_demo(self):
        if self.may_discard():self.project=demo();self.path=None;self.dirty=False;self.refresh()
    def open(self):
        if not self.may_discard():return
        path,_=QFileDialog.getOpenFileName(self,'Төсөл нээх','','RAINYMINE төсөл (*.rmine)')
        if path:
            def run():
                p=load_project(path);self.project=p;self.path=path;self.dirty=False;self.refresh();return True
            self.guard(run)
    def save(self,save_as=False):
        path=self.path if not save_as else None
        if not path:path,_=QFileDialog.getSaveFileName(self,'Төсөл хадгалах','Төсөл.rmine','RAINYMINE төсөл (*.rmine)')
        if not path:return False
        if not path.lower().endswith('.rmine'):path+='.rmine'
        def run():
            save_project(path,self.project);self.path=path;self.dirty=False;self.update_title();self.statusBar().showMessage('Хадгалсан: '+path);return True
        return self.guard(run)
    def backup(self):
        if not self.dirty or not self.path:return
        try:save_project(str(self.path)+'.autosave',self.project)
        except (OSError,ValueError):self.statusBar().showMessage('Автомат нөөц хадгалж чадсангүй. Ctrl+S ашиглана уу.')
    def import_data(self,kind):
        if kind=='collars' and self.project.collars:
            if QMessageBox.question(self,'Амсрын сан солих','Амсар импортлоход одоогийн цооног, survey, сорьцын сан солигдоно. Үргэлжлүүлэх үү?')!=QMessageBox.StandardButton.Yes:return
        path,_=QFileDialog.getOpenFileName(self,'CSV импорт','','UTF-8 CSV (*.csv)')
        if not path:return
        def run():
            candidate=deepcopy(self.project)
            values={'collars':read_collars,'surveys':read_surveys,'assays':read_assays,'surface':read_surface}[kind](path)
            setattr(candidate,kind,values)
            if kind=='collars':candidate.surveys=[];candidate.assays=[]
            candidate.validate();self.project=candidate;self.dirty=True;self.refresh();self.statusBar().showMessage(f'CSV импортоллоо: {len(values):,} мөр • Өөрчлөлтөө хадгална уу.')
        self.guard(run)
    def add_hole(self):
        dlg=QDialog(self);dlg.setWindowTitle('Цооног нэмэх');form=QFormLayout(dlg);name=QLineEdit();form.addRow('Цооногийн нэр',name);inputs={}
        for key,label,low,high,default in [('x','X / Зүүн, м',-1e9,1e9,0),('y','Y / Хойд, м',-1e9,1e9,0),('z','Z / Өндөр, м',-1e9,1e9,0),('depth','Гүн, м',.01,20000,200),('azimuth','Азимут, °',0,359.99,0),('dip','Налуу, °',-90,0,-90)]:
            spin=QDoubleSpinBox();spin.setRange(low,high);spin.setDecimals(2);spin.setValue(default);inputs[key]=spin;form.addRow(label,spin)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Нэмэх');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Болих');form.addRow(buttons)
        def add():
            def run():
                candidate=deepcopy(self.project);candidate.collars.append(Collar(name.text().strip(),**{k:s.value() for k,s in inputs.items()}));candidate.validate();self.project=candidate;self.dirty=True;self.refresh();dlg.accept()
            self.guard(run)
        buttons.accepted.connect(add);buttons.rejected.connect(dlg.reject);dlg.exec()
    def settings(self):
        dlg=QDialog(self);dlg.setWindowTitle('Төслийн тохиргоо');form=QFormLayout(dlg)
        name=QLineEdit(self.project.name);crs=QLineEdit(self.project.crs);units=QComboBox();units.addItems(['%','g/t','ppm']);units.setCurrentText(self.project.grade_unit)
        form.addRow('Нэр',name);form.addRow('CRS тайлбар',crs);form.addRow('Агуулгын нэгж',units)
        note=QLabel('CRS нь зөвхөн тайлбар. Координат хөрвүүлэхгүй. Нэгж өөрчлөхөд тоон утга хөрвөхгүй.');note.setWordWrap(True);form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
        def apply():
            def run():
                p=deepcopy(self.project);p.name=name.text();p.crs=crs.text();p.grade_unit=units.currentText();p.validate();self.project=p;self.dirty=True;self.refresh();dlg.accept()
            self.guard(run)
        buttons.accepted.connect(apply);buttons.rejected.connect(dlg.reject);dlg.exec()
    def validate_data(self):
        def run():
            self.project.validate()
            for h in self.project.collars:Trajectory(h,self.project.surveys).at(h.depth)
            unsurveyed=sum(not any(s.hole_id==h.hole_id for s in self.project.surveys) for h in self.project.collars)
            QMessageBox.information(self,'Өгөгдөл шалгалаа',f'Бүтэц ба замналын тооцоо зөв.\nSurvey-гүй {unsurveyed} цооног шулуунаар дүрслэгдэнэ.\n\nГеологийн чанар, лабораторийн QA/QC, CRS нийцлийг энэ шалгалт батлахгүй.')
        self.guard(run)
    def destination(self,title,ext):
        path,_=QFileDialog.getSaveFileName(self,title,'Rainymine.'+ext,f'{ext.upper()} (*.{ext})')
        return path+('.'+ext if path and not path.lower().endswith('.'+ext) else '')
    def export_paths(self):
        path=self.destination('Замнал экспорт','csv')
        if path:self.guard(lambda:export_trajectories(path,self.project))
    def export_png(self):
        path=self.destination('3D зураг хадгалах','png')
        if path:self.guard(lambda:self.scene.screenshot(path))
    def export_vtp(self):
        path=self.destination('3D геометр хадгалах','vtp')
        if path:
            def run():
                self.scene.export_vtp(path)
                atomic_write(path+'.origin.json',__import__('json').dumps({'offset_xyz':self.scene.origin,'units':'metres','crs':self.project.crs,'note':'Add offset_xyz to VTP points to recover project coordinates.'},ensure_ascii=False,indent=2))
            self.guard(run)
    def composites(self):
        length,ok=QInputDialog.getDouble(self,'Композит','Уртаар жигнэсэн композитын урт, м',5,.1,1000,2)
        if not ok:return
        path=self.destination('Композит CSV экспорт','csv')
        if path:
            def run():
                rows=composite_assays(self.project,length);write_records(path,rows,('hole_id','from_m','to_m','grade','support_m','coverage'))
                QMessageBox.information(self,'Композит гаргалаа',f'{len(rows)} интервал.\nХоосон хэсгийг 0 гэж тооцоогүй. Coverage баганаар бүрхэлтийг шалгана уу.\nАгуулгын нэгж: {self.project.grade_unit}')
            self.guard(run)
    def report(self):
        from html import escape
        path=self.destination('Төслийн тайлан','html')
        if not path:return
        def run():
            p=self.project;rows=''.join(f'<tr><td>{escape(h.hole_id)}</td><td>{h.x:.2f}</td><td>{h.y:.2f}</td><td>{h.z:.2f}</td><td>{h.depth:.2f}</td></tr>' for h in p.collars)
            text=f'''<!doctype html><html lang="mn"><meta charset="utf-8"><title>RAINYMINE тайлан</title><style>body{{font:15px Arial;max-width:1000px;margin:40px auto;color:#172337}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #ccd5df;padding:8px;text-align:left}}</style><h1>RAINYMINE — {escape(p.name)}</h1><p>{escape(p.crs)}</p><p>Цооног: {len(p.collars)} | Өрөмдлөг: {sum(h.depth for h in p.collars):,.2f} м | Сорьц: {len(p.assays)} | Нэгж: {escape(p.grade_unit)}</p><p>Туршилтын хувилбар. Энэ тайлан нь нөөцийн баталгаажсан үнэлгээ биш.</p><table><tr><th>Цооног</th><th>X, м</th><th>Y, м</th><th>Z, м</th><th>Гүн, м</th></tr>{rows}</table></html>'''
            atomic_write(path,text)
        self.guard(run)
    def help(self):
        QMessageBox.information(self,'RAINYMINE — Ашиглах заавар','1. Цооногийн амсар CSV импортлоно.\n2. Survey CSV, дараа нь сорьц CSV импортлоно.\n3. Гадаргын XYZ CSV импортлож TIN үүсгэнэ.\n4. 3D цонхыг эргүүлж, хүснэгтээс цооног сонгоно.\n5. Огтлолын нормал, шилжилт, зузааныг тохируулна.\n6. .rmine файлд төслөө хадгална.\n\nБүх координат нэг метрийн системд байна. X зүүн, Y хойд, Z дээш. Азимут хойноос цагийн зүүний дагуу. Dip −90 босоо доош.\n\nSurvey: minimum curvature; сүүлийн станцаас мөргөцөг хүртэл чиглэл тогтмол. Survey байхгүй бол амсрын чиглэлээр шулуун.\n\nЭнэ хувилбарт: блок модель, кригинг, нөөцийн ангилал, уурхайн оновчлол, Micromine форматын импорт ороогүй. Жишээ нь бодит орд биш.\n\nREADME.md болон examples хавтсаас форматыг харна уу.')
    def closeEvent(self,event):
        if self.may_discard():self.vtk.Finalize();event.accept()
        else:event.ignore()

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--screenshot');args=parser.parse_args()
    app=QApplication(sys.argv[:1]);app.setApplicationName('RAINYMINE');app.setOrganizationName('Rainy Studio')
    from PySide6.QtGui import QFont
    app.setFont(QFont('Segoe UI',10))
    asset_root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    if (asset_root/'assets'/'rainymine.ico').exists():app.setWindowIcon(QIcon(str(asset_root/'assets'/'rainymine.ico')))
    license_manager = None
    if not args.smoke:
        from .licensing import LicenseManager
        from .license_ui import LicenseDialog
        try:
            license_manager = LicenseManager()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(None, 'Лицензийн тохиргоо', str(exc))
            return 1
        if not license_manager.status().allowed:
            dialog = LicenseDialog(license_manager)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
    # VTK may log renderer errors without raising Python exceptions.
    # Smoke tests must fail on these errors rather than accepting a blank viewport.
    capture=vtk.vtkStringOutputWindow() if args.smoke else None
    if capture is not None:vtk.vtkOutputWindow.SetInstance(capture)
    from .advanced import AdvancedWorkbench
    window=AdvancedWorkbench();window.show()
    if license_manager is not None:
        from .license_ui import attach_licensing
        attach_licensing(window, license_manager)
    if args.smoke:
        def verify():
            try:
                assert window.scene.sources['holes'].GetNumberOfCells()>0
                from .packaged_checks import verify
                from .viewing import named_section
                window.change_layer('holes',{'opacity':.65})
                assert abs(window.scene.actors['holes'].GetProperty().GetOpacity()-.65)<1e-8
                window.project=named_section(window.project,'SMOKE',[90,0,100])
                window.scene.project=window.project
                assert 'hole_id' in window.scene.identify(window.scene.actors['holes'],0)
                assert 'block_index' in window.scene.identify(window.scene.actors['blocks'],0)
                h=window.project.collars[0];point=window.scene.local((h.x,h.y,h.z));renderer=window.scene.renderer
                renderer.SetWorldPoint(*point,1);renderer.WorldToDisplay();screen=renderer.GetDisplayPoint()
                window.vtk.SetEventPosition(round(screen[0]),round(screen[1]));window.on_click(None,None)
                assert window.picked_info.text()!='3D дээр цооног эсвэл блок дарж сонгоно.'
                meshes=verify(window.project)
                window.project.workspace.setdefault('meshes',[]).extend(meshes)
                window.refresh()
                assert window.scene.sources['mesh_0'].GetNumberOfCells()>0
                assert window.ribbon.count()>=6
                assert window.project.workspace.get('block_model')
                assert window.scene.sources['blocks'].GetNumberOfCells()>0
                window.toggle_view();window.show_hole(window.project.collars[0].hole_id)
                window.scene.set_section((90,0,100));window.scene.set_section(None)
                window.ribbon.setCurrentIndex(3)
                window.toggle_view()
                window.scene.view('iso')
                window.vtk.GetRenderWindow().Render()
                if capture is not None:
                    output=capture.GetOutput()
                    if 'ERROR' in output.upper() or 'ERR|' in output.upper():
                        raise RuntimeError('VTK rendering failed: '+output[-2000:])
                # Native WGL child windows are absent from QWidget.grab().
                # Verify the real framebuffer, then composite it into the UI image.
                QApplication.processEvents()
                window.centralWidget().layout().activate()
                QApplication.processEvents()
                from tempfile import TemporaryDirectory
                from PySide6.QtGui import QImage,QPainter
                from PySide6.QtCore import QPoint,QRect
                from vtkmodules.util.numpy_support import vtk_to_numpy
                with TemporaryDirectory() as folder:
                    capture_image=vtk.vtkWindowToImageFilter();capture_image.SetInput(window.vtk.GetRenderWindow());capture_image.ReadFrontBufferOff();window.vtk.GetRenderWindow().Render();capture_image.Update()
                    pixels=vtk_to_numpy(capture_image.GetOutput().GetPointData().GetScalars())
                    colored=((pixels[:,:3].max(axis=1)-pixels[:,:3].min(axis=1))>35).sum()
                    assert colored>100, 'Blank viewport: no colored geological geometry in framebuffer'
                    if args.screenshot:
                        path=str(Path(folder)/'viewport.png');window.scene.screenshot(path);pixmap=window.grab();painter=QPainter(pixmap)
                        origin=window.vtk.mapTo(window,QPoint(0,0));painter.drawImage(QRect(origin,window.vtk.size()),QImage(path));painter.end();pixmap.save(args.screenshot)
                window.dirty=False;window.close();app.exit(0)
            except Exception:
                import traceback;traceback.print_exc();app.exit(1)
        QTimer.singleShot(1500,verify)
    return app.exec()
