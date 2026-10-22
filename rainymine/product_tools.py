"""Native tool groups for geology, daily work, vector maps and local automation."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,QGroupBox,QScrollArea,
    QFileDialog,QMessageBox,QDialog,QPushButton,QLabel,QGraphicsScene,QGraphicsView,QPlainTextEdit,QDialogButtonBox,QLayout)
from .ribbon import RibbonButton
from .workbench import icon
from .i18n import language,tr
from .icons import semantic_icon


class ProductTools:
    def build_product_ribbon(self):
        groups=[('Геостатистик',[
            ('Агуулгын шинжилгээ',[('Top-cut шинжилгээ',self.cap_tool),('Өндөр агуулгын зай',self.high_grade_tool),('Cell declustering',self.decluster_tool)]),
            ('Локал модель',[('Хувьсах эллипсоид',self.dynamic_tool),('Ангиллын санал',self.classification_tool)])]),
          ('Өдөр тутмын ажил',[
            ('Хэмжилт ба хяналт',[('Өрөмдлөгийн тор',self.pattern_tool),('Хүдэр / хоосон хил',self.digline_tool),('TIN Cut / Fill',self.cutfill_tool)]),
            ('Геотехник',[('Wulff / Schmidt',self.stereonet_tool)])]),
          ('Хэвлэлт',[
            ('Вектор зураг',[('План / зүсэлт PDF',self.map_tool),('ЭБМЗ багц гаргах',self.ebmz_export)]),
            ('Геологийн засвар',[('Контакт / чиглүүлэгч',self.contact_editor)])]),
          ('Автоматжуулалт',[
            ('Локал копилот',[('Блок шүүх / тооцох',self.copilot_tool),('QA/QC зөвлөх',self.qaqc_advisor),('Аргачлалын ноорог',self.methodology_tool)]),
            ('Workflow',[('Бичлэг эхлэх',self.record_start),('Бичлэг хадгалах',self.record_save),('Re-run All',self.replay_tool)])])]
        for title,sections in groups:
            content=QWidget();row=QHBoxLayout(content);row.setContentsMargins(6,4,6,2)
            row.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            for name,commands in sections:
                group=QGroupBox(name);group.setObjectName('ribbonGroup');grid=QGridLayout(group);grid.setContentsMargins(5,2,5,18)
                for i,(caption,callback) in enumerate(commands):
                    kind='chart' if callback in (self.cap_tool,self.decluster_tool,self.stereonet_tool,self.qaqc_advisor) else 'file' if title in ('Хэвлэлт','Автоматжуулалт') else 'surface'
                    button=RibbonButton();button.setText(caption);button.setProperty('commandSource',caption);button.setIcon(semantic_icon(caption,icon(kind)));button.clicked.connect(lambda checked=False,cb=callback:self.guard(cb));grid.addWidget(button,i%2,i//2)
                row.addWidget(group,0,Qt.AlignmentFlag.AlignTop)
            row.addStretch();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.ribbon.addTab(scroll,icon('grid'),title)

    def estimator_params(self):
        result=super().estimator_params()
        if result is not None:
            for key,value in self.project.workspace.get('estimation_overrides',{}).items():
                if key in ('high_grade_restriction','dynamic_anisotropy'):result[key]=deepcopy(value)
        return result

    def record_step(self,tool,params):
        if getattr(self,'_recording',False):self._recorded_steps.append({'tool':tool,'params':deepcopy(params)})

    def cap_tool(self):
        from .geostat_tools import cap_analysis
        from .estimation import sample_support
        values=self.params('Top-cut — босгыг геологич сонгоно',{'Composite m':5,'Cap (blank=none)':''})
        if not values:return
        p=self.project;cap=float(values['Cap (blank=none)']) if values['Cap (blank=none)'].strip() else None
        def work(cancel):return cap_analysis(sample_support(p,float(values['Composite m'])),cap)
        def apply(report):
            self.record_step('cap_analysis',{'cap':cap,'composite_length':float(values['Composite m'])});self.show_rows('Top-cut / decile',report['deciles'])
            from .plot_widgets import show_histogram
            show_histogram(self,report['histogram'])
            if report['lognormal_probability']:self.chart('Lognormal probability',report['lognormal_probability'],'normal_score','log_grade')
        self.launch_task('Агуулгын шинжилгээ…',work,apply)

    def high_grade_tool(self):
        old=self.project.workspace.get('estimation_overrides',{}).get('high_grade_restriction') or {}
        values=self.params('Өндөр агуулгын зайн хязгаар — шинэ үнэлгээнд хэрэглэнэ',{'Threshold (blank=disabled)':old.get('threshold',''),'Radius m':old.get('radius_m',15)})
        if not values:return
        rule=None
        if values['Threshold (blank=disabled)'].strip():
            rule={'threshold':float(values['Threshold (blank=disabled)']),'radius_m':float(values['Radius m'])}
            if min(rule.values())<=0 or not all(np.isfinite(v) for v in rule.values()):raise ValueError('Positive threshold/radius required')
        p=deepcopy(self.project);p.workspace.setdefault('estimation_overrides',{})['high_grade_restriction']=rule;self.commit(p)

    def decluster_tool(self):
        from .geostat_tools import cell_decluster
        from .estimation import sample_support
        values=self.params('Cell declustering — grid shifts, жинг үнэлгээнд автоматаар хэрэглэхгүй',{'Composite m':5,'Cell X m':50,'Cell Y m':50,'Cell Z m':20})
        if not values:return
        p=self.project;size=[float(values['Cell '+a+' m']) for a in 'XYZ']
        def apply(report):
            self.record_step('decluster',{'size':size,'composite_length':float(values['Composite m'])});self.show_rows('Declustering — жингийн нийлбэр 1',
                 [{'sample':i+1,'weight':w,'declustered_mean':report['declustered_mean']} for i,w in enumerate(report['weights'])])
        self.launch_task('Declustering…',lambda cancel:cell_decluster(sample_support(p,float(values['Composite m'])),size),apply)

    def dynamic_tool(self):
        from .geostat_tools import DynamicOrientation
        values=self.params('Хувьсах эллипсоид — Python backend',{'Mode':['Load orientation recipe','Disable']})
        if not values:return
        recipe=None
        if values['Mode']!='Disable':
            path,_=QFileDialog.getOpenFileName(self,'Normal controls / signed-field gradient JSON','','JSON (*.json)')
            if not path:return
            if Path(path).stat().st_size>16_000_000:raise ValueError('Orientation recipe exceeds 16 MB')
            recipe=json.loads(Path(path).read_text(encoding='utf-8-sig'));DynamicOrientation(recipe)
        p=deepcopy(self.project);p.workspace.setdefault('estimation_overrides',{})['dynamic_anisotropy']=recipe;self.commit(p)

    def classification_tool(self):
        from .geostat_tools import propose_classes
        path,_=QFileDialog.getOpenFileName(self,'Төслийн ангиллын саналын дүрэм — баталгаажсан ангилал биш','','JSON (*.json)')
        if not path:return
        if Path(path).stat().st_size>128000:raise ValueError('Classification rules exceed 128 KB')
        rules=json.loads(Path(path).read_text(encoding='utf-8-sig'))['rules'];model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Estimate a block model first')
        def apply(result):
            updated,report=result;p=deepcopy(self.project);p.workspace['block_model']=updated;self.commit(p);self.record_step('classification_proposal',{'rules':rules});self.show_rows('Ангиллын САНАЛ — resource_class өөрчлөгдөөгүй',[report])
        self.launch_task('Ангиллын санал…',lambda cancel:propose_classes(model,rules),apply)

    def _closed_boundary(self):
        strings=[s for s in self.project.workspace.get('strings',[]) if s.get('closed')]
        i=self.choose('Хаалттай талбай',[s['name'] for s in strings])
        return strings[i] if i is not None else None

    def pattern_tool(self):
        from .daily_tools import survey_pattern
        polygon=self._closed_boundary()
        if polygon is None:return
        values=self.params('Сорьцын / хэмжилтийн цооногийн геометр — цэнэгийн тооцоогүй',{'Pattern':['Rectangular','Staggered'],'Spacing m':10,'Row spacing m':10,'Top Z m':100,'Bottom Z m':90,'Azimuth':90})
        if values:self.show_rows('Цооногийн тор — талбайн мэргэжилтэн хянана',survey_pattern(polygon['points'],float(values['Spacing m']),float(values['Row spacing m']),float(values['Top Z m']),float(values['Bottom Z m']),values['Pattern']=='Staggered',float(values['Azimuth'])))

    def cutfill_tool(self):
        from .daily_tools import tin_cut_fill
        meshes=self.project.workspace.get('meshes',[]);names=[f'{i+1}. '+m['name'] for i,m in enumerate(meshes)]
        a=self.choose('Өмнөх TIN',names)
        if a is None:return
        b=self.choose('Дараах TIN',names)
        if b is None:return
        values=self.params('TIN-to-TIN common coverage — эерэг нь Fill',{'Density t/m³ (blank=none)':''})
        if not values:return
        density=float(values['Density t/m³ (blank=none)']) if values['Density t/m³ (blank=none)'].strip() else None
        self.launch_task('TIN Cut / Fill…',lambda cancel:tin_cut_fill(meshes[a],meshes[b],density,cancel),lambda report:self.show_rows('Cut / Fill — зөвхөн давхцсан XY талбай',[report]))

    def digline_tool(self):
        from .daily_tools import ore_control_polygons
        model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Block model required')
        values=self.params('Блокийн хүдэр/хоосон/тодорхойгүй хил',{'Elevation m':model['blocks'][0]['z'],'Cutoff':.5})
        if not values:return
        folder=QFileDialog.getExistingDirectory(self,'DXF / Shapefile гаргах')
        if not folder:return
        crs=self.project.crs_code
        def work(cancel):
            from .daily_export import export_diglines
            rows=ore_control_polygons(model,float(values['Elevation m']),float(values['Cutoff']),cancel)
            if cancel():raise RuntimeError('Dig-line export cancelled')
            return export_diglines(rows,Path(folder)/('Diglines-'+uuid4().hex[:8]),crs)
        self.launch_task('Хил нэгтгэх…',work,lambda result:self.show_rows('Хүдэр/хоосон хил — олборлолтын заавар биш',[result]))

    def stereonet_tool(self):
        from .daily_tools import stereonet
        from .core import read_rows
        path,_=QFileDialog.getOpenFileName(self,'Ориентацтай CSV: dip_direction,dip — alpha/beta-г таахгүй','','CSV (*.csv)')
        if not path:return
        values=self.params('Stereonet — урьдчилсан геометрийн screening',{'Projection':['Schmidt','Wulff'],'Slope dip direction':0,'Slope dip':60,'Friction':30,'Lateral limit':20})
        if not values:return
        rows=read_rows(path,('dip_direction','dip'))
        report=stereonet(rows,values['Projection'],*[float(values[k]) for k in ('Slope dip direction','Slope dip','Friction','Lateral limit')])
        from .plot_widgets import show_stereonet
        show_stereonet(self,report);self.show_rows('Геотехникийн screening — FoS тооцоогүй',report['plane_checks']+report['wedge_candidates'])

    def map_tool(self):
        from .map_composer import export_map
        model=self.project.workspace.get('block_model',{});bounds=model.get('bounds',[0,0,0,100,100,100])
        values=self.params('Вектор план / зүсэлт — хувь масштаб, хянах штамп',{'View':['XZ','YZ','XY'],'Position m':(bounds[1]+bounds[4])/2,'Drillhole slab m':20,'Paper':['A3','A1','A0'],'Scale':'auto','Block labels':['Yes','No']})
        if not values:return
        folder=QFileDialog.getExistingDirectory(self,'PDF / SVG багц хадгалах')
        if not folder:return
        settings={**self.project.workspace.get('ebmz_report',{}),'view':values['View'],'position':float(values['Position m']),'slab_width':float(values['Drillhole slab m']),'paper':values['Paper'],'scale':values['Scale'],'block_labels':values['Block labels']=='Yes'}
        source=self.project;target=Path(folder)/('Plot-'+uuid4().hex[:8])
        self.launch_task('Вектор PDF / SVG…',lambda cancel:export_map(source,settings,target,cancel),lambda path:QMessageBox.information(self,'Зураг бэлэн',path))

    def contact_editor(self):
        from .contact_editor import edit_contacts
        edit_contacts(self)

    def methodology_tool(self):
        from .copilot_tools import methodology_draft
        dialog=QDialog(self);dialog.setWindowTitle('Аргачлалын баримтад тулгуурласан ноорог');dialog.resize(800,650);layout=QVBoxLayout(dialog);editor=QPlainTextEdit(methodology_draft(self.project,language()));layout.addWidget(editor)
        save=QPushButton('TXT хадгалах');layout.addWidget(save)
        def write():
            path=self.destination('Аргачлалын ноорог','txt')
            if path:Path(path).write_text(editor.toPlainText(),encoding='utf-8')
        save.clicked.connect(write);dialog.exec()

    def qaqc_advisor(self):
        from .quality_advisor import quality_advice,show_quality_charts
        data=self.project.workspace.get('qaqc_controls',{}).get('results',[])
        if not data:raise ValueError('Import laboratory QA/QC controls first')
        report=quality_advice(data);self.support.append('QA/QC зөвлөх',report['text']);show_quality_charts(self,data);self.show_rows('QA/QC зөвлөх — шийдвэрийг мэргэжилтэн гаргана',report['issues'])

    def copilot_tool(self):
        self.support.show();self.assistant_tabs.setCurrentWidget(self.help_scroller);self.support.mode.setCurrentIndex(1);self.support.question.setFocus()

    def run_copilot_question(self,question,dock):
        from .copilot_tools import parse_query,validate_plan,model_query,disk_query
        from .local_engine import LocalEngine
        import re
        if re.search(r'(?i)\b(or|not)\b|эсвэл|биш|!=|<>',question):raise ValueError('Only explicit AND filters are currently supported')
        source=self.project;model=source.workspace.get('block_model');stores=source.workspace.get('disk_block_stores',[])
        if not model and len(stores)!=1:raise ValueError('Open a desktop block model or attach exactly one disk store')
        def work(worker):
            import re
            element=re.search(r'(?i)\b(Au|Cu|Ag|Zn|Pb)\s*(?=[><=≥≤])',question)
            normalized=question
            if element:
                channel=source.workspace.get('dh_import_report',{}).get('channel') or []
                if len(channel)<2 or not re.search(r'(?i)(?:^|[^a-z])'+element.group(1)+r'(?:[^a-z]|$)',channel[1]):raise ValueError('Select and verify the requested assay element channel first, or use grade/агуулга for the active channel')
                normalized=question[:element.start()]+question[element.start():].replace(element.group(1),'grade',1)
            domains=sorted({str(b['domain']) for b in model['blocks'] if b.get('domain')}) if model else []
            if not model:
                import sqlite3
                db=sqlite3.connect(Path(stores[0]).resolve().as_uri()+'?mode=ro',uri=True)
                try:domains=[r[0] for r in db.execute('SELECT DISTINCT domain FROM blocks WHERE domain IS NOT NULL LIMIT 201')]
                finally:db.close()
            try:plan=parse_query(normalized,domains)
            except ValueError:
                if not Path(dock.model_path).is_file() or not Path(dock.engine_path).is_file():raise
                if dock.engine is None:dock.engine=LocalEngine(dock.engine_path,dock.model_path)
                dock.engine.start(worker.cancelled.is_set)
                messages=[{'role':'system','content':'Return JSON only: {"tool":"filter_blocks","conditions":[{"field":"grade","op":">","value":0.5}],"limit":50000}. Allowed fields x,y,z,grade,density,domain. AND only. domain equality only. Never SQL/Python. Grade is active project channel; do not assume Au/Cu. Available domains: '+json.dumps(domains,ensure_ascii=False)}, {'role':'user','content':question}]
                plan=validate_plan(json.loads(dock.engine.complete(messages,max_tokens=512)))
            if worker.cancelled.is_set():raise RuntimeError('Copilot cancelled')
            result=model_query(model,plan,source.grade_unit,worker.cancelled.is_set) if model else disk_query(stores[0],plan,worker.cancelled.is_set)
            if model:result['preview']['grid_angles']=model.get('grid_angles',[90,0,0])
            return result
        def done(result):
            if source is not self.project:dock.append('Копилот','Төсөл өөрчлөгдсөн. Дахин ажиллуулна уу.');return
            dock.append('Копилот',json.dumps({'query':result['plan'],'totals':result['totals'],'scope':result['scope']},ensure_ascii=False,indent=2))
            if result['rows']:
                from .large_view import LargePreviewFactory
                LargePreviewFactory.show(self,result['preview'],'Копилот — зөвхөн шүүсэн preview');self.show_rows('Копилот — эх өгөгдөл өөрчлөгдөөгүй',result['rows'])
        dock.start_worker(work,done)

    def record_start(self):
        self._recording=True;self._recorded_steps=[{'tool':'validate','params':{}}];self.statusBar().showMessage('Workflow бичлэг эхэллээ — дэмжсэн хэрэгслийн батлагдсан параметрүүдийг хадгална.')

    def record_save(self):
        steps=getattr(self,'_recorded_steps',[])
        if not steps:raise ValueError('Start a recording and run supported tools first')
        path=self.destination('Workflow JSON','json')
        if path:Path(path).write_text(json.dumps({'version':1,'name':self.project.name,'steps':steps},ensure_ascii=False,indent=2),encoding='utf-8');self._recording=False

    def replay_tool(self):
        from .workflow import validate_recipe,run_workflow
        path,_=QFileDialog.getOpenFileName(self,'Re-run All — зөвхөн дэмжсэн JSON алхам','','JSON (*.json)')
        if not path:return
        if Path(path).stat().st_size>1_000_000:raise ValueError('Workflow recipe exceeds 1 MB')
        recipe=validate_recipe(json.loads(Path(path).read_text(encoding='utf-8-sig')));target=None
        if any(s['tool']=='report' for s in recipe['steps']):
            root=QFileDialog.getExistingDirectory(self,'Workflow тайлан хадгалах')
            if not root:return
            target=Path(root)/('Workflow-'+uuid4().hex[:8])
        source=self.project
        def apply(result):
            candidate,log=result;self.commit(candidate);self.show_rows('Workflow — нэг Undo алхам',[{'step':r['step'],'tool':r['tool'],'completed':True} for r in log])
        self.launch_task('Re-run All…',lambda cancel,progress:run_workflow(source,recipe,target,cancel,progress),apply,with_progress=True)
