"""User-facing modelling, economic scenarios and external data exchange."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import QWidget,QHBoxLayout,QToolButton,QFileDialog,QMessageBox
from .navigation import NavigationWorkbench
from .workbench import icon
from .estimation import sample_support
from .implicit import implicit_surface
from .optimization import economic_pit,pit_mesh
from .exchange import xlsx_to_csv,read_stl,write_stl,database_snapshot
from .data_tools import SCHEMAS


class AdvancedWorkbench(NavigationWorkbench):
    def build_ui(self):
        super().build_ui()
        page=QWidget();row=QHBoxLayout(page)
        for text,kind,callback in [('RBF implicit\nгадарга','surface',self.implicit_dialog),
                 ('Pit\nоновчлол','pit',self.optimize_dialog),('Excel\nимпорт','grid',self.excel_dialog),
                 ('STL\nимпорт','cube',self.stl_import),('STL\nэкспорт','cube',self.stl_export),
                 ('Geobank / SQL\nунших','file',self.database_dialog)]:
            from .ribbon import RibbonButton
            b=RibbonButton();b.setText(text);b.setIcon(icon(kind));b.setIconSize(QSize(24,24))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.clicked.connect(lambda checked=False,cb=callback:cb());row.addWidget(b)
        row.addStretch();self.ribbon.addTab(page,'Загвар / оновчлол')

    def implicit_dialog(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Bounds авахын тулд эхлээд блок модель үүсгэнэ үү.')
            defaults={'Cutoff':.5,'Composite metres':10,'Resolution':31,'Smoothing':0,'Neighbors':32}
            defaults.update({p+' '+a:model['bounds'][j+i*3] for i,p in enumerate(('Min','Max')) for j,a in enumerate('XYZ')})
            settings=self.params('RBF агуулгын гадарга — structural/fault constraint байхгүй',defaults)
            if not settings:return
            project=deepcopy(self.project)
            bounds=[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ']
            def work(cancel):
                samples=sample_support(project,float(settings['Composite metres']))
                return implicit_surface(samples,bounds,float(settings['Cutoff']),int(settings['Resolution']),float(settings['Smoothing']),int(settings['Neighbors']),cancel=cancel)
            def apply(result):
                mesh,metadata=result;p=deepcopy(self.project);mesh['modelling']=metadata;p.workspace.setdefault('meshes',[]).append(mesh);self.commit(p)
                report=metadata['mesh_report']
                QMessageBox.information(self,'RBF гадарга',f"{len(mesh['faces'])} гурвалжин.\nBounds дотор extrapolation хийгдсэн; геологийн хяналт шаардлагатай.\nBoundary edges: {report.get('open_edges')}\nХаалттай, баталгаажсан хүдрийн solid гэж үзэхгүй.")
            self.launch_task('RBF гадарга…',work,apply)
        self.guard(run)

    def optimize_dialog(self):
        def run():
            model=self.project.workspace.get('block_model')
            if not model:raise ValueError('Эхлээд блок модель үүсгэнэ үү.')
            settings=self.params('Undiscounted pit — model хилээс гаднах stripping орохгүй',{
                'Density t/m3':2.7,'Price / grade-unit / tonne':100,'Recovery 0–1':.9,
                'Mining cost / tonne':3,'Processing cost / tonne':12,'Slope degrees':45})
            if not settings:return
            model=deepcopy(model)
            def work(cancel):
                result=economic_pit(model,*[float(settings[k]) for k in ('Density t/m3','Price / grade-unit / tonne','Recovery 0–1','Mining cost / tonne','Processing cost / tonne','Slope degrees')])
                if cancel():return None
                return result,pit_mesh(model,result['selected_indices']) if result['selected_indices'] else None
            def apply(output):
                result,mesh=output;p=deepcopy(self.project);p.workspace['pit_optimization']=result
                if mesh:p.workspace.setdefault('meshes',[]).append(mesh)
                self.commit(p);self.show_rows('Pit scenario — инженерийн хяналт хийгдээгүй',[{k:v for k,v in result.items() if k!='selected_indices'}])
            self.launch_task('Pit оновчлол…',work,apply)
        self.guard(run)

    def excel_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,'Excel values импорт','','Excel (*.xlsx)')
        if not path:return
        settings=self.params('Excel импорт',{'Төрөл':list(SCHEMAS),'Sheet':'Sheet1'})
        if not settings:return
        with TemporaryDirectory() as folder:
            csv_path=Path(folder)/(Path(path).stem+'.csv')
            if self.guard(lambda:xlsx_to_csv(path,csv_path,settings['Sheet'])) is not False:
                self.import_data(settings['Төрөл'],str(csv_path))

    def stl_import(self):
        path,_=QFileDialog.getOpenFileName(self,'STL импорт — нэгж/CRS автоматаар хөрвөхгүй','','STL (*.stl)')
        if path:
            def run():
                p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(read_stl(path));self.commit(p)
            self.guard(run)

    def stl_export(self):
        meshes=self.project.workspace.get('meshes',[]);index=self.choose('STL экспорт',[m['name'] for m in meshes])
        if index is not None:
            path=self.destination('STL экспорт — project metre coordinates','stl')
            if path:self.guard(lambda:write_stl(path,meshes[index]))

    def database_dialog(self):
        def run():
            settings=self.params('Geobank SQL Server — DBA canonical views шаардлагатай',{'Windows ODBC DSN':'RainymineGeobank','SQL schema':'dbo'})
            if not settings:return
            if QMessageBox.question(self,'Анхдагч сан солих',
                'Collar, survey, assay, lithology дөрвөн санг snapshot-оор солино. Блок модель цэвэрлэгдэнэ.\nSELECT-only account ба SNAPSHOT тохируулсан DSN шаардлагатай. Үргэлжлүүлэх үү?')!=QMessageBox.StandardButton.Yes:return
            project=deepcopy(self.project)
            def apply(candidate):
                self.commit(candidate);QMessageBox.information(self,'SQL snapshot','Дөрвөн хүснэгт уншиж шалгалаа. Холболтын нууц мэдээллийг төсөлд хадгалаагүй.')
            self.launch_task('SQL snapshot…',lambda cancel:database_snapshot(project,settings['Windows ODBC DSN'],settings['SQL schema']),apply)
        self.guard(run)
