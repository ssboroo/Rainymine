"""Professional workflow commands, connected to native geometry and bounded data readers."""
from copy import deepcopy
from pathlib import Path
import csv
import numpy as np
from PySide6.QtWidgets import QFileDialog,QMessageBox,QDialog,QVBoxLayout,QLabel,QPushButton,QHBoxLayout
from .background import Task


class ProTools:
    def build_pro_menu(self):
        self._engineering_tasks=[];self._preview_dialogs=[];self._gizmo=None
        menu=self.menuBar().addMenu('Мэргэжлийн хэрэгсэл')
        groups=[('Нээлттэй солилцоо',[('OMF 2.0-beta.1 экспорт…',self.omf_export),('GeoPackage экспорт…',self.gpkg_export),('GeoPackage импорт…',self.gpkg_import),('CSV / CAD + metadata багц…',self.exchange_bundle)]),('CAD / Solid',[('Boolean union / intersection / difference…',self.solid_boolean),('Mesh repair…',self.solid_repair),('Шилжүүлэх / эргүүлэх / scale…',self.transform_dialog),('3D gizmo — сонгосон mesh…',self.start_gizmo),('Vertex / segment snap…',self.snap_dialog)]),
                ('Файл / GIS',[('Surpac STR импорт…',self.surpac_import),('Surpac STR экспорт…',self.surpac_export),('Surpac ASCII DTM импорт…',self.surpac_dtm_import),('SHP импорт…',self.shapefile_import),('GeoTIFF DEM импорт…',self.dem_import),('LAS/LAZ шүүлт ба экспорт…',self.lidar_export),('DWG → DXF adapter…',self.dwg_import)]),
                ('Геологи / Үнэлгээ',[('Contact / trend / fault RBF…',self.contact_rbf),('Литологийн fault/trend RBF…',self.lithology_rbf),('Indicator kriging…',self.indicator_dialog),('Олон шаттай үнэлгээ…',self.multipass_dialog),('Variogram family fit…',self.family_fit)]),
                ('Уурхайн зураг төсөл',[('Спираль ramp…',self.ramp_dialog),('Шугамаар малталтын сүлжээ…',self.network_dialog),('Өрөмдлөгийн ring / fan…',self.ring_dialog),('Stope box MILP…',self.stope_dialog)]),
                ('Төлөвлөлт',[('Олборлолт + feed blend MILP…',self.joint_schedule)]),
                ('Том өгөгдөл',[('LAS / LAZ GPU preview…',self.lidar_preview),('Parquet GPU block preview…',self.large_blocks)])]
        for name,commands in groups:
            submenu=menu.addMenu(name)
            for title,callback in commands:
                action=self.action(submenu,title,lambda cb=callback:self.guard(cb));action.setProperty('toolCategory',name)
                from .icons import semantic_icon,icon
                action.setIcon(semantic_icon(title,icon('gear')))

    def launch_task(self,title,operation,apply):
        if self._engineering_tasks:raise ValueError('Ажиллаж буй тооцоогоо дуусгах эсвэл цуцална уу.')
        return Task(self,title,operation,apply)

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
        settings=self.params('Regular box stope MILP — MSO wall-angle/dilution биш',{'Cells X':2,'Cells Y':2,'Cells Z':2,'Density':2.7,'Value / grade-unit / tonne':100,'Mining cost / tonne':10,'Seconds':20})
        if settings:
            def apply(report):
                p=deepcopy(self.project);p.workspace['stope_box_optimization']=report
                if report['selected']:
                    from .optimization import pit_mesh
                    mesh=pit_mesh(model,sorted({i for stope in report['selected'] for i in stope['block_indices']}));mesh['name']='Stope box selection';mesh['role']='stope';p.workspace.setdefault('meshes',[]).append(mesh)
                self.commit(p);self.show_rows('Stope selection',report['selected'])
            self.launch_task('Stope candidate MILP…',lambda cancel:stope_boxes(model,[int(settings['Cells '+a]) for a in 'XYZ'],*[float(settings[k]) for k in ('Density','Value / grade-unit / tonne','Mining cost / tonne','Seconds')]),apply)

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
            defaults={'Maximum displayed blocks':250000,'Cutoff (blank=none)':''}
            if bounds:defaults.update({p+' '+a:bounds[i+j*3] for j,p in enumerate(('Min','Max')) for i,a in enumerate('XYZ')})
            settings=self.params('External Parquet GPU preview',defaults)
            if settings:
                region=[float(settings[p+' '+a]) for p in ('Min','Max') for a in 'XYZ'] if bounds else None
                def apply(payload):
                    if self.check_source_crs(payload['crs']):LargePreviewFactory.show(self,payload,'Parquet GPU blocks')
                cutoff=float(settings['Cutoff (blank=none)']) if settings['Cutoff (blank=none)'].strip() else None
                self.launch_task('Parquet batches…',lambda cancel:parquet_preview(path,int(settings['Maximum displayed blocks']),bounds=region,cutoff=cutoff,cancel=cancel),apply)

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
