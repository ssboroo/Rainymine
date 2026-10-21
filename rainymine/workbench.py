"""Professional ribbon workbench connecting experimental geology workflows."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import csv
import json
import math
from PySide6.QtCore import Qt,QSize,QByteArray
from PySide6.QtGui import QIcon,QPixmap,QPainter,QAction,QKeySequence
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QPushButton,QLabel,QMessageBox,
    QFileDialog,QInputDialog,QTabWidget,QWidget,QGroupBox,QToolButton,QToolBar,QDockWidget,
    QCheckBox,QProgressDialog,QSplitter,QHeaderView,QApplication,QScrollArea)
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from .ui import Window
from .scene import Scene
from .core import Project,Lithology,finite,write_records,atomic_write
from .data_tools import History,SCHEMAS,save_mapping_profile,mapping_profile,csv_preview,mapped_import,rows_to_values,parse_cell,transform_project,qaqc_assays,evaluate_controls
from .geometry import read_obj,write_obj,read_dxf,write_dxf,mesh_report,constrained_tin,validate_polygon
from .estimation import estimate_model,sample_support,cross_validate,experimental_variogram,fit_variogram,tonnage_grade
from .planning import pit_benches,underground_drive,schedule,tasks_from_blocks,haul_route,haul_capacity,optimize_schedule,economic_tasks
from .domains import fault_patch
from .benchmark import compare_reference

LIGHT='''
QWidget {font-family:"Segoe UI";font-size:11px;color:#243146;}
QMainWindow,QDialog {background:#f2f3f7;}
QMenuBar {background:#3b315d;color:white;padding:3px;}
QMenuBar::item:selected {background:#665381;}
QMenu {background:white;border:1px solid #ccd0da;}
QMenu::item:selected {background:#e7e1f3;}
QToolBar {background:#f4f4f7;border:0;spacing:3px;}
QToolButton {background:transparent;border:1px solid transparent;padding:4px;color:#243146;}
QToolButton:hover {background:#e7e1f3;border:1px solid #b7a7cf;border-radius:3px;}
QPushButton {background:#f4f4f8;border:1px solid #bfc5d0;border-radius:3px;padding:7px 10px;}
QPushButton:hover {background:#e7e1f3;border-color:#8972b2;}
QTabWidget::pane {border:1px solid #ccd0da;background:#f7f7fa;}
QTabBar::tab {background:#ddd9e7;padding:7px 14px;border:0;color:#453b59;}
QTabBar::tab:selected {background:#f7f7fa;color:#5a3586;border-top:2px solid #8061a7;}
QGroupBox {border:0;border-right:1px solid #d5d7df;margin-top:0;padding:0 5px 0 5px;}
QGroupBox::title {subcontrol-origin:padding;subcontrol-position:bottom center;color:#737888;padding:1px;}
QDockWidget::title {background:#e7e5ed;color:#3d3b4c;padding:5px;}
QDockWidget {background:#f7f7fa;}
QTreeWidget,QTableWidget {background:white;alternate-background-color:#f5f6f9;color:#26364a;border:1px solid #d0d5de;gridline-color:#e0e3e9;selection-background-color:#ded7ed;selection-color:#29213a;}
QHeaderView::section {background:#eceef3;color:#46536a;border:0;border-right:1px solid #d5d9e1;padding:5px;}
QLineEdit,QDoubleSpinBox,QComboBox {background:white;color:#243146;border:1px solid #bcc3ce;padding:5px;selection-background-color:#dad1e8;}
QCheckBox {padding:3px;spacing:5px;}
QStatusBar {background:#f0eff4;color:#5a6475;border-top:1px solid #d4d7df;}
QLabel#brand {font-size:15px;font-weight:700;color:#614589;}
QLabel#muted {color:#748095;}
QScrollBar:vertical {background:#f0f1f5;width:11px;}
QScrollBar::handle:vertical {background:#bcc3cf;min-height:30px;}
'''

from .icons import icon

class GridDialog(QDialog):
    def __init__(self,parent,columns,rows,title):
        super().__init__(parent);self.setWindowTitle(title);self.resize(980,520);self.columns=columns
        layout=QVBoxLayout(self);self.table=QTableWidget(len(rows),len(columns));self.table.setHorizontalHeaderLabels(columns);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i,row in enumerate(rows):
            for j,k in enumerate(columns):self.table.setItem(i,j,QTableWidgetItem('' if row.get(k) is None else str(row.get(k,''))))
        layout.addWidget(self.table);buttons=QHBoxLayout()
        for label,fn in [('Мөр нэмэх',lambda:self.table.insertRow(self.table.rowCount())),('Сонгосон мөр устгах',self.remove)]:
            b=QPushButton(label);b.clicked.connect(fn);buttons.addWidget(b)
        layout.addLayout(buttons);self.box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Save).setText('Шалгаж хадгалах');self.box.button(QDialogButtonBox.StandardButton.Cancel).setText('Болих');self.box.rejected.connect(self.reject);layout.addWidget(self.box)
    def remove(self):
        for i in sorted({x.row() for x in self.table.selectedIndexes()},reverse=True):self.table.removeRow(i)
    def rows(self):return [{k:self.table.item(i,j).text().strip() if self.table.item(i,j) else '' for j,k in enumerate(self.columns)} for i in range(self.table.rowCount())]

class Workbench(Window):
    def __init__(self):
        self.history=History();self.secondary=None;self.computing=False
        super().__init__();self.setStyleSheet(LIGHT)
        self.scene.renderer.SetBackground(1,1,1);self.scene.renderer.GradientBackgroundOff()
        self.secondary=Scene(self.vtk2.GetRenderWindow());self.vtk2.Initialize();self.secondary.renderer.SetBackground(1,1,1);self.secondary.renderer.GradientBackgroundOff()
        for key,check in self.layer_checks.items():check.toggled.connect(lambda value,k=key:self.secondary.visible(k,value))
        self.enrich_demo();self.refresh()
    def enrich_demo(self):
        if not self.project.name.startswith('ЖИШЭЭ'):return
        for h in self.project.collars:
            self.project.lithology.extend([Lithology(h.hole_id,0,h.depth*.35,'Хурдас'),Lithology(h.hole_id,h.depth*.35,h.depth*.7,'Хүдэржилт'),Lithology(h.hole_id,h.depth*.7,h.depth,'Боржин')])
        self.project.workspace['block_model']=estimate_model(self.project,[499950,5299950,1100,500450,5300400,1500],[50,50,50],{'method':'idw','minimum':2,'neighbors':8,'radii':[220,220,130],'composite_length':10,'minimum_coverage':1})
        self.project.workspace['block_display']='slices'
        self.layer_checks['surface'].setChecked(False)
    def build_ui(self):
        super().build_ui()
        for bar in self.findChildren(QToolBar):bar.hide()
        self.ribbon=QTabWidget();self.ribbon.setMaximumHeight(146);self.ribbon.setMinimumHeight(146)
        def tab(name,groups):
            page=QWidget();row=QHBoxLayout(page);row.setContentsMargins(3,2,3,0);row.setSpacing(2)
            for title,actions in groups:
                group=QGroupBox(title);items=QHBoxLayout(group);items.setContentsMargins(4,0,4,18);items.setSpacing(0)
                for label,kind,fn in actions:
                    from .ribbon import RibbonButton
                    b=RibbonButton();b.setIcon(icon(kind));b.setIconSize(QSize(24,24));b.setText(label);b.clicked.connect(lambda checked=False,f=fn:f());items.addWidget(b)
                row.addWidget(group)
            row.addStretch();self.ribbon.addTab(page,name)
        tab('Төсөл',[('Файл',[('Шинэ\nтөсөл','file',self.new),('Төсөл\nнээх','file',self.open),('Хадгалах','file',self.save)]),('Өгөгдөл',[('Багана\nтохируулах','grid',lambda:self.import_data('collars')),('CRS\nхөрвүүлэх','pick',self.crs_dialog),('Хүснэгт\nзасвар','grid',self.edit_grid)]),('Түүх',[('Буцаах','undo',self.undo),('Сэргээх','undo',self.redo),('Тохиргоо','gear',self.settings)])])
        tab('Өрөмдлөг',[('Импорт',[('Амсар','holes',lambda:self.import_data('collars')),('Survey','holes',lambda:self.import_data('surveys')),('Сорьц','chart',lambda:self.import_data('assays')),('Литологи','holes',lambda:self.import_data('lithology'))]),('Чанар',[('Сорьцын\nбүрхэлт','grid',self.qaqc),('Стандарт /\nBlank / Dup','chart',self.controls),('Шалгах','gear',self.validate_data)]),('Гаргалгаа',[('Композит','grid',self.composites),('Замнал CSV','file',self.export_paths)])])
        tab('Геологи / DTM',[('Геометр',[('String /\nPolygon','polygon',self.edit_string),('Геометр\nзасах','pick',self.edit_existing_string),('Гадарга\nXYZ','surface',lambda:self.import_data('surface'))]),('DTM / Solid',[('Breakline\nTIN','surface',self.build_tin),('Mesh\nшалгах','cube',self.check_mesh)]),('Солилцоо',[('OBJ\nимпорт','cube',self.import_obj),('OBJ\nэкспорт','cube',self.export_obj),('DXF\nимпорт','polygon',self.import_dxf),('DXF\nэкспорт','polygon',self.export_dxf)])])
        tab('Блок модель',[('Модель',[('Блок модель\nүүсгэх','cube',self.block_dialog),('Домэйн\nPolygon','polygon',self.edit_string),('Блок CSV\nэкспорт','grid',self.export_blocks),('3 зүсэлт /\nБүх блок','cube',self.block_display)]),('Үнэлгээ',[('Variogram\nба fit','chart',self.variogram),('Cross-\nvalidation','chart',self.cross_validation),('External\nBenchmark','chart',self.external_benchmark),('Fault\nPlane','surface',self.add_fault),('Density /\nCutoff','cube',self.resource_report)])])
        tab('Уурхай',[('Загварын prototype',[('Ил уурхайн\nBench','pit',self.pit),('Далд уурхайн\nМалталт','cube',self.drive)]),('Төлөвлөлт',[('Capacity\nSchedule','grid',self.schedule_dialog),('Зам /\nТээвэр','surface',self.haul_dialog),('MILP\nОновчлол','chart',self.schedule_milp_dialog),('Төслийн\nтайлан','file',self.report)])])
        tab('Харагдац',[('Камер',[('3D','cube',lambda:self.scene.view('iso')),('Дээрээс','grid',lambda:self.scene.view('top')),('Урдаас','surface',lambda:self.scene.view('north')),('Төвлөрүүлэх','pick',lambda:self.scene.reset())]),('Ажлын орчин',[('Хоёр\nviewport','grid',self.toggle_view),('Агуулга /\nЛитологи','holes',self.color_mode),('Зай\nхэмжих','pick',lambda:self.measure.setChecked(not self.measure.isChecked()))]),('Экспорт',[('PNG зураг','file',self.export_png),('VTP\nгеометр','cube',self.export_vtp),('Заавар','file',self.help)])])
        rb=QToolBar('Ribbon');rb.setMovable(False);rb.addWidget(self.ribbon);self.addToolBar(Qt.ToolBarArea.TopToolBarArea,rb)
        # Large white scientific viewport; the second view is an optional plan window.
        layout=self.centralWidget().layout();layout.removeWidget(self.vtk)
        self.split=QSplitter(Qt.Orientation.Horizontal);self.split.addWidget(self.vtk);self.vtk2=QVTKRenderWindowInteractor();self.split.addWidget(self.vtk2);self.vtk2.hide();layout.insertWidget(1,self.split,1)
        docks=self.findChildren(QDockWidget);left=docks[0];properties=docks[1];properties.setWindowTitle('ШИНЖ ЧАНАР / ОГТЛОЛ');self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,properties);self.splitDockWidget(left,properties,Qt.Orientation.Vertical)
        for dock in (left,properties):
            content=dock.widget();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);dock.setWidget(scroll);dock.setMinimumHeight(150)
        self.resizeDocks([left,properties],[300,240],Qt.Orientation.Vertical);self.resizeDocks([left],[265],Qt.Orientation.Horizontal)
        self.coordinates=QLabel('X —   Y —   Z —');self.statusBar().addPermanentWidget(self.coordinates)
        edit=self.menuBar().addMenu('Засвар');self.action(edit,'Буцаах',self.undo,'Ctrl+Z');self.action(edit,'Сэргээх',self.redo,'Ctrl+Y')
    def refresh(self):
        super().refresh()
        for text in (self.scene.legend.GetLabelTextProperty(),self.scene.legend.GetTitleTextProperty()):text.SetColor(.15,.18,.24)
        self.scene.window.Render()
        if self.secondary:
            self.secondary.mode=self.scene.mode;self.secondary.load(self.project);self.secondary.view('top');self.update_section()
            for text in (self.secondary.legend.GetLabelTextProperty(),self.secondary.legend.GetTitleTextProperty()):text.SetColor(.15,.18,.24)
            for key,check in self.layer_checks.items():self.secondary.visible(key,check.isChecked())
        if hasattr(self,'coordinates'):self.coordinates.setText((self.project.crs_code or 'Локал метр')+'  |  X —  Y —  Z —')
    def guard(self,callback):
        before=deepcopy(self.project);result=super().guard(callback)
        if result is False and self.project!=before:
            self.project=before;self.refresh()
        elif self.project!=before and self.dirty:self.history.apply(before,self.project,'Өгөгдөл / геометр / тооцоо')
        return result
    def commit(self,candidate):
        candidate.validate();self.project=candidate;self.dirty=True;self.refresh()
    def undo(self):
        if self.computing:return
        self.project=self.history.undo(self.project);self.dirty=True;self.refresh()
    def redo(self):
        if self.computing:return
        self.project=self.history.redo(self.project);self.dirty=True;self.refresh()
    def new(self):
        old=self.project;super().new()
        if self.project is not old:self.history=History()
    def open(self):
        old=self.project;super().open()
        if self.project is not old:self.history=History()
    def open_demo(self):
        old=self.project;super().open_demo()
        if self.project is not old:self.history=History();self.enrich_demo();self.refresh()
    def update_section(self,*args):
        super().update_section(*args)
        if self.secondary:self.secondary.set_section((self.angle.value(),self.offset.value(),self.width.value()) if self.slab.isChecked() else None)
    def show_hole(self,name):
        super().show_hole(name)
        if self.secondary:self.secondary.select(name)
    def toggle_view(self):
        self.vtk2.setVisible(not self.vtk2.isVisible())
        if self.vtk2.isVisible():self.split.setSizes([700,500]);self.secondary.window.Render()
    def color_mode(self):
        self.scene.mode='lithology' if self.scene.mode=='assay' else 'assay';self.refresh()
        if self.scene.mode=='lithology':self.info.setText('Литологийн код:\n'+'\n'.join(f'{i+1}: {r}' for i,r in enumerate(sorted({a.rock for a in self.project.lithology}))))
    def on_click(self,obj,event):
        import vtk
        if hasattr(self,'scene'):
            x,y=self.vtk.GetEventPosition();picker=vtk.vtkCellPicker();picker.SetTolerance(.008)
            if picker.Pick(x,y,0,self.scene.renderer):
                local=picker.GetPickPosition();p=[a+b for a,b in zip(local,self.scene.origin)];self.coordinates.setText('  '.join(f'{a}: {b:,.3f}' for a,b in zip('XYZ',p)))
        super().on_click(obj,event)
    def closeEvent(self,event):
        if self.computing:event.ignore();return
        super().closeEvent(event)
        if event.isAccepted():self.vtk2.Finalize()
    def choose(self,title,items):
        if not items:QMessageBox.information(self,title,'Сонгох өгөгдөл алга.');return None
        name,ok=QInputDialog.getItem(self,title,'Сонгоно уу:',items,0,False);return items.index(name) if ok else None
    def params(self,title,defaults):
        dlg=QDialog(self);dlg.setWindowTitle(title);dlg.resize(660,640);layout=QVBoxLayout(dlg)
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();form=QFormLayout(content);scroll.setWidget(content);layout.addWidget(scroll);inputs={}
        for name,value in defaults.items():
            if isinstance(value,list):w=QComboBox();w.addItems(value)
            else:w=QLineEdit(str(value))
            inputs[name]=w;form.addRow(name,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);b.button(QDialogButtonBox.StandardButton.Ok).setText('Тооцох / хадгалах');b.button(QDialogButtonBox.StandardButton.Cancel).setText('Болих');b.accepted.connect(dlg.accept);b.rejected.connect(dlg.reject);layout.addWidget(b)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return None
        return {k:(w.currentText() if isinstance(w,QComboBox) else w.text()) for k,w in inputs.items()}
    def show_rows(self,title,rows):
        if not rows:QMessageBox.information(self,title,'Өгөгдөл / анхааруулга алга.');return
        columns=list(dict.fromkeys(k for row in rows for k in row));dlg=GridDialog(self,columns,rows,title);dlg.box.button(QDialogButtonBox.StandardButton.Save).setText('CSV экспорт')
        dlg.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        def save():
            path=self.destination(title,'csv')
            if path:self.guard(lambda:write_records(path,rows,columns))
        dlg.box.accepted.connect(save);dlg.exec()
    def import_data(self,kind,path=None):
        if path is None:path,_=QFileDialog.getOpenFileName(self,'CSV импорт — багана тохируулах','','CSV (*.csv)')
        if not path:return
        from .dh_import import NAMES
        if Path(path).name.lower() in NAMES and hasattr(self,'dh_import_dialog'):
            self.dh_import_dialog(str(Path(path).parent));return
        def run():
            headers,preview,delimiter=csv_preview(path);dlg=QDialog(self);dlg.setWindowTitle('Импортын багана тохируулах');dlg.resize(760,520);layout=QVBoxLayout(dlg);form=QFormLayout();selectors={}
            for field in SCHEMAS[kind]:
                combo=QComboBox();combo.addItems(headers)
                if field in headers:combo.setCurrentText(field)
                selectors[field]=combo;form.addRow(field,combo)
            profile_selector=QComboBox();profile_selector.addItem('— Гараар тохируулах —')
            profile_selector.addItems(sorted(self.project.workspace.get('mapping_profiles',{}).get(kind,{})))
            profile_button=QPushButton('Загвар хэрэглэх')
            def apply_profile():
                def apply():
                    mapping=mapping_profile(self.project,profile_selector.currentText(),kind,headers)
                    for field,value in mapping.items():selectors[field].setCurrentText(value)
                self.guard(apply)
            profile_button.clicked.connect(apply_profile)
            profile_row=QHBoxLayout();profile_row.addWidget(profile_selector);profile_row.addWidget(profile_button)
            layout.addLayout(profile_row)
            profile_name=QLineEdit();profile_name.setMaxLength(80);profile_name.setPlaceholderText('Нэр өгвөл амжилттай импортын дараа загвар хадгална')
            form.addRow('Загварын нэр',profile_name)
            layout.addLayout(form);table=QTableWidget(len(preview),len(headers));table.setHorizontalHeaderLabels(headers)
            for i,row in enumerate(preview):
                for j,h in enumerate(headers):table.setItem(i,j,QTableWidgetItem(str(row.get(h,''))))
            layout.addWidget(table);layout.addWidget(QLabel('Бүх мөр зөв болсон үед импорт бүхлээрээ орно. Буруу мөрийг чимээгүй алгасахгүй.'))
            box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);box.accepted.connect(dlg.accept);box.rejected.connect(dlg.reject);layout.addWidget(box)
            if dlg.exec()!=QDialog.DialogCode.Accepted:return
            rows,report=mapped_import(path,kind,{f:c.currentText() for f,c in selectors.items()},delimiter)
            if report['rejected']:
                self.show_rows('Импортын алдаа — импорт хийгдээгүй',report['issues']);return
            p=deepcopy(self.project);setattr(p,kind,rows_to_values(kind,rows))
            if kind=='collars' and (p.surveys or p.assays or p.lithology or p.structure or p.geotech):
                if QMessageBox.question(self,'Амсрын сан солих','Survey, сорьц, литологи, бүтэц, геотехникийн санг цэвэрлэж амсрыг солих уу?')!=QMessageBox.StandardButton.Yes:return
                p.surveys=[];p.assays=[];p.lithology=[];p.structure=[];p.geotech=[]
            if profile_name.text().strip():
                p=save_mapping_profile(p,profile_name.text(),kind,report['mapping'])
            p.workspace.setdefault('imports',[]).append(report);self.commit(p)
            QMessageBox.information(self,'Импорт дууслаа',f"{report['accepted']} мөр. SHA256 ба баганын mapping төсөлд хадгалагдлаа.")
        self.guard(run)
    def edit_grid(self):
        kinds=list(SCHEMAS);index=self.choose('Хүснэгт засвар',kinds)
        if index is None:return
        kind=kinds[index];values=getattr(self.project,kind)
        rows=[dict(zip(('x','y','z'),v)) if kind=='surface' else asdict(v) for v in values]
        dlg=GridDialog(self,SCHEMAS[kind],rows,'Өгөгдөл засвар — '+kind)
        def save():
            def run():
                parsed=[]
                for row in dlg.rows():parsed.append({k:parse_cell(kind,k,v) for k,v in row.items()})
                p=deepcopy(self.project);setattr(p,kind,rows_to_values(kind,parsed));self.commit(p);dlg.accept()
            self.guard(run)
        dlg.box.accepted.connect(save);dlg.exec()
    def crs_dialog(self):
        params=self.params('Оффлайн CRS хөрвүүлэх',{'Эх CRS':self.project.crs_code or 'EPSG:4326','Зорилтот CRS':'EPSG:32648'})
        if params:self.guard(lambda:self.commit(transform_project(self.project,params['Эх CRS'],params['Зорилтот CRS'])))
    def qaqc(self):self.guard(lambda:self.show_rows('Сорьцгүй интервал / coverage',qaqc_assays(self.project)))
    def controls(self):
        params=self.params('QA/QC хяналтын хязгаар',{'Blank limit':.05,'Duplicate RPD limit':.2,'Standard Z limit':3})
        if not params:return
        path,_=QFileDialog.getOpenFileName(self,'sample_id,type,measured,expected,sd баганатай CSV','','CSV (*.csv)')
        if path:
            def run():
                with open(path,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
                result=evaluate_controls(rows,float(params['Blank limit']),float(params['Duplicate RPD limit']),float(params['Standard Z limit']))
                import hashlib
                p=deepcopy(self.project);p.workspace['qaqc_controls']={'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'limits':params,'results':result};self.commit(p);self.show_rows('QA/QC — өгөгдөл устгаагүй',result)
            self.guard(run)
    def edit_string(self,index=None):
        strings=self.project.workspace.get('strings',[]);old=strings[index] if index is not None else {'name':'Domain / String','points':[],'closed':True}
        fields=self.params('String / Polygon',{'Нэр':old['name'],'Төрөл':['Polygon','String'] if old.get('closed') else ['String','Polygon']})
        if not fields:return
        dlg=GridDialog(self,('x','y','z'),[dict(zip(('x','y','z'),p)) for p in old['points']],'XYZ оройнууд — эхний цэгийг сүүлд давтахгүй')
        def save():
            def run():
                s={'name':fields['Нэр'],'closed':fields['Төрөл']=='Polygon','points':[[float(r[k]) for k in ('x','y','z')] for r in dlg.rows()]};p=deepcopy(self.project);ss=p.workspace.setdefault('strings',[])
                if index is None:ss.append(s)
                else:ss[index]=s
                self.commit(p);dlg.accept()
            self.guard(run)
        dlg.box.accepted.connect(save);dlg.exec()
    def edit_existing_string(self):
        index=self.choose('Геометр засвар',[s['name'] for s in self.project.workspace.get('strings',[])])
        if index is not None:self.edit_string(index)
    def import_obj(self):
        path,_=QFileDialog.getOpenFileName(self,'Triangulated OBJ импорт','','OBJ (*.obj)')
        if path:
            def run():p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(read_obj(path));self.commit(p)
            self.guard(run)
    def export_obj(self):
        meshes=self.project.workspace.get('meshes',[]);i=self.choose('OBJ экспорт',[m['name'] for m in meshes])
        if i is not None:
            path=self.destination('OBJ экспорт','obj')
            if path:self.guard(lambda:write_obj(path,meshes[i]))
    def import_dxf(self):
        path,_=QFileDialog.getOpenFileName(self,'DXF импорт','','DXF (*.dxf)')
        if path:
            def run():
                result,unsupported=read_dxf(path);p=deepcopy(self.project)
                for k in ('strings','meshes'):p.workspace.setdefault(k,[]).extend(result[k])
                self.commit(p)
                if unsupported:QMessageBox.information(self,'Дэмжигдээгүй DXF entity',str(unsupported))
            self.guard(run)
    def export_dxf(self):
        path=self.destination('DXF экспорт','dxf')
        if path:self.guard(lambda:write_dxf(path,self.project.workspace))
    def build_tin(self):
        def run():
            mesh=constrained_tin(self.project.surface,self.project.workspace.get('strings',[]));p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(mesh);self.commit(p)
        self.guard(run)
    def check_mesh(self):
        meshes=self.project.workspace.get('meshes',[]);i=self.choose('Mesh топологи',[m['name'] for m in meshes])
        if i is not None:self.guard(lambda:self.show_rows('Mesh — self-intersection хараахан шалгахгүй',[mesh_report(meshes[i])]))
    def estimator_params(self):
        result=self.params('Үнэлгээ — search / covariance / block support',{'Арга':['idw','kriging','nearest','simple_kriging'],'Neighbors':12,'Minimum':3,'Radius X':200,'Radius Y':200,'Radius Z':100,'Search azimuth':90,'Search dip':0,'Search roll':0,'Max samples per hole':64,'Minimum holes':1,'Top cut (blank = none)':'','IDW power':2,'Variogram model':['spherical','exponential','gaussian'],'Nugget':0,'Partial sill':1,'Known mean (SK)':0,'Range metres':100,'Covariance':['Isotropic','Anisotropic'],'Variogram range X':100,'Variogram range Y':100,'Variogram range Z':50,'Variogram azimuth':90,'Variogram dip':0,'Variogram roll':0,'Block support':['Point','2 × 2 × 2','3 × 3 × 3','4 × 4 × 4'],'Composite metres':5,'Minimum coverage':1})
        if not result:return None
        params={'method':result['Арга'],'neighbors':int(result['Neighbors']),'minimum':int(result['Minimum']),'radii':[float(result['Radius '+a]) for a in 'XYZ'],'search_angles':[float(result['Search '+a]) for a in ('azimuth','dip','roll')],'power':float(result['IDW power']),'nugget':float(result['Nugget']),'partial_sill':float(result['Partial sill']),'range_m':float(result['Range metres']),'composite_length':float(result['Composite metres']),'minimum_coverage':float(result['Minimum coverage'])}
        params['variogram_model']=result['Variogram model']
        params['known_mean']=float(result['Known mean (SK)'])
        params.update(max_per_hole=int(result['Max samples per hole']),minimum_holes=int(result['Minimum holes']),top_cut=float(result['Top cut (blank = none)']) if result['Top cut (blank = none)'].strip() else None)
        n=1 if result['Block support']=='Point' else int(result['Block support'][0]);params['discretization']=[n,n,n]
        if result['Covariance']=='Anisotropic':
            params['variogram_ranges']=[float(result['Variogram range '+a]) for a in 'XYZ']
            params['variogram_angles']=[float(result['Variogram '+a]) for a in ('azimuth','dip','roll')]
        params['faults']=deepcopy(self.project.workspace.get('faults',[]))
        return params
    def block_dialog(self):
        def run():
            parameters=self.estimator_params()
            if not parameters:return
            coords=[(h.x,h.y,h.z) for h in self.project.collars]
            if not coords:raise ValueError('Эхлээд цооног импортлоно уу.')
            low=[min(p[i] for p in coords)-50 for i in range(3)];low[2]-=250;high=[max(p[i] for p in coords)+50 for i in range(3)]
            settings=self.params('Блокийн bounds, хэмжээ — метр',{'Min X':low[0],'Min Y':low[1],'Min Z':low[2],'Max X':high[0],'Max Y':high[1],'Max Z':high[2],'Size X':50,'Size Y':50,'Size Z':20,'Grid azimuth':90,'Grid dip':0,'Grid roll':0,'Sub-block levels':0,'Домэйн':['Бүх талбай']+[s['name'] for s in self.project.workspace.get('strings',[]) if s.get('closed')]})
            if not settings:return
            parameters['grid_angles']=[float(settings['Grid '+a]) for a in ('azimuth','dip','roll')]
            parameters['subblock_levels']=int(settings['Sub-block levels'])
            domain=next((s for s in self.project.workspace.get('strings',[]) if s['name']==settings['Домэйн'] and s.get('closed')),None)
            progress=QProgressDialog('Блокийн агуулга тооцож байна…','Цуцлах',0,100,self);progress.setWindowModality(Qt.WindowModality.ApplicationModal);progress.setMinimumDuration(0);self.computing=True
            def update(i,n):progress.setValue(int(i/n*100));QApplication.processEvents()
            try:model=estimate_model(self.project,[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ'],[float(settings['Size '+a]) for a in 'XYZ'],parameters,domain,cancel=progress.wasCanceled,progress=update)
            finally:self.computing=False;progress.close()
            p=deepcopy(self.project);p.workspace['block_model']=model;p.workspace.pop('block_slice_positions',None);self.commit(p)
            QMessageBox.information(self,'Блок модель',f"{len(model['blocks'])} блок.\nНөөцийн ангилалгүй. Support: {model['support']}.")
        self.guard(run)
    def block_display(self):
        def run():
            p=deepcopy(self.project);p.workspace['block_display']='blocks' if p.workspace.get('block_display','slices')=='slices' else 'slices';self.commit(p)
        self.guard(run)
    def chart(self,title,rows,xkey,ykey,reference=False):
        from PySide6.QtCharts import QChart,QChartView,QScatterSeries,QLineSeries
        if not rows:return
        dlg=QDialog(self);dlg.setWindowTitle(title);dlg.resize(850,560);layout=QVBoxLayout(dlg);chart=QChart();chart.setTitle(title);series=QScatterSeries();series.setName(ykey);series.setMarkerSize(6)
        for r in rows:series.append(float(r[xkey]),float(r[ykey]))
        chart.addSeries(series)
        if reference:
            line=QLineSeries();line.setName('y = x');lo=min(min(r[xkey],r[ykey]) for r in rows);hi=max(max(r[xkey],r[ykey]) for r in rows);line.append(lo,lo);line.append(hi,hi);chart.addSeries(line)
        chart.createDefaultAxes();chart.axes(Qt.Orientation.Horizontal)[0].setTitleText(xkey);chart.axes(Qt.Orientation.Vertical)[0].setTitleText(ykey);layout.addWidget(QChartView(chart));dlg.exec()
    def export_blocks(self):
        model=self.project.workspace.get('block_model')
        if not model:QMessageBox.information(self,'Блок модель','Эхлээд блок модель үүсгэнэ үү.');return
        angles=model.get('grid_angles',[90,0,0]);origin=model.get('grid_origin',model['bounds'][:3])
        rows=[dict(b,**{'grid_'+a:v for a,v in zip(('azimuth','dip','roll'),angles)},**{'origin_'+a:v for a,v in zip('xyz',origin)}) for b in model['blocks']]
        self.show_rows('Блокийн атрибут — UNCLASSIFIED',rows)
    def cross_validation(self):
        def run():
            params=self.estimator_params()
            if not params:return
            result=cross_validate(sample_support(self.project,params['composite_length'],params['minimum_coverage']),params)
            p=deepcopy(self.project);p.workspace['cross_validation']=result;self.commit(p)
            summary={k:v for k,v in result.items() if k!='rows'};QMessageBox.information(self,'Leave-one-hole-out validation',json.dumps(summary,ensure_ascii=False,indent=2));self.chart('Observed / Estimated — leave-one-hole-out',result['rows'],'observed','estimated',True);self.chart('Residuals',result['rows'],'observed','error');self.show_rows('Observed / estimated / residual',result['rows'])
        self.guard(run)
    def variogram(self):
        def run():
            fields=self.params('Experimental variogram',{'Mode':['Isotropic','Directional'],'Azimuth':90,'Dip':0,'Tolerance degrees':22.5,'Bandwidth metres':100,'Lag metres':20,'Lags':15,'Composite metres':5})
            if not fields:return
            direction=None if fields['Mode']=='Isotropic' else {'azimuth':float(fields['Azimuth']),'dip':float(fields['Dip']),'tolerance':float(fields['Tolerance degrees']),'bandwidth':float(fields['Bandwidth metres'])}
            result=experimental_variogram(sample_support(self.project,float(fields['Composite metres'])),float(fields['Lag metres']),int(fields['Lags']),direction,self.project.workspace.get('faults',[]))
            if len(result['rows'])>=3:
                result['fit']=fit_variogram(result['rows'])
                result['fit']['model']='spherical; '+fields['Mode'].lower()+'; exploratory fit'
            p=deepcopy(self.project);p.workspace['variogram']=result;self.commit(p);self.chart(fields['Mode']+' experimental variogram',result['rows'],'distance','semivariance');self.show_rows('Variogram lag / semivariance',result['rows'])
            if 'fit' in result:QMessageBox.information(self,'Spherical model fit',json.dumps(result['fit'],indent=2))
        self.guard(run)
    def help(self):
        QMessageBox.information(self,'RAINYMINE — Ажлын дараалал',
            '1. Collar → Survey → Assay / Lithology CSV импортлоно. Баганын загварыг нэрлэж хадгалж болно.\n'
            '2. Геометр/блок үүсгэхээс өмнө CRS-ийг метрийн проекцод хөрвүүлнэ.\n'
            '3. Композитын coverage, QA/QC болон чиглэлтэй вариограммыг шалгана.\n'
            '4. Үнэлгээнд search, covariance ranges/angles, top cut, hole limits, block support-оо тохируулна.\n'
            '5. Grid rotation нь bounds-ийн minimum XYZ цэгийг тойрно. Slice нь grid-ийн локал тэнхлэгтэй.\n'
            '6. Cross-validation нь withheld hole-ийг бүрэн хассан point-support шалгалт.\n'
            '7. Density/cutoff тайлан гаргаж .rmine төсөлд хадгална.\n\n'
            'Azimuth хойноос цагийн зүүний дагуу; dip дээш эерэг. Search болон covariance тусдаа тохиргоотой.\n'
            'Discretized block support нь midpoint quadrature approximation; composite midpoint-ууд point support хэвээр.\n'
            'Sub-block нь finest-cell centre ангиллаар заагийг ойролцоо дүрсэлнэ. Fault нь infinite plane barrier; displacement байхгүй.\n'
            'Замын gradient/fleet cycle, optional-task MILP болон external CSV benchmark нь тусдаа workflow.\n'
            'Sub-block / эргэлттэй grid-ийн schedule дэмжигдээгүй. Бүх үр дүн UNCLASSIFIED.\n'
            'README.md / ACCEPTANCE.md-д бодит хязгаар, баталгаажуулалтын төлөв бий.')

    def resource_report(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Эхлээд блок модель үүсгэнэ үү.')
            fields=self.params('Tonnage / Grade — UNCLASSIFIED',{'Density t/m³':2.7,'Cutoffs':'.2,.5,1,2'})
            if not fields:return
            rows=tonnage_grade(model,float(fields['Density t/m³']),[float(x) for x in fields['Cutoffs'].split(',')]);p=deepcopy(self.project);p.workspace['tonnage_grade']=rows;self.commit(p);self.show_rows('Tonnage-grade — мэргэжлийн баталгаа аваагүй',rows)
        self.guard(run)
    def pit(self):
        def run():
            f=self.params('Тойрог bench design — prototype',{'Center X':500200,'Center Y':5300200,'Bottom radius':100,'Bottom Z':1200,'Bench height':10,'Benches':10,'Face angle degrees':60,'Berm width':5})
            if not f:return
            mesh,strings,report=pit_benches([float(f['Center X']),float(f['Center Y'])],float(f['Bottom radius']),float(f['Bottom Z']),float(f['Bench height']),int(f['Benches']),float(f['Face angle degrees']),float(f['Berm width']))
            p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(mesh);p.workspace.setdefault('strings',[]).extend(strings);p.workspace.setdefault('design_reports',[]).append(report);self.commit(p)
        self.guard(run)
    def drive(self):
        def run():
            f=self.params('Шулуун далд малталт — prototype',{'Start X':500000,'Start Y':5300000,'Start Z':1300,'End X':500200,'End Y':5300000,'End Z':1310,'Width':5,'Height':4})
            if not f:return
            mesh,report=underground_drive([float(f['Start '+a]) for a in 'XYZ'],[float(f['End '+a]) for a in 'XYZ'],float(f['Width']),float(f['Height']));p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(mesh);p.workspace.setdefault('design_reports',[]).append(report);self.commit(p)
        self.guard(run)
    def schedule_dialog(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Эхлээд блок модель үүсгэнэ үү.')
            f=self.params('Capacity schedule — heuristic',{'Density t/m³':2.7,'Cutoff':.5,'Mining tonnes/period':1000000,'Processing tonnes/period':500000,'Periods':24})
            if not f:return
            result=schedule(tasks_from_blocks(model,float(f['Density t/m³']),float(f['Cutoff'])),float(f['Mining tonnes/period']),float(f['Processing tonnes/period']),int(f['Periods']));p=deepcopy(self.project);p.workspace['schedule']=result;self.commit(p)
            QMessageBox.information(self,'Schedule',f"Төлөвлөсөн: {len(result['rows'])}; төлөвлөгдөөгүй: {len(result['unscheduled'])}.\nGreedy heuristic; global optimization, налуугийн өргөтгөсөн precedence, haulage/stockpile хараахан байхгүй.")
            self.show_rows('Capacity schedule',result['rows'])
            if result['unscheduled']:self.show_rows('Төлөвлөгдөөгүй task / шалтгаан',result['unscheduled'])
        self.guard(run)

    def add_fault(self):
        def run():
            f=self.params('Planar fault barrier — displacement байхгүй',{'Нэр':'Fault 1','X':500200,'Y':5300200,'Z':1300,'Normal X':1,'Normal Y':0,'Normal Z':0,'Guide extent metres':200})
            if not f:return
            fault={'name':f['Нэр'],'point':[float(f[a]) for a in 'XYZ'],'normal':[float(f['Normal '+a]) for a in 'XYZ']}
            patch=fault_patch(fault,float(f['Guide extent metres']));p=deepcopy(self.project)
            p.workspace.setdefault('faults',[]).append(fault);p.workspace.setdefault('meshes',[]).append(patch);self.commit(p)
        self.guard(run)

    def haul_dialog(self):
        def run():
            strings=[s for s in self.project.workspace.get('strings',[]) if not s.get('closed')]
            i=self.choose('Замын төв шугам — эхлээд XYZ String үүсгэнэ',[s['name'] for s in strings])
            if i is None:return
            f=self.params('Polyline haul route / constant-speed fleet',{'Width metres':12,'Maximum gradient %':10,'Payload tonnes':40,'Trucks':3,'Loaded km/h':20,'Empty km/h':30,'Load minutes':3,'Dump minutes':1,'Queue minutes':1,'Shift hours':8,'Utilization':.8})
            if not f:return
            route=haul_route(strings[i]['points'],float(f['Width metres']),float(f['Maximum gradient %']))
            capacity=haul_capacity(route,float(f['Payload tonnes']),int(f['Trucks']),float(f['Loaded km/h']),float(f['Empty km/h']),float(f['Load minutes']),float(f['Dump minutes']),float(f['Queue minutes']),float(f['Shift hours']),float(f['Utilization']))
            p=deepcopy(self.project);p.workspace.setdefault('haul_scenarios',[]).append({'string':deepcopy(strings[i]),'route':route,'capacity':capacity});self.commit(p)
            self.show_rows('Замын сегментүүд',route['segments']);self.show_rows('Fleet capacity — average cycle approximation',[capacity])
        self.guard(run)

    def schedule_milp_dialog(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Эхлээд world-axis parent model үүсгэнэ үү.')
            f=self.params('Economic MILP — optional tasks / precedence',{'Density t/m³':2.7,'Cutoff':.5,'Metal price / tonne metal':8000,'Mining cost / tonne rock':3,'Processing cost / tonne ore':8,'Haul cost / tonne rock':1,'Recovery':.9,'Mining tonnes/period':1000000,'Processing tonnes/period':500000,'Periods':12,'Discount per period':.01,'Solver seconds':10})
            if not f:return
            tasks=economic_tasks(model,float(f['Density t/m³']),float(f['Cutoff']),self.project.grade_unit,float(f['Metal price / tonne metal']),float(f['Mining cost / tonne rock']),float(f['Processing cost / tonne ore']),float(f['Recovery']),float(f['Haul cost / tonne rock']))
            result=optimize_schedule(tasks,float(f['Mining tonnes/period']),float(f['Processing tonnes/period']),int(f['Periods']),float(f['Discount per period']),float(f['Solver seconds']))
            result['assumptions']=f;result['grade_unit']=self.project.grade_unit;result['model_run_sha256']=model.get('run_sha256')
            p=deepcopy(self.project);p.workspace['optimization']=result;self.commit(p)
            QMessageBox.information(self,'MILP үр дүн',json.dumps({k:v for k,v in result.items() if k not in ('rows','unscheduled','assumptions')},ensure_ascii=False,indent=2));self.show_rows('MILP schedule',result['rows'])
        self.guard(run)

    def external_benchmark(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Эхлээд model үүсгэнэ үү.')
            path,_=QFileDialog.getOpenFileName(self,'Гадаад reference — x,y,z,grade CSV','','CSV (*.csv)')
            if not path:return
            f=self.params('External numerical comparison — review pending',{'Coordinate tolerance metres':.01,'Grade absolute tolerance':.001,'Grade relative tolerance':.01})
            if not f:return
            result=compare_reference(model,path,float(f['Coordinate tolerance metres']),float(f['Grade absolute tolerance']),float(f['Grade relative tolerance']))
            p=deepcopy(self.project);p.workspace['external_benchmark']=result;self.commit(p)
            QMessageBox.information(self,'Харьцуулалт — хараат бус баталгаа биш',json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2));self.show_rows('Reference errors',result['rows'])
        self.guard(run)
