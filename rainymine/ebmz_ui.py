"""One-click review pack after one-time project metadata/layout setup."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from PySide6.QtWidgets import QFileDialog, QMessageBox
from .background import Task
from .ebmz_report import export_pack, number
from .i18n import tr


class EbmzTools:
    def ebmz_settings(self):
        current = self.project.workspace.get('ebmz_report', {})
        fields = [('commodity','Ашигт малтмал',''),('company','Байгууллага',''),
                  ('license','Тусгай зөвшөөрлийн дугаар',''),('author','Боловсруулсан',''),
                  ('reviewer','Хянасан',''),('cutoff','Заагийн агуулга',0),
                  ('density','Орлуулах нягт т/м³ (хоосон = хэрэглэхгүй)',''),
                  ('scale','A3 масштаб (auto эсвэл 1000 гэх мэт)','auto'),
                  ('section_x','YZ зүсэлтийн X (хоосон = загварын төв)',''),
                  ('section_y','XZ зүсэлтийн Y (хоосон = загварын төв)','')]
        result = self.params(tr('ЭБМЗ багцын тохиргоо — хянах төсөл'),
                             {tr(label):current.get(key,default) for key,label,default in fields})
        if not result:
            return False
        settings = {key:result[tr(label)].strip() for key,label,_ in fields}
        cutoff = number(settings['cutoff'],'Заагийн агуулга')
        if cutoff < 0:
            raise ValueError('Заагийн агуулга сөрөг байж болохгүй.')
        if settings['density']:
            number(settings['density'],'Нягт',True)
        if settings['scale'] != 'auto':
            number(settings['scale'],'Масштаб',True)
        for key in ('section_x', 'section_y'):
            if settings[key]:
                number(settings[key],'Зүсэлтийн байрлал')
            else:
                settings.pop(key)
        if any(len(str(v))>200 for v in settings.values()):
            raise ValueError('Талбар бүр 200 хүртэл тэмдэгт байна.')
        folder = QFileDialog.getExistingDirectory(self,tr('Тайлангийн багц хадгалах үндсэн хавтас'),current.get('output_root',''))
        if not folder:
            return False
        settings['output_root'] = folder
        candidate = deepcopy(self.project)
        candidate.workspace['ebmz_report'] = settings
        self.commit(candidate)
        return True

    def ebmz_export(self):
        def run():
            if self._engineering_tasks:
                raise ValueError('Эхлээд ажиллаж буй тооцоог дуусгах эсвэл цуцална уу.')
            if not self.project.workspace.get('block_model',{}).get('blocks'):
                raise ValueError('Блок загвар алга. Эхлээд загвар үүсгэх эсвэл импортолно уу.')
            settings = self.project.workspace.get('ebmz_report')
            if not settings:
                if not self.ebmz_settings():
                    return
                settings = self.project.workspace['ebmz_report']
            settings = dict(settings)
            root = Path(settings.pop('output_root'))
            target = root/('RAINYMINE-EBMZ-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
            source = self.project
            Task(self,tr('ЭБМЗ хяналтын багц үүсгэж байна…'),
                 lambda cancel:export_pack(source,settings,target,cancel),
                 lambda path:QMessageBox.information(self,tr('ЭБМЗ багц бэлэн'),
                     tr('Хүснэгт, A4 тайлан, A3 зүсэлт, хяналтын жагсаалт үүслээ. Мэргэжилтний хяналт шаардлагатай.')+'\n\n'+path))
        self.guard(run)
