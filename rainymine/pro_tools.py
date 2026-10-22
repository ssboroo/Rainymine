"""Professional workflow commands, connected to native geometry and bounded data readers."""
from copy import deepcopy
from pathlib import Path
import csv
import numpy as np
from PySide6.QtWidgets import QFileDialog,QMessageBox,QDialog,QVBoxLayout,QLabel,QPushButton,QHBoxLayout
from .foundation_ui import FoundationTools


class ProTools(FoundationTools):
    def build_pro_menu(self):
        self._engineering_tasks=[];self._preview_dialogs=[];self._gizmo=None
        menu=self.menuBar().addMenu('Мэргэжлийн хэрэгсэл')
        groups=[('Блок өгөгдөл',[('Micromine / CSV блок импорт…',self.block_csv_import),('Гадаад блок геометр / агуулга харьцуулах…',self.block_reference_check)]),('DH өгөгдөл',[('DH CSV багц импорт…',self.dh_import_dialog),('DH эх хүснэгт / CSV экспорт…',self.dh_source_browser),('DH сорьцын элемент солих…',self.dh_change_channel)]),('Нээлттэй солилцоо',[('OMF 2.0-beta.1 экспорт…',self.omf_export),('GeoPackage экспорт…',self.gpkg_export),('GeoPackage импорт…',self.gpkg_import),('CSV / CAD + metadata багц…',self.exchange_bundle)]),('CAD / Solid',[('Boolean union / intersection / difference…',self.solid_boolean),('Mesh repair…',self.solid_repair),('Шилжүүлэх / эргүүлэх / scale…',self.transform_dialog),('3D gizmo — сонгосон mesh…',self.start_gizmo),('Vertex / segment snap…',self.snap_dialog)]),
                ('Файл / GIS',[('Surpac STR импорт…',self.surpac_import),('Surpac STR экспорт…',self.surpac_export),('Surpac ASCII DTM импорт…',self.surpac_dtm_import),('SHP импорт…',self.shapefile_import),('GeoTIFF DEM импорт…',self.dem_import),('LAS/LAZ шүүлт ба экспорт…',self.lidar_export),('DWG → DXF adapter…',self.dwg_import)]),
                ('Геологи / Үнэлгээ',[('Муруй хагарлын сүлжээ JSON…',self.fault_network_import),('Contact / trend / fault RBF…',self.contact_rbf),('Литологийн fault/trend RBF…',self.lithology_rbf),('Indicator kriging…',self.indicator_dialog),('Олон шаттай үнэлгээ…',self.multipass_dialog),('Variogram family fit…',self.family_fit)]),
                ('Уурхайн зураг төсөл',[('Спираль ramp…',self.ramp_dialog),('Шугамаар малталтын сүлжээ…',self.network_dialog),('Өрөмдлөгийн ring / fan…',self.ring_dialog),('Stope box MILP…',self.stope_dialog)]),
                ('Төлөвлөлт',[('Pit RF хувилбар / үе шат…',self.nested_pit_dialog),('Олборлолт + feed blend MILP…',self.joint_schedule)]),
                ('Том өгөгдөл',[('LAS / LAZ GPU preview…',self.lidar_preview),('Parquet GPU block preview…',self.large_blocks)])]
        for name,commands in groups:
            submenu=menu.addMenu(name)
            for title,callback in commands:
                action=self.action(submenu,title,lambda cb=callback:self.guard(cb));action.setProperty('toolCategory',name)
                from .icons import semantic_icon,icon
                action.setIcon(semantic_icon(title,icon('gear')))
        self.build_foundation_menu(menu)

    def fault_network_import(self):
        import json
        from .fault_network import FaultNetwork,fault_mesh
        path,_=QFileDialog.getOpenFileName(self,'Муруй / хавтгай хагарлын DAG','','Fault network (*.json)')
        if not path:return
        if Path(path).stat().st_size>1_000_000:raise ValueError('Fault JSON exceeds 1 MB')
        payload=json.loads(Path(path).read_text(encoding='utf-8'))
        faults=payload['faults'];bounds=payload['bounds'];resolution=payload.get('resolution',25)
        def work(cancel):
            network=FaultNetwork(faults)
            meshes=[fault_mesh(network,i,bounds,resolution,cancel) for i in range(len(faults))]
            return meshes
        def apply(meshes):
            p=deepcopy(self.project);p.workspace['faults']=faults
            p.workspace['meshes']=[m for m in p.workspace.get('meshes',[]) if m.get('role')!='fault_guide']+meshes
            for mesh in p.workspace['meshes']:
                if mesh.get('role') in ('implicit_contact','implicit_grade'):mesh['stale_after_fault_edit']=True
            model=p.workspace.get('block_model')
            if model:
                for block in model['blocks']:
                    block.update(grade=None,variance=None,status='fault_network_changed')
                    for key in ('kriging_efficiency','slope_of_regression','block_variance'):block.pop(key,None)
                model.pop('run_sha256',None);model['faults']=deepcopy(faults)
            self.commit(p)
            self.show_rows('Хагарлын сүлжээ — агуулгыг дахин үнэлнэ',[
                {'name':f['name'],'kind':f.get('kind','plane'),'active_if':f.get('active_if',{}),
                 'slip':f.get('slip',[0,0,0]),'geological_review':False} for f in faults])
        self.launch_task('Хагарлын RBF / DAG…',work,apply)

    def nested_pit_dialog(self):
        from .optimization import nested_pits,pit_mesh
        model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Эхлээд блок модель үүсгэнэ үү.')
        settings=self.params('Pit RF — MILP 5000 / pseudoflow 50000; инженерийн хяналт шаардлагатай',{
            'Density t/m3':2.7,'Price / grade-unit / tonne':100,'Recovery 0–1':.9,
            'Mining cost / tonne':3,'Processing cost / tonne':12,'Slope degrees':45,
            'RF start':.30,'RF end':1.20,'RF step':.05,'Backend':['milp','pseudoflow']})
        if not settings:return
        model=deepcopy(model)
        keys=('Density t/m3','Price / grade-unit / tonne','Recovery 0–1',
              'Mining cost / tonne','Processing cost / tonne','Slope degrees','RF start','RF end','RF step')
        def work(cancel,progress):
            report=nested_pits(model,*[float(settings[k]) for k in keys],cancel=cancel,progress=progress,backend=settings['Backend'])
            meshes=[]
            for scenario in report['scenarios']:
                if cancel():raise RuntimeError('Pit RF cancelled.')
                if scenario['selected_indices']:
                    mesh=pit_mesh(model,scenario['selected_indices'])
                    mesh['name']=f"RF {scenario['revenue_factor']:.2f} pit"
                    meshes.append(mesh)
            return report,meshes
        def apply(result):
            report,meshes=result;p=deepcopy(self.project)
            p.workspace.setdefault('meshes',[]).extend(meshes)
            p.workspace.setdefault('engineering_runs',[]).append({'tool':'Pit RF sensitivity','report':report})
            self.commit(p)
            self.show_rows('Pit-by-pit RF / инженерийн хяналт хийгдээгүй',[
                {k:v for k,v in row.items() if k in ('revenue_factor','net_value','base_price_net_value',
                'selected_blocks','mined_tonnes','processed_tonnes','nested_with_previous')}
                for row in report['scenarios']])
            self.chart('Pit-by-pit — base price',report['scenarios'],'revenue_factor','base_price_net_value')
        self.launch_task('Pit RF…',work,apply,with_progress=True)

    def block_csv_import(self):
        from .block_csv import read_block_csv, KEYS
        path,_=QFileDialog.getOpenFileName(self,'Блок CSV — parent / rotated / sub-block','','CSV (*.csv)')
        if not path:return
        if Path(path).stat().st_size>32_000_000:raise ValueError('CSV 32 MB-аас их байна.')
        with open(path,encoding='utf-8-sig',newline='') as stream:
            headers=next(csv.reader(stream),[])
        if not headers or len(headers)>256:raise ValueError('CSV header алга / хэт олон баганатай.')
        geometry_settings=self.params('CSV геометр — эргэлтийн эх тодорхойлолт',{'Geometry':['World-axis uniform parents','Explicit rotated / sub-block grid'],'Metadata rows after header':0})
        if not geometry_settings:return
        skip_rows=int(geometry_settings['Metadata rows after header'])
        geometry=None
        if geometry_settings['Geometry']=='Explicit rotated / sub-block grid':
            config=self.params('RAINYMINE ENU: azimuth хойноос CW; dip дээш эерэг; roll local X',{'Origin X':0,'Origin Y':0,'Origin Z':0,'Parent X':10,'Parent Y':10,'Parent Z':10,'Azimuth':90,'Dip':0,'Roll':0,'Orientation source':['RAINYMINE ENU','Explicit source axes / matrix JSON']})
            if not config:return
            geometry={'origin':[float(config['Origin '+a]) for a in 'XYZ'],'parent_size':[float(config['Parent '+a]) for a in 'XYZ'],'angles':[float(config[k]) for k in ('Azimuth','Dip','Roll')]}
            if config.get('Orientation source','RAINYMINE ENU')=='Explicit source axes / matrix JSON':
                converted=self.orientation_convert()
                if converted is None:return
                geometry['angles']=converted['angles'];geometry['source_orientation']=converted
        defaults={key:([key]+[h for h in headers if h!=key] if key in headers else headers) for key in KEYS}
        settings=self.params('Блокийн төв XYZ, хэмжээ DX/DY/DZ, агуулгын багана',defaults)
        if not settings:return
        attributes={};unused=[h for h in headers if h not in settings.values()]
        if unused:
            extra=self.params('Блокийн нэмэлт баганууд',{'Нягтын багана':['—']+unused,'Домэйны багана':['—']+unused,'Бусад багана':['Текстээр хадгалах','Оруулахгүй']})
            if not extra:return
            density=extra['Нягтын багана'];domain=extra['Домэйны багана']
            if density!='—':attributes['density']={'column':density,'kind':'number','unit':'t/m3'}
            if domain!='—':attributes['domain']={'column':domain,'kind':'text','unit':''}
            if density==domain and density!='—':raise ValueError('Нягт / домэйн тусдаа багана байна.')
            if extra['Бусад багана']=='Текстээр хадгалах':
                for column in unused:
                    if column not in (density,domain):attributes['source:'+column]={'column':column,'kind':'text','unit':''}
        if QMessageBox.question(self,'Импортын нөхцөл',
                'Эх CSV-ийн XYZ нь дэлхийн координат дахь төв, DX/DY/DZ нь local grid хэмжээ метрээр өгөгдсөн үү?\n'
                'Геометр: '+geometry_settings['Geometry']+' · skipped metadata: '+str(skip_rows)+'\n'
                'CRS: '+self.project.crs_code+' · Агуулгын нэгж: '+self.project.grade_unit+'\n'
                'Нэгж / CRS автоматаар хөрвүүлэхгүй. Нэмэлт багана: '+str(len(attributes))+'\n'
                'Одоогийн блок модель солигдоно. Нөөцийн ангиллыг UNCLASSIFIED болгоно.')!=QMessageBox.StandardButton.Yes:return
        crs=self.project.crs_code;unit=self.project.grade_unit
        def apply(result):
            model,report=result
            p=deepcopy(self.project);p.workspace['block_model']=model
            p.workspace.pop('block_slice_positions',None)
            stale=('tonnage_grade','schedule','optimization','stope_box_optimization','joint_blend_schedule','external_benchmark')
            report['invalidated_workspace_results']=[key for key in stale if key in p.workspace]
            for key in stale:p.workspace.pop(key,None)
            p.workspace['block_display']='blocks'
            p.workspace.setdefault('engineering_runs',[]).append(report)
            from .core import project_text
            project_text(p)  # Reject unsavable desktop projects before replacing active data.
            self.commit(p)
            QMessageBox.information(self,'Блок CSV импорт',f"{report['blocks']} блок; {report['null_grades']} хоосон агуулга.\n"
                                    +'Оруулаагүй багана: '+', '.join(report['extra_columns']))
        self.launch_task('Блок CSV унших…',lambda cancel:read_block_csv(path,settings,crs,unit,cancel=cancel,geometry=geometry,skip_rows=skip_rows,attributes=attributes),apply)

    def block_reference_check(self):
        from .benchmark import compare_block_geometry
        model=deepcopy(self.project.workspace.get('block_model'))
        if not model:raise ValueError('Блок модель алга.')
        path,_=QFileDialog.getOpenFileName(self,'Гадаад reference — x,y,z,dx,dy,dz,grade','','CSV (*.csv)')
        if not path:return
        config=self.params('Reference RAINYMINE ENU өнцөг ба хүлцэл — инженерийн баталгаа биш',{'Reference azimuth':90,'Reference dip':0,'Reference roll':0,'Coordinate tolerance m':.001,'Dimension tolerance m':.001,'Grade absolute':.001,'Grade relative':.01})
        if not config:return
        angles=[float(config['Reference '+k]) for k in ('azimuth','dip','roll')]
        def apply(report):
            p=deepcopy(self.project);p.workspace.setdefault('engineering_runs',[]).append({'tool':'External block geometry reference','report':report})
            self.commit(p)
            QMessageBox.information(self,'Reference comparison','Numerical pass: '+str(report['numerical_pass'])+'\nIndependent review: PENDING')
            self.show_rows('Geometry / grade reference',report['rows'])
        self.launch_task('Reference харьцуулах…',lambda cancel:compare_block_geometry(model,path,angles,cancel=cancel,**dict(zip(('coordinate_tolerance','dimension_tolerance','grade_absolute','grade_relative'),[float(config[k]) for k in ('Coordinate tolerance m','Dimension tolerance m','Grade absolute','Grade relative')]))),apply)


    def add_mesh(self,mesh,report=None):
        p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(mesh)
        if report is not None:p.workspace.setdefault('engineering_runs',[]).append({'tool':mesh['name'],'report':report})
        self.commit(p)

    def selected_mesh(self,title):
        meshes=self.project.workspace.get('meshes',[]);index=self.choose(title,[m['name'] for m in meshes])
        return None if index is None else (index,deepcopy(meshes[index]))

    def solid_boolean(self):
        from .cad import boolean_mesh
        first=self.selected_mesh('Эх solid');second=self.selected_mesh('Хоёр дахь solid')
        if first is None or second is None:return
        settings=self.params('Watertight manifold Boolean',{'Үйлдэл':['union','intersection','difference']})
        if not settings:return
        def apply(result):
            mesh,report=result
            if mesh is None:QMessageBox.information(self,'Boolean','Үр дүн хоосон. Төсөл өөрчлөгдөөгүй.');return
            self.add_mesh(mesh,report)
        self.launch_task('Solid Boolean…',lambda cancel:boolean_mesh(first[1],second[1],settings['Үйлдэл']),apply)

    def solid_repair(self):
        from .cad import repair_mesh
        selected=self.selected_mesh('Засах mesh')
        if selected is None:return
        settings=self.params('Conservative repair — self-intersection засвар батлахгүй',{'Merge tolerance, м':.000001,'Fill hole radius, м (0=off)':0})
        if settings:self.launch_task('Mesh repair…',lambda cancel:repair_mesh(selected[1],float(settings['Merge tolerance, м']),float(settings['Fill hole radius, м (0=off)'])),lambda result:self.add_mesh(*result))

    def transform_dialog(self):
        from .cad import transform_geometry
        meshes=self.project.workspace.get('meshes',[]);strings=self.project.workspace.get('strings',[])
        entries=[('meshes',i,m) for i,m in enumerate(meshes)]+[('strings',i,s) for i,s in enumerate(strings)]
        index=self.choose('Transform объект',[kind+' · '+obj['name'] for kind,i,obj in entries])
        if index is None:return
        settings=self.params('Төвийг тойрсон affine — эхийг хадгалж copy үүсгэнэ',{'Move X':0,'Move Y':0,'Move Z':0,'Azimuth':90,'Dip':0,'Roll':0,'Scale X':1,'Scale Y':1,'Scale Z':1})
        if settings:
            kind,i,obj=entries[index];result=transform_geometry(obj,[float(settings['Move '+a]) for a in 'XYZ'],[float(settings[k]) for k in ('Azimuth','Dip','Roll')],[float(settings['Scale '+a]) for a in 'XYZ'])
            result['name']+=' · transformed';p=deepcopy(self.project);p.workspace[kind].append(result);self.commit(p)

    def start_gizmo(self):
        import vtk
        if self._gizmo:raise ValueError('Нээлттэй gizmo-г Apply/Cancel хийнэ үү.')
        key=self.active_layer
        if not key or not key.startswith('mesh_'):raise ValueError('Давхаргын жагсаалтаас mesh сонгоно уу.')
        index=int(key.split('_')[1]);actor=self.scene.actors[key];original=deepcopy(self.project.workspace['meshes'][index]);source=self.project;origin=np.asarray(self.scene.origin)
        representation=vtk.vtkBoxRepresentation();representation.SetPlaceFactor(1.05);representation.PlaceWidget(actor.GetBounds())
        widget=vtk.vtkBoxWidget2();widget.SetInteractor(self.vtk.GetRenderWindow().GetInteractor());widget.SetRepresentation(representation)
        from PySide6.QtCore import Qt
        dialog=QDialog(self);dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True);dialog.setWindowTitle('3D gizmo · '+original['name']);layout=QVBoxLayout(dialog);layout.addWidget(QLabel('Хүрээг зөөж, эргүүлж, хэмжээг өөрчилнө. Apply хийхэд copy хадгална.'))
        apply=QPushButton('Apply');cancel=QPushButton('Cancel');row=QHBoxLayout();row.addWidget(apply);row.addWidget(cancel);layout.addLayout(row)
        def move(obj,event):
            transform=vtk.vtkTransform();representation.GetTransform(transform);actor.SetUserTransform(transform);self.vtk.GetRenderWindow().Render()
        def cleanup(*args):
            widget.Off();actor.SetUserTransform(None);self._gizmo=None;self.vtk.GetRenderWindow().Render()
        def save():
            def run():
                if self.project is not source:raise ValueError('Төсөл өөрчлөгдсөн; gizmo-г дахин эхлүүлнэ үү.')
                transform=vtk.vtkTransform();representation.GetTransform(transform)
                matrix=transform.GetMatrix();linear=np.array([[matrix.GetElement(i,j) for j in range(3)] for i in range(3)])
                if abs(np.linalg.det(linear))<1e-10:raise ValueError('Gizmo singular transform.')
                mesh=deepcopy(original);mesh['vertices']=[(np.asarray(transform.TransformPoint(*(np.asarray(p)-origin)))+origin).tolist() for p in original['vertices']]
                if np.linalg.det(linear)<0:mesh['faces']=[list(reversed(f)) for f in mesh['faces']]
                mesh['name']+=' · gizmo';cleanup();dialog.close();self.add_mesh(mesh)
            self.guard(run)
        widget.AddObserver('InteractionEvent',move);apply.clicked.connect(save);cancel.clicked.connect(dialog.close);dialog.finished.connect(cleanup)
        self._gizmo=(widget,representation,dialog,actor);dialog.show();widget.On()

    def snap_dialog(self):
        from .cad import SnapIndex
        points=[];segments=[]
        for string in self.project.workspace.get('strings',[]):
            start=len(points);points.extend(string['points']);segments.extend([[start+i,start+i+1] for i in range(len(string['points'])-1)])
            if string.get('closed'):segments.append([len(points)-1,start])
        points.extend([[h.x,h.y,h.z] for h in self.project.collars])
        settings=self.params('Vertex / segment snapping — координат лавлах',{'X':0,'Y':0,'Z':0,'Tolerance, м':5})
        if settings:
            result=SnapIndex(points,segments).nearest([float(settings[k]) for k in 'XYZ'],float(settings['Tolerance, м']))
            self.show_rows('Snap result',[result or {'result':'Tolerance дотор объект алга.'}])

    def surpac_import(self):
        from .formats import read_surpac
        path,_=QFileDialog.getOpenFileName(self,'Surpac ASCII string','','Surpac (*.str)')
        if path:
            def apply(data):
                p=deepcopy(self.project);p.workspace.setdefault('strings',[]).extend(data['strings']);p.workspace.setdefault('engineering_runs',[]).append({'source':Path(path).name,'tool':'Surpac STR','isolated_points':data['isolated_points'],'header':data['header'],'crs':'user-confirmed project coordinates'})
                self.commit(p)
            if self.confirm_local_coordinates('STR'):
                self.launch_task('Surpac унших…',lambda cancel:read_surpac(path),apply)

    def confirm_local_coordinates(self,kind):
        return QMessageBox.question(self,'Координатын баталгаа',kind+'-ийн CRS metadata баталгаагүй. XYZ нь одоогийн төслийн метрийн координат мөн үү?')==QMessageBox.StandardButton.Yes

    def surpac_export(self):
        from .formats import write_surpac
        path=self.destination('Surpac string экспорт','str')
        if path:write_surpac(path,self.project.workspace.get('strings',[]))

    def surpac_dtm_import(self):
        from .formats import read_surpac_dtm
        path,_=QFileDialog.getOpenFileName(self,'Surpac ASCII DTM + ижил хавтасны STR','','DTM (*.dtm)')
        if path and self.confirm_local_coordinates('DTM'):self.launch_task('DTM унших…',lambda cancel:read_surpac_dtm(path),self.add_mesh)

    def check_source_crs(self,crs):
        from pyproj import CRS
        if not crs:return self.confirm_local_coordinates('Эх файл')
        source=CRS.from_user_input(crs)
        if not source.is_projected or any(abs(axis.unit_conversion_factor-1)>1e-9 for axis in source.axis_info[:2]):raise ValueError('Projected metre CRS шаардлагатай; эхлээд CRS хөрвүүлнэ үү.')
        if not self.project.crs_code or not source.equals(CRS.from_user_input(self.project.crs_code)):
            raise ValueError('Эх файлын CRS '+source.to_string()+' төслийн CRS-тэй таарахгүй. CRS-ээ зөв тохируулж дахин импортлоно уу.')
        return True

    def shapefile_import(self):
        from .formats import read_shapefile
        path,_=QFileDialog.getOpenFileName(self,'SHP + SHX + DBF + PRJ','','Shapefile (*.shp)')
        if path:
            def apply(data):
                if not self.check_source_crs(data['crs']):return
                p=deepcopy(self.project);p.workspace.setdefault('strings',[]).extend(data['strings']);p.workspace.setdefault('engineering_runs',[]).append({'tool':'SHP','source':Path(path).name,'attributes':data['attributes'],'points':data['points'],'z_assumed_zero':data['z_assumed_zero']});self.commit(p)
            self.launch_task('SHP унших…',lambda cancel:read_shapefile(path),apply)

    def dem_import(self):
        from .formats import read_dem
        path,_=QFileDialog.getOpenFileName(self,'GeoTIFF elevation band 1 — Z метр байна','','DEM (*.tif *.tiff)')
        if path:
            settings=self.params('DEM nodata-г хадгалсан surface preview',{'Maximum side':256})
            if not settings:return
            def apply(result):
                mesh,metadata=result
                if self.check_source_crs(metadata['crs']):self.add_mesh(mesh,metadata)
            self.launch_task('GeoTIFF унших…',lambda cancel:read_dem(path,int(settings['Maximum side'])),apply)

    def dwg_import(self):
        from ezdxf.addons import odafc
        if not odafc.is_installed():raise ValueError('DWG-д ODA File Converter тусдаа суусан байх шаардлагатай. ODA-ийн лицензийн дагуу суулгах эсвэл DXF экспорт хэрэглэнэ үү.')
        path,_=QFileDialog.getOpenFileName(self,'DWG → DXF','','DWG (*.dwg)')
        if not path:return
        def work(cancel):
            from tempfile import TemporaryDirectory
            from .geometry import read_dxf
            with TemporaryDirectory() as folder:
                target=Path(folder)/'converted.dxf';odafc.convert(path,str(target));return read_dxf(target)
        def apply(result):
            data,unsupported=result;p=deepcopy(self.project)
            for key in ('strings','meshes'):p.workspace.setdefault(key,[]).extend(data[key])
            self.commit(p)
            if unsupported:self.show_rows('DWG/DXF unsupported entities',[{'entity':str(unsupported)}])
        self.launch_task('ODA DWG conversion…',work,apply)

    def contact_rbf(self):
        from .implicit_domains import contact_surface
        path,_=QFileDialog.getOpenFileName(self,'Contact CSV: x,y,z,value — zero contact, ± signed controls','','CSV (*.csv)')
        if not path:return
        from .core import read_rows
        rows=read_rows(path,('x','y','z','value'));xyz=np.array([[r[k] for k in 'xyz'] for r in rows])
        if not len(xyz):raise ValueError('Contact CSV хоосон.')
        defaults={'Kernel':['thin_plate_spline','cubic','linear'],'Resolution':25,'Neighbors':32,'Smoothing':0,'Range X':100,'Range Y':100,'Range Z':50,'Azimuth':90,'Dip':0,'Roll':0}
        defaults.update({'Min '+a:float(xyz[:,i].min()) for i,a in enumerate('XYZ')});defaults.update({'Max '+a:float(xyz[:,i].max()) for i,a in enumerate('XYZ')})
        settings=self.params('Contact RBF — project fault planes хязгаарлана',defaults)
        if settings:
            faults=deepcopy(self.project.workspace.get('faults',[]))
            self.launch_task('Contact / fault RBF…',lambda cancel:contact_surface(rows,[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ'],int(settings['Resolution']),settings['Kernel'],float(settings['Smoothing']),int(settings['Neighbors']),[float(settings['Range '+a]) for a in 'XYZ'],[float(settings[k]) for k in ('Azimuth','Dip','Roll')],faults,cancel),lambda result:self.add_mesh(*result))

    def lithology_rbf(self):
        from .implicit_domains import lithology_constraints,contact_surface
        codes=sorted({r.rock for r in self.project.lithology})
        if len(codes)<2:raise ValueError('Хоёроос цөөнгүй lithology code шаардлагатай.')
        model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Bounds авах блок загвар шаардлагатай.')
        settings=self.params('Lithology binary RBF — unlogged хэсэгт control зохиохгүй',{'Target rock':codes,'Support metres':10,'Resolution':25,'Kernel':['linear','thin_plate_spline','cubic'],'Range X':100,'Range Y':100,'Range Z':50,'Azimuth':90,'Dip':0,'Roll':0})
        if not settings:return
        project=deepcopy(self.project);bounds=list(model['bounds'])
        def work(cancel):
            controls=lithology_constraints(project,settings['Target rock'],float(settings['Support metres']))
            mesh,report=contact_surface(controls,bounds,int(settings['Resolution']),settings['Kernel'],ranges=[float(settings['Range '+a]) for a in 'XYZ'],angles=[float(settings[k]) for k in ('Azimuth','Dip','Roll')],faults=project.workspace.get('faults',[]),cancel=cancel)
            mesh['name']='Lithology '+settings['Target rock'];report['field']='binary midpoint lithology classification, not measured signed distance';report['target_rock']=settings['Target rock'];return mesh,report
        self.launch_task('Lithology / fault RBF…',work,lambda result:self.add_mesh(*result))

    def indicator_dialog(self):
        from .advanced_estimation import indicator_kriging
        from .estimation import sample_support
        settings=self.params('Indicator kriging — variance нь indicator covariance',{'X':0,'Y':0,'Z':0,'Threshold':.5})
        if not settings:return
        params=self.estimator_params()
        if params:
            samples=sample_support(self.project,params.get('composite_length',5));point=[float(settings[k]) for k in 'XYZ']
            self.launch_task('Indicator kriging…',lambda cancel:indicator_kriging(samples,point,float(settings['Threshold']),params),lambda result:self.show_rows('Indicator probability',[result]))

    def multipass_dialog(self):
        from .advanced_estimation import estimate_passes
        from .estimation import sample_support
        model=deepcopy(self.project.workspace.get('block_model'))
        if not model:raise ValueError('Блок загвар алга.')
        params=self.estimator_params()
        if not params:return
        settings=self.params('Centre-support multi-pass — өмнөх grade дахин тооцно',{'Radius multipliers':'1,1.5,3'})
        if settings:
            multipliers=[float(v.strip()) for v in settings['Radius multipliers'].split(',')]
            if not 1<=len(multipliers)<=5 or any(not np.isfinite(v) or v<=0 for v in multipliers):raise ValueError('Pass radii буруу.')
            passes=[{**params,'radii':[r*m for r in params['radii']]} for m in multipliers];samples=sample_support(self.project,params.get('composite_length',5))
            if model.get('domain'):
                from .geometry import inside_polygon
                from .spatial import model_basis
                basis=model_basis(model);origin=np.array(model['bounds'][:3]);height=model['bounds'][5]-model['bounds'][2]
                samples=[s for s in samples if inside_polygon(s['xyz'][0],s['xyz'][1],model['domain']['points']) and 0<=((np.array(s['xyz'])-origin)@basis)[2]<=height]
            def apply(result):
                blocks,counts=result;p=deepcopy(self.project);model['blocks']=blocks;model['multi_pass']=counts;model['params']=params;model['support']='point at block centre';model['discretization']=[1,1,1];model.pop('run_sha256',None);model.pop('input_sha256',None);model['multi_pass_params']=passes;model['params']={**params,'discretization':[1,1,1]};model['sample_count']=len(samples);model['faults']=params.get('faults',[]);p.workspace['block_model']=model;self.commit(p);self.show_rows('Multi-pass counts',counts)
            self.launch_task('Multi-pass estimate…',lambda cancel:estimate_passes(samples,model['blocks'],passes,cancel),apply)

    def family_fit(self):
        from .estimation import experimental_variogram,fit_variogram,sample_support
        settings=self.params('Variogram family fit — exploratory',{'Family':['spherical','exponential','gaussian'],'Composite, м':5,'Lag, м':20,'Lags':15})
        if settings:
            samples=sample_support(self.project,float(settings['Composite, м']))
            def work(cancel):
                rows=experimental_variogram(samples,float(settings['Lag, м']),int(settings['Lags']))['rows'];return fit_variogram(rows,settings['Family'])
            self.launch_task('Variogram fit…',work,lambda result:self.show_rows('Variogram family fit',[result]))

    def ramp_dialog(self):
        from .mine_design import spiral_ramp
        settings=self.params('Спираль ramp surface — pit wall collision шалгаагүй',{'Center X':0,'Center Y':0,'Bottom Z':0,'Top Z':100,'Bottom radius':100,'Width':15,'Gradient %':10,'Radial growth / turn':20,'Step metres':2})
        if settings:
            def work(cancel):return spiral_ramp([float(settings['Center '+a]) for a in 'XY'],*[float(settings[k]) for k in ('Bottom Z','Top Z','Bottom radius','Width','Gradient %','Radial growth / turn','Step metres')])
            def apply(result):
                mesh,line,report=result;p=deepcopy(self.project);p.workspace.setdefault('meshes',[]).append(mesh);p.workspace.setdefault('strings',[]).append(line);p.workspace.setdefault('engineering_runs',[]).append({'tool':'spiral_ramp','report':report});self.commit(p)
            self.launch_task('Ramp geometry…',work,apply)

    def network_dialog(self):
        from .mine_design import tunnel_network
        strings=[s for s in self.project.workspace.get('strings',[]) if not s.get('closed')];index=self.choose('Drive centreline',[s['name'] for s in strings])
        if index is None:return
        settings=self.params('Union tunnel network — geotechnical design шалгаагүй',{'Width':5,'Height':5})
        if settings:
            points=deepcopy(strings[index]['points']);self.launch_task('Tunnel Boolean union…',lambda cancel:tunnel_network(points,float(settings['Width']),float(settings['Height'])),self.add_mesh)

    def ring_dialog(self):
        from .mine_design import drill_ring
        settings=self.params('Геометрийн ring/fan — charge loading тооцохгүй',{'X':0,'Y':0,'Z':0,'Azimuth':90,'Dip':0,'From angle':-60,'To angle':60,'Count':9,'Length':20,'Roll':0})
        if settings:
            holes=drill_ring([float(settings[k]) for k in 'XYZ'],*[float(settings[k]) for k in ('Azimuth','Dip','From angle','To angle')],int(settings['Count']),float(settings['Length']),float(settings['Roll']))
            p=deepcopy(self.project);p.workspace.setdefault('strings',[]).extend(holes);self.commit(p)

    def stope_dialog(self):
        from .mine_design import stope_boxes
        model=deepcopy(self.project.workspace.get('block_model'))
        if not model:raise ValueError('Блок загвар алга.')
        settings=self.params('Floating box MILP — pillar/wall-angle хяналт хийгдээгүй',{'Cells X':2,'Cells Y':2,'Cells Z':2,'Density':2.7,'Value / grade-unit / tonne':100,'Mining cost / tonne':10,'Seconds':20,'Additional shapes (e.g. 3,2,2;4,2,2)':'','Internal dilution cutoff':0,'Maximum internal dilution 0–1':1,'Minimum mean grade':0})
        if settings:
            def apply(report):
                p=deepcopy(self.project);p.workspace['stope_box_optimization']=report
                if report['selected']:
                    from .optimization import pit_mesh
                    mesh=pit_mesh(model,sorted({i for stope in report['selected'] for i in stope['block_indices']}));mesh['name']='Stope box selection';mesh['role']='stope';p.workspace.setdefault('meshes',[]).append(mesh)
                self.commit(p);self.show_rows('Stope selection',report['selected'])
            shapes=[[int(v.strip()) for v in shape.split(',')] for shape in settings['Additional shapes (e.g. 3,2,2;4,2,2)'].split(';') if shape.strip()]
            self.launch_task('Stope candidate MILP…',lambda cancel:stope_boxes(model,[int(settings['Cells '+a]) for a in 'XYZ'],*[float(settings[k]) for k in ('Density','Value / grade-unit / tonne','Mining cost / tonne','Seconds')],shapes=shapes,cutoff=float(settings['Internal dilution cutoff']),maximum_internal_dilution=float(settings['Maximum internal dilution 0–1']),minimum_mean_grade=float(settings['Minimum mean grade']),cancel=cancel),apply)

    def joint_schedule(self):
        from .advanced_estimation import blend_schedule
        from .planning import economic_tasks
        model=deepcopy(self.project.workspace.get('block_model'))
        if not model:raise ValueError('Блок загвар алга.')
        unit=self.project.grade_unit
        settings=self.params('Олборлолт + same-period feed blend — stockpile байхгүй',{'Density':2.7,'Cutoff':.5,'Metal price / tonne':1000,'Recovery':.9,'Mining cost / tonne':3,'Processing cost / tonne':12,'Haul cost / tonne':1,'Mining tonnes / period':100000,'Processing tonnes / period':50000,'Periods':4,'Minimum feed grade':.5,'Maximum feed grade':2,'Discount':.05,'Seconds':20})
        if settings:
            def work(cancel):
                tasks=economic_tasks(model,float(settings['Density']),float(settings['Cutoff']),unit,*[float(settings[k]) for k in ('Metal price / tonne','Mining cost / tonne','Processing cost / tonne','Recovery','Haul cost / tonne')])
                for task in tasks:
                    task['grade']=model['blocks'][int(task['id'])].get('grade') or 0.
                return blend_schedule(tasks,float(settings['Mining tonnes / period']),float(settings['Processing tonnes / period']),int(settings['Periods']),float(settings['Minimum feed grade']),float(settings['Maximum feed grade']),float(settings['Discount']),float(settings['Seconds']))
            def apply(report):
                p=deepcopy(self.project);p.workspace['joint_blend_schedule']=report;self.commit(p);self.show_rows('Period feed and capacity',report['periods'])
            self.launch_task('Joint scheduling MILP…',work,apply)

    def lidar_preview(self):
        from .formats import las_preview
        from .large_view import LargePreviewFactory
        path,_=QFileDialog.getOpenFileName(self,'LAS / LAZ — эхийг өөрчлөхгүй GPU preview','','LiDAR (*.las *.laz)')
        if path:
            import laspy
            with laspy.open(path,read_evlrs=False) as reader:
                defaults={p+' '+a:float((reader.header.mins if p=='Min' else reader.header.maxs)[i]) for p in ('Min','Max') for i,a in enumerate('XYZ')}
            defaults.update({'Maximum displayed points':250000,'Classes (blank=all)':''})
            settings=self.params('LiDAR streaming preview',defaults)
            if settings:
                bounds=[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ']
                classes=[int(v.strip()) for v in settings['Classes (blank=all)'].split(',')] if settings['Classes (blank=all)'].strip() else None
                def apply(payload):
                    if self.check_source_crs(payload['crs']):LargePreviewFactory.show(self,payload,'LiDAR GPU preview')
                self.launch_task('LAS/LAZ chunks…',lambda cancel:las_preview(path,int(settings['Maximum displayed points']),bounds=bounds,classes=classes,cancel=cancel),apply)

    def lidar_export(self):
        import laspy
        from .formats import filter_las
        source,_=QFileDialog.getOpenFileName(self,'Эх LAS/LAZ','','LiDAR (*.las *.laz)')
        if not source:return
        with laspy.open(source) as reader:
            defaults={p+' '+a:float((reader.header.mins if p=='Min' else reader.header.maxs)[i]) for p in ('Min','Max') for i,a in enumerate('XYZ')}
        defaults['Classes (blank=all)']=''
        settings=self.params('LAS/LAZ subset — бүх point dimension хадгална',defaults)
        if not settings:return
        target,_=QFileDialog.getSaveFileName(self,'Filtered LAS/LAZ','','LiDAR (*.las *.laz)')
        if not target:return
        bounds=[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ']
        classes=[int(v) for v in settings['Classes (blank=all)'].split(',')] if settings['Classes (blank=all)'].strip() else None
        self.launch_task('LAS/LAZ экспорт…',lambda cancel:filter_las(source,target,bounds,classes,cancel),lambda report:self.show_rows('LiDAR экспорт',[report]))

    def large_blocks(self):
        from .large_view import parquet_preview,LargePreviewFactory
        path,_=QFileDialog.getOpenFileName(self,'RAINYMINE Parquet — bounded GPU instancing preview','','Parquet (*.parquet)')
        if path:
            from .block_store import block_metadata
            metadata=block_metadata(path);bounds=metadata['model'].get('bounds')
            defaults={'Maximum displayed blocks':250000,'Preview RAM budget MiB':512,'Cutoff (blank=none)':''}
            if bounds:defaults.update({p+' '+a:bounds[i+j*3] for j,p in enumerate(('Min','Max')) for i,a in enumerate('XYZ')})
            settings=self.params('External Parquet GPU preview',defaults)
            if settings:
                region=[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ'] if bounds else None
                def apply(payload):
                    if self.check_source_crs(payload['crs']):LargePreviewFactory.show(self,payload,'Parquet GPU blocks')
                cutoff=float(settings['Cutoff (blank=none)']) if settings['Cutoff (blank=none)'].strip() else None
                self.launch_task('Parquet batches…',lambda cancel:parquet_preview(path,int(settings['Maximum displayed blocks']),bounds=region,cutoff=cutoff,cancel=cancel,memory_budget_mib=float(settings['Preview RAM budget MiB'])),apply)

    def closeEvent(self,event):
        if any(task.worker.isRunning() for task in self._engineering_tasks):
            for task in self._engineering_tasks:task.cancel.set()
            event.ignore();return
        if self._gizmo:self._gizmo[2].close()
        for dialog in list(self._preview_dialogs):dialog.close()
        super().closeEvent(event)

    def open_exchange_export(self,kind):
        from .open_exchange import write_omf,write_geopackage,write_exchange_bundle
        writer,extension={'omf':(write_omf,'omf'),'gpkg':(write_geopackage,'gpkg'),'bundle':(write_exchange_bundle,'zip')}[kind]
        title={'omf':'OMF 2.0-beta.1 — хүлээн авагчийн хувилбарыг шалгана','gpkg':'GeoPackage — GIS геометр; блок/interval хүснэгт орохгүй','bundle':'CSV / DXF / OBJ / STL + CRS, нэгж, NULL metadata'}[kind]
        path=self.destination(title,extension)
        if path:
            project=deepcopy(self.project)
            self.launch_task(title,lambda cancel:writer(path,project,cancel),lambda report:self.show_rows('Солилцооны экспорт',[report]))

    def omf_export(self):self.open_exchange_export('omf')
    def gpkg_export(self):self.open_exchange_export('gpkg')
    def exchange_bundle(self):self.open_exchange_export('bundle')

    def gpkg_import(self):
        import fiona
        from .open_exchange import read_geopackage
        from .large_view import LargePreviewFactory
        path,_=QFileDialog.getOpenFileName(self,'GeoPackage GIS давхарга','','GeoPackage (*.gpkg)')
        if not path:return
        layers=[]
        for name in fiona.listlayers(path):
            with fiona.open(path,layer=name,enabled_drivers=['GPKG']) as source:
                if source.schema['geometry'] not in (None,'None'):layers.append(name)
        index=self.choose('GeoPackage давхарга — polygon hole нь тусдаа marked ring байна',layers)
        if index is None:return
        def apply(data):
            if not self.check_source_crs(data['crs']):return
            p=deepcopy(self.project);p.workspace.setdefault('strings',[]).extend(data['strings']);p.workspace.setdefault('engineering_runs',[]).append({'tool':'GeoPackage','source':Path(path).name,**{k:v for k,v in data.items() if k!='strings'}});self.commit(p)
            if data['points']:
                xyz=np.asarray(data['points']);payload={'kind':'points','xyz':xyz,'source_index':np.arange(len(xyz),dtype=np.int64),'source_points':len(xyz),'matched_before_sampling':len(xyz),'stride':1}
                LargePreviewFactory.show(self,payload,'GeoPackage · '+data['layer'])
        self.launch_task('GeoPackage унших…',lambda cancel:read_geopackage(path,layers[index]),apply)

    def dh_import_dialog(self,directory=""):
        from .dh_import import scan_sources,options
        from PySide6.QtCore import QTimer
        paths,_=QFileDialog.getOpenFileNames(self,'DH багц — dh_collar.csv болон бусад dh_*.csv-ээ хамт сонгоно',str(directory),'DH CSV (*.csv)')
        if not paths:return
        source=self.project
        def work(cancel):
            bundle=scan_sources(paths,cancel);return bundle,options(bundle)
        def apply(result):
            def configure():
                if self.project is not source:return
                if self._engineering_tasks:QTimer.singleShot(20,configure);return
                self.guard(lambda:self.dh_configure(*result))
            QTimer.singleShot(0,configure)
        self.launch_task('DH эх хүснэгтүүдийг шалгаж архивлах…',work,apply)

    def dh_configure(self,bundle,choices=None):
        from .dh_import import options,project_from_bundle
        choices=choices or options(bundle)
        channels=list(choices['channels']);channels.sort(key=lambda c:(c!=('dh_assay.csv','Au','PPM'),c))
        labels=[' | '.join(c) for c in channels];rocks=list(choices['lithology_columns']);rocks.sort(key=lambda c:(c!='Lith1_Code',c!='Lith_primary',c))
        settings=self.params('DH — шинэ өгөгдлийн төсөл; Survey байхгүй бол амсрын өнцгөөр шулуун таамаг',{
            'Идэвхтэй сорьц (нэг элемент)':labels+['— Сорьц сонгохгүй —'],
            'Литологийн кодын атрибут':rocks+['— Литологи сонгохгүй —'],
            'Илрүүлэх хязгаараас доош утга':['Exclude — эх утгыг хадгалж тооцооноос хасах','Half limit — эх limit-ийн 1/2 (сонгосон орлуулалт)']})
        if not settings:return
        selected=settings['Идэвхтэй сорьц (нэг элемент)'];channel=channels[labels.index(selected)] if selected in labels else None
        lith=settings['Литологийн кодын атрибут'];lith=lith if lith in rocks else None
        policy='half_limit' if settings['Илрүүлэх хязгаараас доош утга'].startswith('Half') else 'exclude'
        def apply(result):
            project,report=result;self.commit(project);self.path=None;self.update_title()
            self.show_rows('DH импорт — эх файлууд төсөлд хадгалагдсан; Survey байхгүй',[
                {'үзүүлэлт':'Амсар','утга':report['collars']},{'үзүүлэлт':'Идэвхтэй сорьц','утга':report['active_assays']},
                {'үзүүлэлт':'Литологи','утга':report['active_lithology']},{'үзүүлэлт':'Survey station','утга':0},
                {'үзүүлэлт':'CSV баганын алдаатай мөр (эх archive-д хадгалсан)','утга':len(report['source_parse_issues'])},
                {'үзүүлэлт':'Интервал / join алдаа','утга':len(report['issues'])},
                {'үзүүлэлт':'Замнал','утга':'Downhole survey байхгүй: collar azimuth/dip-ээр шулуун таамаг'},
                {'үзүүлэлт':'Өмнөх тооцоолол','утга':'Шинэ өгөгдлийн төсөл үүссэн. Хадгалахдаа шинэ .rmine сонгоно.'}])
        self.launch_task('DH сонгосон элемент / литологи холбох…',lambda cancel:project_from_bundle(bundle,channel,lith,policy,cancel=cancel),apply)

    def dh_change_channel(self):
        bundle=self.project.workspace.get('dh_bundle')
        if not bundle:raise ValueError('Эхлээд DH багц импортлоно уу.')
        if QMessageBox.question(self,'DH өгөгдлийг дахин сонгох','Archive-аас шинэ өгөгдлийн төсөл үүсгэнэ. Одоогийн блок/тооцооллыг шинэ элементийн үр дүн гэж авч үлдэхгүй. Үргэлжлүүлэх үү?')==QMessageBox.StandardButton.Yes:self.dh_configure(bundle)

    def dh_source_browser(self):
        from .dh_import import source_page,source_bytes
        from .open_exchange import atomic_destination
        from PySide6.QtWidgets import QComboBox,QSpinBox,QTableWidget,QTableWidgetItem,QAbstractItemView
        bundle=self.project.workspace.get('dh_bundle')
        if not bundle:raise ValueError('DH эх архив байхгүй. DH багц импортлоно уу.')
        dialog=QDialog(self);dialog.setWindowTitle('DH эх хүснэгт — 200 мөр / хуудас; бүх эх утга хадгалагдсан');dialog.resize(1200,720)
        layout=QVBoxLayout(dialog);row=QHBoxLayout();files=QComboBox();files.addItems(sorted(bundle['files']));page=QSpinBox();page.setMinimum(1);row.addWidget(files,1);row.addWidget(QLabel('Хуудас'));row.addWidget(page);export=QPushButton('Эх CSV-г яг хэвээр гаргах');row.addWidget(export);layout.addLayout(row)
        info=QLabel();info.setWordWrap(True);layout.addWidget(info);table=QTableWidget();table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(table)
        def load(reset=False):
            def run():
                name=files.currentText();entry=bundle['files'][name]
                page.blockSignals(True);page.setMaximum(max(1,(entry['rows']+199)//200))
                if reset:page.setValue(1)
                page.blockSignals(False);rows=source_page(bundle,name,page.value()-1);columns=['source_row']+entry['headers']
                for r in rows:
                    for key in r:
                        if key not in columns:columns.append(key)
                table.setRowCount(len(rows));table.setColumnCount(len(columns));table.setHorizontalHeaderLabels(columns)
                for i,r in enumerate(rows):
                    for j,key in enumerate(columns):table.setItem(i,j,QTableWidgetItem(str(r.get(key,''))))
                info.setText(f"{name} · {entry['rows']:,} мөр · {len(entry.get('parse_issues',[]))} CSV бүтэц буруу мөр · "+('No data found — эх файл хоосон' if entry['empty_marker'] else 'SHA256 шалгасан эх утга; negative / < / NULL өөрчлөгдөөгүй'))
            self.guard(run)
        def save():
            path=self.destination('DH эх CSV экспорт','csv')
            if path:
                def run():
                    data=source_bytes(bundle,files.currentText())
                    with atomic_destination(path) as temp:temp.write_bytes(data)
                self.guard(run)
        files.currentIndexChanged.connect(lambda:load(True));page.valueChanged.connect(lambda:load());export.clicked.connect(save);load();dialog.exec()
