"""Linked picking, per-layer properties and reusable section navigation."""
from copy import deepcopy
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import (QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QTreeWidget,QTreeWidgetItem,QLabel,QPushButton,QSlider,QComboBox,QColorDialog,
    QDoubleSpinBox,QDialog,QDialogButtonBox,QInputDialog,QMessageBox,QToolButton)
from .workbench import Workbench,icon
from .viewing import DEFAULT_STYLE,styled_project,named_section

class NavigationWorkbench(Workbench):
    def __init__(self):
        self.active_layer=None;self.updating_layers=False
        super().__init__()
        for key,check in self.layer_checks.items():check.toggled.connect(lambda value,k=key:self.change_layer(k,{'visible':value}))
    def build_ui(self):
        super().build_ui()
        self.layer_dock=QDockWidget('3D ДАВХАРГА / PROPERTIES',self);self.layer_dock.setMinimumWidth(215)
        panel=QWidget();layout=QVBoxLayout(panel)
        self.layer_list=QTreeWidget();self.layer_list.setHeaderLabels(['Давхарга','Элемент']);self.layer_list.setMinimumHeight(120);layout.addWidget(self.layer_list,1)
        self.layer_list.itemChanged.connect(self.layer_checked);self.layer_list.currentItemChanged.connect(self.layer_selected)
        form=QFormLayout();self.opacity=QSlider(Qt.Orientation.Horizontal);self.opacity.setRange(0,100);self.opacity.sliderReleased.connect(lambda:self.change_layer(self.active_layer,{'opacity':self.opacity.value()/100}))
        self.representation=QComboBox();self.representation.addItems(['Бүтэн гадарга','Торон дүрслэл','Цэг']);self.representation.activated.connect(lambda i:self.change_layer(self.active_layer,{'representation':('surface','wireframe','points')[i]}))
        form.addRow('Тунгалагшил',self.opacity);form.addRow('Харагдац',self.representation);layout.addLayout(form)
        row=QHBoxLayout();color=QPushButton('Өнгө…');color.clicked.connect(self.choose_color);reset=QPushButton('Агуулгын өнгө');reset.clicked.connect(lambda:self.change_layer(self.active_layer,{'color':None}));row.addWidget(color);row.addWidget(reset);layout.addLayout(row)
        self.picked_info=QLabel('3D дээр цооног эсвэл блок дарж сонгоно.');self.picked_info.setWordWrap(True);self.picked_info.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.picked_info)
        self.layer_dock.setWidget(panel);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.layer_dock)
        page=QWidget();buttons=QHBoxLayout(page)
        for title,kind,callback in [('Давхаргын\nсамбар','grid',self.toggle_layers),('Огтлол\nхадгалах','file',self.save_section),('Огтлол\nнээх','surface',self.open_section),('Өмнөх\nогтлол','undo',lambda:self.step_section(-1)),('Дараах\nогтлол','surface',lambda:self.step_section(1)),('X / Y / Z\nзүсэлт','cube',self.slice_dialog)]:
            from .ribbon import RibbonButton
            button=RibbonButton();button.setIcon(icon(kind));button.setIconSize(QSize(24,24));button.setText(title);button.clicked.connect(lambda checked=False,cb=callback:cb());buttons.addWidget(button)
        from .support_ui import SupportDock
        self.support=SupportDock(self);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.support);self.support.hide()
        from .ribbon import RibbonButton
        help_button=RibbonButton();help_button.setIcon(icon('gear'));help_button.setText('Local AI\nТуслах');help_button.clicked.connect(lambda:self.support.setVisible(not self.support.isVisible()));buttons.addWidget(help_button)
        buttons.addStretch();self.ribbon.addTab(page,'3D хэрэгслүүд')
        menu=self.menuBar().addMenu('Огтлол');self.action(menu,'Өмнөх огтлол',lambda:self.step_section(-1),'PgUp');self.action(menu,'Дараах огтлол',lambda:self.step_section(1),'PgDown');self.action(menu,'Огтлол хадгалах',self.save_section)
    def refresh(self):
        super().refresh()
        for scene in (self.scene,self.secondary):
            if scene:scene.apply_styles()
        for key,check in self.layer_checks.items():
            style=self.project.workspace.get('layer_styles',{}).get(key,{})
            if 'visible' in style:check.blockSignals(True);check.setChecked(style['visible']);check.blockSignals(False)
        self.refresh_layers()
    def layer_name(self,key):
        fixed={'holes':'Цооног / сорьц','collars':'Амсрын цэгүүд','surface':'Гадаргын загвар','blocks':'Блок загвар'}
        if key in fixed:return fixed[key]
        if key.startswith('string_'):return self.project.workspace.get('strings',[])[int(key.split('_')[1])]['name']
        if key.startswith('mesh_'):return self.project.workspace.get('meshes',[])[int(key.split('_')[1])]['name']
        return key
    def refresh_layers(self):
        if not hasattr(self,'layer_list'):return
        self.updating_layers=True;self.layer_list.clear();current=None
        for key,actor in self.scene.actors.items():
            if key=='selected':continue
            source=self.scene.sources.get(key);item=QTreeWidgetItem([self.layer_name(key),str(source.GetNumberOfCells() if source else 0)]);item.setData(0,Qt.ItemDataRole.UserRole,key)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(0,Qt.CheckState.Checked if actor.GetVisibility() else Qt.CheckState.Unchecked);self.layer_list.addTopLevelItem(item)
            if key==self.active_layer:current=item
        self.layer_list.setCurrentItem(current or self.layer_list.topLevelItem(0));self.updating_layers=False;self.layer_selected(self.layer_list.currentItem())
    def layer_selected(self,item,*args):
        if not item or self.updating_layers:return
        self.active_layer=item.data(0,Qt.ItemDataRole.UserRole);actor=self.scene.actors[self.active_layer];style=self.project.workspace.get('layer_styles',{}).get(self.active_layer,{})
        self.opacity.setValue(round(actor.GetProperty().GetOpacity()*100));self.representation.setCurrentIndex(('surface','wireframe','points').index(style.get('representation','surface')))
    def layer_checked(self,item,column):
        if not self.updating_layers:self.change_layer(item.data(0,Qt.ItemDataRole.UserRole),{'visible':item.checkState(0)==Qt.CheckState.Checked})
    def change_layer(self,key,changes):
        if not key or self.updating_layers:return
        def run():
            effective={'visible':bool(self.scene.actors[key].GetVisibility()),**changes};candidate=styled_project(self.project,key,effective);self.project=candidate;self.dirty=True
            for scene in (self.scene,self.secondary):
                if scene:scene.project=candidate;scene.apply_styles();scene.window.Render()
            if key in self.layer_checks and 'visible' in changes:
                check=self.layer_checks[key];check.blockSignals(True);check.setChecked(changes['visible']);check.blockSignals(False)
            self.update_title();self.refresh_layers()
        self.guard(run)
    def choose_color(self):
        if not self.active_layer:return
        color=QColorDialog.getColor(parent=self,title='Давхаргын өнгө')
        if color.isValid():self.change_layer(self.active_layer,{'color':[color.redF(),color.greenF(),color.blueF()]})
    def toggle_layers(self):self.layer_dock.setVisible(not self.layer_dock.isVisible())
    def save_section(self):
        name,ok=QInputDialog.getText(self,'Огтлол хадгалах','Огтлолын нэр:')
        if ok:self.guard(lambda:self.commit(named_section(self.project,name,[self.angle.value(),self.offset.value(),self.width.value()])))
    def open_section(self):
        sections=self.project.workspace.get('sections',[]);index=self.choose('Хадгалсан огтлол',[s['name'] for s in sections])
        if index is not None:
            az,offset,width=sections[index]['values']
            for spin,value in ((self.angle,az),(self.offset,offset),(self.width,width)):spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
            self.slab.setChecked(True);self.update_section()
    def step_section(self,sign):
        self.slab.setChecked(True);self.offset.setValue(self.offset.value()+sign*self.width.value())
    def slice_dialog(self):
        model=self.project.workspace.get('block_model')
        if not model:QMessageBox.information(self,'Блокийн зүсэлт','Эхлээд блок модель үүсгэнэ үү.');return
        bounds=model['bounds'];positions=self.project.workspace.get('block_slice_positions',[(bounds[i]+bounds[i+3])/2 for i in range(3)])
        dlg=QDialog(self);dlg.setWindowTitle('Grid X / Y / Z зүсэлт — локал grid координат, метр');form=QFormLayout(dlg);spins=[]
        for i,axis in enumerate('XYZ'):
            spin=QDoubleSpinBox();spin.setDecimals(3);spin.setRange(bounds[i],bounds[i+3]-.001);spin.setSingleStep(model['size'][i]);spin.setValue(positions[i]);spins.append(spin);form.addRow(axis,spin)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);box.accepted.connect(dlg.accept);box.rejected.connect(dlg.reject);form.addRow(box)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            def run():
                p=deepcopy(self.project);p.workspace['block_slice_positions']=[s.value() for s in spins];p.workspace['block_display']='slices';self.commit(p)
            self.guard(run)
    def on_click(self,obj,event):
        if not self.measure_mode:
            import vtk
            x,y=self.vtk.GetEventPosition();picker=vtk.vtkCellPicker();picker.SetTolerance(.008)
            if picker.Pick(x,y,0,self.scene.renderer):
                info=self.scene.identify(picker.GetActor(),picker.GetCellId())
                if info:
                    if 'hole_id' in info:
                        self.show_hole(info['hole_id'])
                        for i in range(self.tree.topLevelItemCount()):
                            item=self.tree.topLevelItem(i)
                            if item.text(0)==info['hole_id']:self.tree.setCurrentItem(item);break
                        self.picked_info.setText('Сонгосон цооног: '+info['hole_id'])
                    elif 'block_index' in info:
                        self.picked_info.setText(self.block_selection_text(info['block_index'],info))
                    else:self.picked_info.setText(self.layer_name(info['layer'])+'\nCell: '+str(info['cell_id']))
                    self.active_layer=info['layer'];self.refresh_layers()
        super().on_click(obj,event)

    def block_selection_text(self,index,block):
        grade='—' if block.get('grade') is None else f"{block['grade']:,.3f}"
        variance='—' if block.get('variance') is None else f"{block['variance']:.6g}"
        return f"Блок #{index}\nX {block['x']:,.2f}  Y {block['y']:,.2f}\nZ {block['z']:,.2f}\nАгуулга: {grade} {self.project.grade_unit}\nVariance: {variance}\n{block.get('status','')}"

    def closeEvent(self,event):
        if hasattr(self,'support') and self.support.busy():
            self.support.cancel();event.ignore();return
        super().closeEvent(event)
        if event.isAccepted() and hasattr(self,'support'):self.support.shutdown()
