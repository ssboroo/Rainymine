"""Explicitly bounded v2 engineering workflows in the native desktop."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4
from PySide6.QtWidgets import QFileDialog,QMessageBox
from .i18n import tr


class V2Tools:
    def build_v2_menu(self):
        menu=self.menuBar().addMenu('Мэргэжлийн баталгаажуулалт')
        for title,callback in [('CP харьцуулалтын багц…',self.cp_validation_pack),
                               ('Том CSV → дискэн блок сан…',self.disk_csv_import),
                               ('Геологийн үеийн дараалал JSON…',self.chronology_import),
                               ('Эх программын эргэлт хөрвүүлэх…',self.orientation_convert)]:
            self.action(menu,title,lambda cb=callback:self.guard(cb))

    def orientation_convert(self):
        from .orientation import source_orientation
        path,_=QFileDialog.getOpenFileName(self,'Тэнхлэг / ENU matrix / explicit Euler JSON','','JSON (*.json)')
        if not path:return
        if Path(path).stat().st_size>128000:raise ValueError('Orientation JSON exceeds 128 KB')
        raw=Path(path).read_bytes();definition=json.loads(raw.decode('utf-8-sig'))
        source=definition.get('source_software','Other')
        values=self.params('Эх программ — өнцгийн дүрмийг JSON-оос ил тод авна',
                           {'Source software (provenance only)':[source]+[s for s in ('Micromine','Leapfrog','Datamine','GSLIB','Other') if s!=source],
                            'Source version':definition.get('source_version','')})
        if not values:return
        definition['source_software']=values['Source software (provenance only)'];definition['source_version']=values['Source version']
        result=source_orientation(definition)
        import hashlib
        result['source_definition_file_sha256']=hashlib.sha256(raw).hexdigest()
        self.show_rows('ENU хөрвүүлэлт — vendor fixture хяналт шаардлагатай',[result])
        return result

    def disk_csv_import(self):
        from .disk_import import import_disk_csv
        source,_=QFileDialog.getOpenFileName(self,'Том блок CSV — зөвхөн эргүүлээгүй төв/хэмжээ','','CSV (*.csv)')
        if not source:return
        with open(source,encoding='utf-8-sig',newline='') as stream:
            import csv
            headers=next(csv.reader(stream),[])
        if not headers or len(headers)>256:raise ValueError('Invalid block CSV headers')
        required=('x','y','z','dx','dy','dz','grade')
        values=self.params('Том CSV mapping — 20 сая хүртэл; leaf давхцал баталгаажаагүй',
                           {**{k:([k]+[h for h in headers if h!=k] if k in headers else headers) for k in required},
                            'density':['—']+headers,'domain':['—']+headers})
        if not values:return
        mapping={k:v for k,v in values.items() if v!='—'}
        destination,_=QFileDialog.getSaveFileName(self,'Шинэ дискэн сан','Imported.rmdb','RAINYMINE block database (*.rmdb)')
        if not destination:return
        if QMessageBox.question(self,'Геометр ба нэгж',
                'Эх CSV нь эргүүлээгүй блокийн world XYZ төв, метрийн DX/DY/DZ мөн үү?\n'
                'CRS: '+self.project.crs_code+' · '+self.project.grade_unit+'\n'
                'Эргэлттэй торонд энэ импортыг хэрэглэхгүй. Давхцал, regular-grid topology баталгаажаагүй.')!=QMessageBox.StandardButton.Yes:return
        crs,unit=self.project.crs_code,self.project.grade_unit
        def apply(report):
            self.link_disk(report['path']);self.show_rows('Том CSV импорт — эх файл хадгалагдсан',[report])
        self.launch_task('CSV → дискэн сан…',lambda cancel,progress:import_disk_csv(source,destination,mapping,crs,unit,cancel=cancel,progress=progress),apply,with_progress=True)

    def chronology_import(self):
        from .chronology import apply_chronology
        model=self.project.workspace.get('block_model')
        if not model:raise ValueError('Эхлээд блок загвар үүсгэнэ үү.')
        path,_=QFileDialog.getOpenFileName(self,'Хөгшнөөс залуу руу: intrusion / vein / stratigraphy / erosion','','JSON (*.json)')
        if not path:return
        if Path(path).stat().st_size>16_000_000:raise ValueError('Chronology JSON exceeds 16 MB')
        recipe=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        def apply(result):
            updated,report=result;p=deepcopy(self.project);p.workspace['block_model']=updated
            for key in ('tonnage_grade','schedule','optimization','stope_box_optimization','joint_blend_schedule','external_benchmark'):p.workspace.pop(key,None)
            p.workspace.setdefault('engineering_runs',[]).append({'tool':'chronological ownership','report':report})
            self.commit(p)
            from .large_view import LargePreviewFactory
            import numpy as np
            names=sorted({b['domain'] for b in updated['blocks'] if b['domain']!='UNASSIGNED'})
            codes={name:i+1 for i,name in enumerate(names)}
            payload={'kind':'blocks','xyz':np.array([[b[k] for k in 'xyz'] for b in updated['blocks']]),
                     'sizes':np.array([[b[k] for k in ('dx','dy','dz')] for b in updated['blocks']]),
                     'grade':np.array([codes.get(b['domain'],np.nan) for b in updated['blocks']]),
                     'source_index':np.arange(len(updated['blocks']),dtype=np.int64),
                     'source_points':len(updated['blocks']),'matched_before_sampling':len(updated['blocks']),
                     'stride':1,'crs':p.crs_code,'grid_angles':updated.get('grid_angles',[90,0,0]),
                     'categories':{code:name for name,code in codes.items()},'scalar_title':tr('Геологийн материал')}
            LargePreviewFactory.show(self,payload,'Геологийн үеийн дараалал — блокийн төвийн харьяалал')
            self.show_rows('Геологийн харьяалал — агуулгыг дахин үнэлнэ',[report])
        self.launch_task('Геологийн дараалал…',lambda cancel:apply_chronology(model,recipe,cancel),apply)

    def cp_validation_pack(self):
        from .cp_validation import create_validation_pack
        if not self.project.workspace.get('block_model'):raise ValueError('Блок загвар алга.')
        paths=[]
        for title,pattern in [('Гадаад блок reference CSV: x,y,z,dx,dy,dz,grade','CSV (*.csv)'),
                              ('Гадаад Minimum Curvature reference: hole_id,depth,x,y,z','CSV (*.csv)'),
                              ('Reference provenance / параметрийн JSON','JSON (*.json)')]:
            path,_=QFileDialog.getOpenFileName(self,title,'',pattern)
            if not path:return
            paths.append(path)
        values=self.params('CP хяналт — хувь тохирол нь стандартын баталгаа биш',
                           {'Coordinate tolerance m':.01,'Grade absolute tolerance':.001,
                            'Relative tolerance 0–1':.02,'Swath width m':50,
                            'Cutoffs ascending':'0,0.2,0.5,1','Fallback density t/m³ (blank=none)':''})
        if not values:return
        root=QFileDialog.getExistingDirectory(self,'CP хяналтын багц хадгалах')
        if not root:return
        settings={'coordinate_m':float(values['Coordinate tolerance m']),
                  'grade_absolute':float(values['Grade absolute tolerance']),
                  'relative':float(values['Relative tolerance 0–1']),
                  'swath_width_m':float(values['Swath width m']),
                  'cutoffs':[float(c.strip()) for c in values['Cutoffs ascending'].split(',')],
                  'density':values['Fallback density t/m³ (blank=none)'].strip()}
        destination=Path(root)/('RAINYMINE-CP-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6]);source=self.project
        self.launch_task('CP reference шалгалт…',lambda cancel:create_validation_pack(source,*paths,destination,settings,cancel),
                         lambda report:self.show_rows('CP хяналт хүлээгдэж байна',[report]))
