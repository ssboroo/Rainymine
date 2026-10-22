"""Native entry points for recovery-era workflow and bounded engineering tools."""
from copy import deepcopy
import csv
import time
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QFileDialog,QInputDialog


class FoundationTools:
    def build_foundation_menu(self,menu):
        groups=[('Ажлын урсгал', [('Импорт → QA/QC → Үнэлгээ → Экспорт…',self.workflow_dialog)]),
                ('Дискэн блок сан',[('Том блок сан үүсгэх…',self.disk_create),('Блок сан холбох…',self.disk_attach),('Дискэн IDW үнэлгээ…',self.disk_estimate),('Дискэн блок засах…',self.disk_edit),('Дискэн өөрчлөлт буцаах',lambda:self.disk_undo(False)),('Дискэн өөрчлөлт сэргээх',lambda:self.disk_undo(True)),('Дискэн блок 3D харах…',self.disk_preview),('Дискэн тонн / металл…',self.disk_totals),('Дискэн блок CSV экспорт…',self.disk_export)]),
                ('Хяналттай инженерийн загвар',[('Давхарга / хавтгай хагарлын шилжилт…',self.stratigraphy_dialog),('Давхаргаар тусгаарласан IDW үнэлгээ…',self.stratigraphy_estimate_dialog),('Овоолго / дахин таталтын баланс…',self.stockpile_dialog),('Замын хэсэгчилсэн тээвэр…',self.segment_haul_dialog),('Зангилааг бусад шугамд тааруулах…',self.snap_edit_dialog)])]
        for title,commands in groups:
            submenu=menu.addMenu(title)
            for label,callback in commands:
                action=self.action(submenu,label,lambda cb=callback:self.guard(cb));action.setProperty('toolCategory',title)
                from .icons import semantic_icon,icon
                action.setIcon(semantic_icon(label,icon('gear')))

    def workflow_dialog(self):
        from .i18n import language
        en=language()=='en'
        dialog=QDialog(self);dialog.setWindowTitle('Workflow review' if en else 'Ажлын урсгалын хяналт');dialog.resize(720,560);layout=QVBoxLayout(dialog)
        notice=QLabel('Run each stage, then record the observed outcome. Records are user observations, not independent certification.' if en else 'Үе шат бүрийг ажиллуулаад ажигласан үр дүнгээ бүртгэнэ. Бүртгэл нь хэрэглэгчийн ажиглалт; хараат бус баталгаа биш.');notice.setWordWrap(True);layout.addWidget(notice)
        status=QLabel();status.setWordWrap(True);layout.addWidget(status)
        def refresh_status():
            p=self.project;model=p.workspace.get('block_model',{});controls=p.workspace.get('qaqc_controls',{})
            status.setText(f"Collars: {len(p.collars)} · Assays: {len(p.assays)} · CRS: {p.crs_code or 'UNSPECIFIED'}\nQA/QC control rows: {len(controls.get('results',[]))} · Blocks: {len(model.get('blocks',[]))}\nUnestimated: {sum(b.get('grade') is None for b in model.get('blocks',[]))} · Observations: {len(p.workspace.get('workflow_observations',[]))}")
        stages=[('Import DH bundle' if en else '1. DH багц импорт',self.dh_import_dialog),('Validate data' if en else '2. Өгөгдөл шалгах',self.validate_data),('Laboratory QA/QC' if en else '3. Лабораторийн QA/QC',self.controls),('Build / estimate model' if en else '4. Модель / үнэлгээ',self.block_dialog),('Reference comparison' if en else '5. Reference харьцуулалт',self.external_benchmark),('Export exchange bundle' if en else '6. Солилцооны экспорт',self.exchange_bundle)]
        for label,callback in stages:
            button=QPushButton(label);layout.addWidget(button)
            def invoke(checked=False,cb=callback,title=label):
                started=time.perf_counter();self.guard(cb);elapsed=time.perf_counter()-started;refresh_status()
                outcome,ok=QInputDialog.getItem(dialog,'Observed outcome' if en else 'Ажигласан үр дүн','This records the interaction duration, including dialogs; background jobs may still be running.' if en else 'Хугацаанд цонх ашигласан хугацаа орно. Арын тооцоо үргэлжилж байж болно.',['completed','blocked','cancelled'],0,False)
                if ok:
                    note,accepted=QInputDialog.getText(dialog,'Review note' if en else 'Хяналтын тэмдэглэл','Reviewer / errors / note' if en else 'Шалгасан хүн / алдаа / тэмдэглэл')
                    if accepted:
                        def record():
                            p=deepcopy(self.project);p.workspace.setdefault('workflow_observations',[]).append({'stage':title,'observed_outcome':outcome,'interaction_seconds':round(elapsed,3),'note':note,'time_unix':time.time(),'independent_review_verified':False});self.commit(p)
                        self.guard(record);refresh_status()
            button.clicked.connect(invoke)
        close=QPushButton('Close' if en else 'Хаах');close.clicked.connect(dialog.accept);layout.addWidget(close);refresh_status();dialog.exec()

    def disk_path(self):
        if self._engineering_tasks:raise ValueError('Эхлээд ажиллаж буй тооцоог дуусгах эсвэл цуцална уу.')
        paths=self.project.workspace.get('disk_block_stores',[])
        if not paths:raise ValueError('Эхлээд дискэн блок сан үүсгэх эсвэл холбох шаардлагатай.')
        index=self.choose('Дискэн блок сан',paths)
        return None if index is None else paths[index]

    def link_disk(self,path):
        from .disk_model import DiskModel
        from pyproj import CRS
        with DiskModel(path) as store:
            if not self.project.crs_code or CRS.from_user_input(store.meta['crs'])!=CRS.from_user_input(self.project.crs_code) or store.meta['grade_unit']!=self.project.grade_unit:raise ValueError('Block store CRS / grade unit must match project settings')
        p=deepcopy(self.project);paths=p.workspace.setdefault('disk_block_stores',[]);path=str(Path(path).resolve())
        if path not in paths:paths.append(path)
        self.commit(p)

    def disk_attach(self):
        if self._engineering_tasks:raise ValueError('Эхлээд ажиллаж буй тооцоог дуусгах эсвэл цуцална уу.')
        path,_=QFileDialog.getOpenFileName(self,'Дискэн блок сан холбох','','RAINYMINE block database (*.rmdb)')
        if path:self.link_disk(path)

    def disk_create(self):
        from .disk_model import DiskModel
        if not self.project.crs_code:raise ValueError('Төслийн projected metre CRS-ийг эхлээд тохируулна уу.')
        settings=self.params('Дискэн тогтмол grid — төвийн үнэлгээ',{'Origin X':500000.,'Origin Y':5300000.,'Origin Z':1200.,'Count X':100,'Count Y':100,'Count Z':100,'Size X':10.,'Size Y':10.,'Size Z':10.,'Density t/m³':2.7})
        if not settings:return
        path,_=QFileDialog.getSaveFileName(self,'Дискэн блок сан','Blocks.rmdb','RAINYMINE block database (*.rmdb)')
        if not path:return
        crs=self.project.crs_code;unit=self.project.grade_unit
        self.launch_task('Дискэн grid үүсгэж байна…',lambda cancel:DiskModel.create(path,[float(settings['Origin '+a]) for a in 'XYZ'],[int(settings['Count '+a]) for a in 'XYZ'],[float(settings['Size '+a]) for a in 'XYZ'],crs,unit,float(settings['Density t/m³']),cancel),lambda result:self.link_disk(result['path']))

    def disk_estimate(self):
        from .disk_model import DiskModel
        from .estimation import sample_support
        path=self.disk_path()
        if not path:return
        self.link_disk(path)
        settings=self.params('Дискэн IDW — centre support; no geological certification',{'Composite metres':5.,'Minimum coverage':1.,'Radius metres':100.,'Neighbours':12,'Minimum samples':3,'Power':2.})
        if not settings:return
        samples=sample_support(self.project,float(settings['Composite metres']),float(settings['Minimum coverage']))
        values=[[*s['xyz'],s['grade']] for s in samples]
        def work(cancel):
            with DiskModel(path) as store:return store.estimate_idw(values,float(settings['Radius metres']),int(settings['Neighbours']),int(settings['Minimum samples']),float(settings['Power']),cancel)
        def apply(report):
            p=deepcopy(self.project);p.workspace.setdefault('disk_estimation_runs',[]).append(dict(report,path=path));self.commit(p);self.show_rows('Дискэн IDW',[report])
        self.launch_task('Дискэн IDW…',work,apply)

    def disk_edit(self):
        from .disk_model import DiskModel
        path=self.disk_path()
        if not path:return
        settings=self.params('Дискэн блок засах — хоосон утга NULL',{'Block ID':0,'Grade (blank=NULL)':'','Density (blank=NULL)':'','Domain (blank=NULL)':''})
        if settings:
            parse=lambda key:float(settings[key]) if settings[key].strip() else None
            with DiskModel(path) as store:store.edit(int(settings['Block ID']),parse('Grade (blank=NULL)'),parse('Density (blank=NULL)'),settings['Domain (blank=NULL)'] or None)
            self.statusBar().showMessage('Дискэн өөрчлөлт хадгалагдлаа. Дискэн Undo ашиглаж болно.')

    def disk_undo(self,redo=False):
        from .disk_model import DiskModel
        path=self.disk_path()
        if path:
            with DiskModel(path) as store:changed=store.undo(redo)
            self.statusBar().showMessage('Өөрчлөлт сэргээгдлээ.' if changed else 'Хадгалсан түүх алга.')

    def disk_totals(self):
        from .disk_model import DiskModel
        path=self.disk_path()
        if path:
            def work(cancel):
                with DiskModel(path) as store:return store.totals()
            self.launch_task('Дискэн тайлан…',work,lambda report:self.show_rows('Тонн / металл — ангилаагүй',[report]))

    def disk_preview(self):
        from .disk_model import DiskModel
        from .large_view import LargePreviewFactory
        path=self.disk_path()
        if path:
            def work(cancel):
                with DiskModel(path) as store:return store.preview()
            self.launch_task('Дискэн 3D preview…',work,lambda payload:LargePreviewFactory.show(self,payload,'Disk model · sampled preview'))

    def disk_export(self):
        from .disk_model import DiskModel
        path=self.disk_path()
        if not path:return
        output,_=QFileDialog.getSaveFileName(self,'Дискэн блок CSV + CRS / нэгжийн багц','Blocks.zip','CSV + metadata ZIP (*.zip)')
        if output:
            def work(cancel):
                with DiskModel(path) as store:return store.export_bundle(output,cancel)
            self.launch_task('Дискэн CSV экспорт…',work,lambda report:self.show_rows('Экспортын CRS / нэгж',[report]))

    def stratigraphy_dialog(self):
        from .acceptance_tools import classify_stratigraphy
        model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Эхлээд үндсэн блок загвар үүсгэнэ үү.')
        settings=self.params('Зэрэгцээ давхарга — grade хүчингүй болж дахин үнэлнэ',{'Normal X':0.,'Normal Y':0.,'Normal Z':1.,'Origin X':0.,'Origin Y':0.,'Origin Z':0.,'Contacts ascending metres':'1200,1250,1300','Layer names bottom to top':'L1,L2,L3,L4','Fault slips JSON oldest to newest':'[]'})
        if settings:
            import json
            result,report=classify_stratigraphy(model,[float(settings['Normal '+a]) for a in 'XYZ'],[float(settings['Origin '+a]) for a in 'XYZ'],[float(v) for v in settings['Contacts ascending metres'].split(',')],[v.strip() for v in settings['Layer names bottom to top'].split(',')],json.loads(settings['Fault slips JSON oldest to newest']))
            p=deepcopy(self.project);p.workspace['block_model']=result;p.workspace.setdefault('engineering_runs',[]).append(report);self.commit(p)

    def stockpile_dialog(self):
        from .acceptance_tools import stockpile_ledger
        path,_=QFileDialog.getOpenFileName(self,'period,pile,received_t,received_grade,reclaimed_t,capacity_t CSV','','CSV (*.csv)')
        if not path:return
        settings=self.params('Овоолгын баланс — perfect mixing; no optimization',{'Processing tonnes / period':100000.,'Haul tonnes / period':200000.})
        if not settings:return
        with open(path,encoding='utf-8-sig',newline='') as stream:
            rows=[]
            for row in csv.DictReader(stream):
                if len(rows)>=10000:raise ValueError('Maximum 10000 stockpile rows')
                rows.append({'period':int(row['period']),'pile':row['pile'],**{k:float(row[k]) for k in ('received_t','received_grade','reclaimed_t','capacity_t')}})
        report=stockpile_ledger(rows,self.project.grade_unit,float(settings['Processing tonnes / period']),float(settings['Haul tonnes / period']))
        import hashlib
        report['source_sha256']=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        p=deepcopy(self.project);p.workspace.setdefault('stockpile_runs',[]).append(report);self.commit(p);self.show_rows('Овоолго / дахин таталт',report['rows'])

    def stratigraphy_estimate_dialog(self):
        from .acceptance_tools import estimate_stratigraphy
        model=deepcopy(self.project.workspace.get('block_model',{}))
        if not model.get('stratigraphy'):raise ValueError('Эхлээд давхаргын ангилал үүсгэнэ үү.')
        settings=self.params('Давхаргаар тусгаарласан IDW — restored coordinates / point support',{'Radius metres':200.,'Neighbours':12,'Minimum samples':3,'Composite metres':5.,'Minimum coverage':1.,'Power':2.})
        if not settings:return
        radius=float(settings['Radius metres']);params={'method':'idw','radii':[radius]*3,'neighbors':int(settings['Neighbours']),'minimum':int(settings['Minimum samples']),'power':float(settings['Power']),'composite_length':float(settings['Composite metres']),'minimum_coverage':float(settings['Minimum coverage'])}
        project=deepcopy(self.project)
        def apply(result):
            p=deepcopy(self.project);p.workspace['block_model']=result;self.commit(p)
        self.launch_task('Давхаргын IDW…',lambda cancel:estimate_stratigraphy(project,model,params,cancel),apply)

    def segment_haul_dialog(self):
        from .acceptance_tools import segment_haul
        strings=self.project.workspace.get('strings',[]);index=self.choose('Тээврийн зам',[s['name'] for s in strings])
        if index is None:return
        settings=self.params('Хэсэгчилсэн тээвэр — supplied speed bands',{'Speed bands JSON':'[{"min_gradient":-10,"max_gradient":0,"loaded_kmh":25,"empty_kmh":30},{"min_gradient":0,"max_gradient":10,"loaded_kmh":15,"empty_kmh":20}]','Payload tonnes':90.,'Trucks':5,'Shift hours':8.,'Utilization':.8,'Load minutes':3.,'Dump minutes':2.,'Queue minutes':1.,'Max gradient %':10.})
        if settings:
            import json
            report=segment_haul(strings[index]['points'],json.loads(settings['Speed bands JSON']),float(settings['Payload tonnes']),int(settings['Trucks']),float(settings['Shift hours']),float(settings['Utilization']),float(settings['Load minutes']),float(settings['Dump minutes']),float(settings['Queue minutes']),float(settings['Max gradient %']))
            p=deepcopy(self.project);p.workspace.setdefault('segment_haul_runs',[]).append(report);self.commit(p);self.show_rows('Хэсэгчилсэн тээвэр',report['segments'])

    def snap_edit_dialog(self):
        from .cad import SnapIndex
        from .geometry import validate_workspace
        strings=self.project.workspace.get('strings',[]);index=self.choose('Засах шугам',[s['name'] for s in strings])
        if index is None:return
        settings=self.params('Зангилааг бусад шугамд тааруулах',{'Vertex index (0 based)':0,'Tolerance metres':5.})
        if not settings:return
        vertex=int(settings['Vertex index (0 based)'])
        if not 0<=vertex<len(strings[index]['points']):raise ValueError('Invalid vertex index')
        points=[];segments=[]
        for i,string in enumerate(strings):
            if i==index:continue
            start=len(points);points.extend(string['points']);segments.extend((start+j,start+j+1) for j in range(len(string['points'])-1))
            if string.get('closed'):segments.append((len(points)-1,start))
        result=SnapIndex(points,segments).nearest(strings[index]['points'][vertex],float(settings['Tolerance metres']))
        if not result:raise ValueError('Tolerance дотор бусад шугам олдсонгүй.')
        p=deepcopy(self.project);p.workspace['strings'][index]['points'][vertex]=result['point'];validate_workspace(p.workspace);self.commit(p)
