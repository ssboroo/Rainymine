"""Reversible display localization. Scientific data, field keys and file formats stay intact."""
import re
from PySide6.QtCore import QObject, QEvent, QSettings, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QLabel, QAbstractButton, QGroupBox,
    QLineEdit, QTabWidget, QTreeWidget, QTableWidget, QWidget)

_LANGUAGE = 'mn'
CATALOG = dict(line.split('|', 1) for line in '''Төсөл|Project
Өрөмдлөг|Drilling
Геологи|Geology
Блок загвар|Block model
Уурхайн төлөвлөлт|Mine planning
Харагдац|View
Файл|File
Өгөгдөл|Data
Экспорт|Export
Огтлол|Section
Тусламж|Help
Самбарууд|Panels
Лиценз|License
Шинэ|New
Нээх|Open
Хадгалах|Save
Оруулах|Import
Гаргах|Export
Давхарга|Layer
Давхаргууд|Layers
Хэмжих|Measure
Хайх|Search
Шилжүүлэх|Pan
Эргүүлэх|Rotate
Томруулах|Zoom
Сонгох|Select
Тохиргоо|Settings
Шинэ төсөл|New project
Төсөл нээх…|Open project…
Өөрөөр хадгалах…|Save as…
Жишээ төсөл|Example project
Төслийн тохиргоо|Project settings
Цооногийн амсар|Drillhole collars
Замналын хэмжилт|Survey stations
Сорьцын агуулга|Assay grades
Гадаргын XYZ|Surface XYZ
Цооног гараар нэмэх…|Add drillhole…
Өгөгдлийн шалгалт|Validate data
Замналын координат CSV…|Trajectory coordinates CSV…
Уртаар жигнэсэн композит CSV…|Length-weighted composites CSV…
3D зураг PNG…|3D image PNG…
Цооногийн геометр VTP…|Drillhole geometry VTP…
Төслийн тайлан HTML…|Project report HTML…
Ашиглах заавар|User guide
Үндсэн үйлдэл|Main actions
Төслийн өгөгдөл|Project data
ТӨСЛИЙН ДАВХАРГУУД|PROJECT LAYERS
ХИЙМЭЛ ОЮУНЫ ТУСЛАХ|LOCAL ASSISTANT
Локал туслах|Local assistant
ОФФЛАЙН|OFFLINE
Бэлэн|Ready
Гурван хэмжээст|3D
Төлөвлөгөө|Plan
Цооногууд|Drillholes
Блокийн өгөгдөл|Block data
Цооногийн өгөгдөл|Drillhole data
Сорьцууд|Assays
Төслийн өгөгдөл|Project data
Геометр / Уурхай|Geometry / Mine
Хагарлууд|Faults
Уурхайн зам|Haul roads
Гадарга|Surface
Гадаргын загвар|Surface model
Цооног / сорьц|Drillholes / assays
Амсрын цэгүүд|Collar points
Давхарга|Layer
Элемент|Elements
Тунгалагшил|Opacity
Бүтэн гадарга|Surface
Торон дүрслэл|Wireframe
Цэг|Points
Өнгө…|Color…
Агуулгын өнгө|Grade colors
Давхаргын өнгө|Layer color
Шошго|Labels
Үйлдэл хайх|Command search
Үйлдэл хайх · Ctrl K|Search commands · Ctrl K
Хэрэгслийн мөр хураах / дэлгэх|Collapse / expand ribbon
3D төвлөрсөн горим|3D focus mode
Өгөгдлийн хүснэгт|Data table
Эхлэх|Get started
Өгөгдөл оруулах|Import data
Загвар тохируулах|Configure model
Тохиргоо хийх|Configure
Алдаа засах|Troubleshoot
① Өгөгдөл оруулах|① Import data
② Загвар тохируулах|② Configure model
③ Чанар шалгах|③ Check quality
Амсар, замнал, сорьцын CSV мэдээллээ импортлоно.|Import collar, survey and assay CSV files.
Блокийн хэмжээ, домэйн, үнэлгээний параметрээ тохируулна.|Configure block size, domains and estimation parameters.
Сорьцын бүрхэлт, интервалын алдааг шалгана.|Check assay coverage and interval errors.
Программ ашиглах, тохируулах, алдаа засах локал туслах.|Local help for application use, configuration and troubleshooting.
Шууд заавар сонгох эсвэл асуултаа бичнэ үү.|Choose a guide or enter a question.
Цооногийн нэрээр хайх|Search drillhole names
Цооног хайх…|Search drillholes…
Өгөгдөл хайх…|Search layers…
Дугаар|ID
Зүүн (м)|Easting (m)
Хойд (м)|Northing (m)
Өндөр (м)|Elevation (m)
Агуулга|Grade
Нягт (т/м³)|Density (t/m³)
Чулуулаг|Lithology
Сонгосон блокийн шинж|Selected block properties
Сонгосон давхаргын шинж|Selected layer properties
Нэр|Name
Төрөл|Type
Хаах|Close
Зогсоох|Stop
Болих|Cancel
Цуцлах|Cancel
Нэмэх|Add
Устгах|Delete
Тооцох / хадгалах|Calculate / save
CSV экспорт|Export CSV
Буцаах|Undo
Сэргээх|Redo
Амсар|Collars
Замнал|Survey
Сорьц|Assays
Литологи|Lithology
Хяналтын сорьц|QA/QC controls
Шалгах|Validate
Композит|Composites
Замнал CSV|Trajectory CSV
Гадарга / Биет|Surface / Solid
Туршилтын загвар|Prototype
Нэмэлт хэрэгсэл|More tools
Давхарга ба огтлол|Layers and sections
Харагдац тохируулах|Display settings
Домэйн|Domain
Домэйны хүрээ|Domain polygon
Үнэлгээ|Estimation
Хөндлөн шалгалт|Cross-validation
Гадаад харьцуулалт|External benchmark
Хагарлын хавтгай|Fault plane
Вариограмм тохируулах|Variogram fitting
Блок загвар үүсгэх|Create block model
Нягт / Заагийн агуулга|Density / Cutoff
Ил уурхайн мөргөцөг|Open-pit benches
Хүчин чадлын хуваарь|Capacity schedule
Хос харагдац|Split viewport
Хиймэл оюуны туслах|Local assistant
RBF хүдрийн гадарга|RBF grade surface
Ил уурхайн оновчлол|Pit optimization
Өгөгдлийн сан унших|Read database
Координат хөрвүүлэх|Transform CRS
Шугам / Олон өнцөгт|String / Polygon
Тасралтын шугам|Breakline TIN
Тор шалгах|Validate mesh
Дээрээс|Top
Урдаас|Front
Хажуугаас|Side
Төвлөрүүлэх|Fit all
Файл сонгох|Choose files
Анх тохируулах · 1.28 GB|Initial setup · 1.28 GB
Асуух|Ask
Зогсоох / Санах ой чөлөөлөх|Stop / Release memory
Чат цэвэрлэх|Clear chat
Зааврыг шууд үзэх — модель шаардахгүй|Open a guide — no model required
Жишээ: CSV импортын алдааг яаж засах вэ?|Example: How do I fix a CSV import error?
Та|You
Туслах|Assistant
Rainymine заавар|Rainymine guide
Local AI туслах|Local AI assistant
Хугацаа ба идэвхжүүлэлт…|Status and activation…
7 хоногийн туршилтыг эхлүүлэх|Start 7-day trial
Одоогийн төслөө хадгалах…|Save current project…
Лицензийн файл сонгох…|Choose license file…
Үргэлжлүүлэх|Continue
Лицензийн тохиргоо|License configuration
Тор|Grid
Тасалж харах|Cutaway
Блокийн ирмэг|Block edges
Гадаргын тор|Terrain wireframe
Камер сэргээх|Reset camera
Бүх хэрэгсэл|All tools
Хэл|Language
Хадгалсан огтлолууд|Saved sections
Огтлол хадгалах|Save section
Өмнөх огтлол|Previous section
Дараах огтлол|Next section
Блок модель|Block model
Модель|Model
Импорт|Import
Чанар|Quality
Гаргалгаа|Output
Файл|File
Түүх|History
Камер|Camera
Ажлын орчин|Workspace
Төлөвлөлт|Planning
Дэлгэцийн тохиргоо|Display preferences
Төслийн бодит блокийн өгөгдөл. — нь мэдээлэл байхгүйг заана.|Actual project block data. — means no value is available.
3D дээр цооног эсвэл блок дарж сонгоно.|Click a drillhole or block in 3D to select it.
Ажлын орчныг ачаалж байна…|Loading workspace…
Программ эхэлж байна…|Starting application…
3D дүрслэлийн модулиудыг ачаалж байна…|Loading 3D rendering modules…
Төслийн өгөгдөл болон ажлын орчныг бэлтгэж байна…|Preparing project data and workspace…
3D ажлын орчин бэлэн боллоо|3D workspace ready
'''.strip().splitlines())
CATALOG.update(dict(line.rsplit('|', 1) for line in '3 зүсэлт / Бүх блок|3 slices / All blocks\nDXF импорт|DXF import\nDXF экспорт|DXF export\nExcel импорт|Excel import\nMILP Оновчлол|MILP optimization\nOBJ импорт|OBJ import\nOBJ экспорт|OBJ export\nSTL импорт|STL import\nSTL экспорт|STL export\nVTP геометр|VTP geometry\nX / Y / Z зүсэлт|X / Y / Z slices\nPNG зураг|PNG image\nАгуулга / Литологи|Grade / Lithology\nБагана тохируулах|Column mapping\nБлок CSV экспорт|Block CSV export\nБосоо зүсэлтийн шүүлтүүр|Vertical slab filter\nГадарга XYZ|Surface XYZ\nГадаргын TIN|Surface TIN\nГадаргын XYZ CSV импорт…|Import surface XYZ CSV…\nГеометр засах|Edit geometry\nДавхаргын самбар|Layer panel\nДалд уурхайн Малталт|Underground drive\nЗаавар|Guide\nЗай хэмжих|Measure distance\nЗам / Тээвэр|Road / Haulage\nЗамналын хэмжилт CSV импорт…|Import survey CSV…\nЗасвар|Edit\nЗүсэлтийн зузаан|Slab width\nЛокал метр  |  X —  Y —  Z —|Local metres  |  X —  Y —  Z —\nНормалын азимут|Normal azimuth\nОгтлол нээх|Open section\nСорьц CSV|Assay CSV\nСорьцын бүрхэлт|Assay coverage\nСорьцын агуулга CSV импорт…|Import assay CSV…\nТөвөөс шилжилт|Offset from origin\nТөслийн тайлан|Project report\nТөсөл нээх|Open project\nХоёр цэгийн зай хэмжих|Measure point-to-point distance\nХүснэгт засвар|Edit grid\nЦооног CSV|Collar CSV\nЦооног ба сорьцын агуулга|Drillholes and assay grades\nЦооног сонгож мэдээллийг харна уу.|Select a drillhole to inspect its data.\nЦооногийн амсар CSV импорт…|Import collar CSV…\nШилжилт нь төслийн 3D эхээс хэмжигдэнэ. Нормал: хойноос цагийн зүүний дагуу. Сорьцгүй хэсэг саарал.|Offset is measured from the project 3D origin. Normal azimuth is clockwise from north. Unsampled intervals are gray.\n● ОФФЛАЙН  |  метр|● OFFLINE  |  metres\n＋ Шинэ|＋ New\n3D геометр дээр 2 цэг сонгоно.|Select two points on the 3D geometry.\nЗүүн товч: эргүүлэх   •   Дугуй: томруулах   •   Shift + зүүн: зөөх   •   Хүснэгтээс цооног сонгоно|Left: rotate   •   Wheel: zoom   •   Shift + left: pan   •   Select drillholes from the table\nЛицензийн файл сонгож идэвхжүүлэх…|Select and activate a license file…\nRAINYMINE — Лиценз|RAINYMINE — License\nRAINYMINE · 7 хоногийн туршилт|RAINYMINE · 7-day trial\nТөхөөрөмжийн дугаар — лиценз авахдаа хуулж илгээнэ:|Device ID — copy this when requesting a license:\nЛиценз ба дэмжлэг: RAINY STUDIO · 90220101|Licensing and support: RAINY STUDIO · 90220101\nЛиценз сонгох|Select license\nИдэвхжүүлэх боломжгүй|Activation failed'.splitlines()))

CATALOG['Локал метр  |  X —  Y —  Z —']='Local metres  |  X —  Y —  Z —'
CATALOG['● ОФФЛАЙН  |  метр']='● OFFLINE  |  metres'

CATALOG.update({'Дуусах хугацаа (UTC): ': 'Expires (UTC): ', '7 хоногийн туршилтыг эхлүүлэх эсвэл лицензээ идэвхжүүлнэ үү.': 'Start your 7-day trial or activate a license.', '7 хоногийн туршилтын хугацаа дууссан. Лиценз идэвхжүүлнэ үү.': 'Your 7-day trial has expired. Activate a license to continue.', 'Туршилт эхлүүлснээс хойш 168 цаг үргэлжилнэ. Хугацаа дуусахад лиценз шаардлагатай.\nТөслийн файл устахгүй. Интернэт болон төлбөрийн мэдээлэл шаардахгүй.': 'The trial lasts 168 hours from activation. A license is required after expiry.\nProject files are not deleted. Internet and payment details are not required.'})

# Multi-line ribbon labels share the same catalog, not a second language state.
CATALOG.update(dict(line.split('|',1) for line in '''Хадгалаагүй төсөл сэргээх…|Recover unsaved project…
Ажлын урсгал|Workflow
Импорт → QA/QC → Үнэлгээ → Экспорт…|Import → QA/QC → Estimate → Export…
Дискэн блок сан|Disk block store
Том блок сан үүсгэх…|Create large block store…
Блок сан холбох…|Link block store…
Дискэн IDW үнэлгээ…|Disk IDW estimation…
Дискэн блок засах…|Edit disk block…
Дискэн өөрчлөлт буцаах|Undo disk change
Дискэн өөрчлөлт сэргээх|Redo disk change
Дискэн блок 3D харах…|Disk block 3D preview…
Дискэн тонн / металл…|Disk tonnage / metal…
Дискэн блок CSV экспорт…|Export disk blocks CSV bundle…
Хяналттай инженерийн загвар|Bounded engineering scenarios
Давхарга / хавтгай хагарлын шилжилт…|Stratigraphy / planar fault slip…
Давхаргаар тусгаарласан IDW үнэлгээ…|Layer-isolated IDW estimation…
Овоолго / дахин таталтын баланс…|Stockpile / reclaim balance…
Замын хэсэгчилсэн тээвэр…|Segment haulage…
Зангилааг бусад шугамд тааруулах…|Snap vertex to other strings…
Хадгалаагүй төсөл сэргээх|Recover unsaved project
Нөөцөөс шинэ хуулбар нээнэ. Эх файл өөрчлөгдөхгүй.|Open a copy from recovery. The original file is preserved.
Хаах|Close
Ажлын урсгалын хяналт|Workflow review
Дискэн блок сан холбох|Link disk block store
Дискэн блок сан|Disk block store
Дискэн grid үүсгэж байна…|Creating disk grid…
Дискэн IDW…|Disk IDW…
Дискэн тайлан…|Disk report…
Дискэн 3D preview…|Disk 3D preview…
Дискэн CSV экспорт…|Disk CSV export…
Экспортын CRS / нэгж|Export CRS / units
Тонн / металл — ангилаагүй|Tonnage / metal — unclassified
Овоолго / дахин таталт|Stockpile / reclaim
Хэсэгчилсэн тээвэр|Segment haulage'''.splitlines()))

def tr(text):
    if _LANGUAGE == 'mn' or not isinstance(text, str):
        return text
    if text in CATALOG:
        return CATALOG[text]
    trial = re.fullmatch(r'Туршилтын лиценз — (\d+) цаг үлдсэн\.', text)
    if trial:return f'Trial license — {trial.group(1)} hours remaining.'
    if text.startswith('Идэвхтэй лиценз: '):return 'Active license: '+text[len('Идэвхтэй лиценз: '):]
    flat = text.replace('\n', ' ')
    if flat in CATALOG:
        return CATALOG[flat]
    for source, target in (('Агуулга (', 'Grade ('), ('Блок загвар · ', 'Block model · '),
                           ('Блок #', 'Block #')):
        if text.startswith(source):
            return target + text[len(source):]
    if re.fullmatch(r'[\d,]+ блок', text):
        return text[:-4] + 'blocks'
    return text


def language():
    return _LANGUAGE


class UiLocalizer(QObject):
    """Localize display properties only; never translate editable text or domain values."""
    def __init__(self, parent):
        super().__init__(parent)
        self._busy = False
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget):
            self.apply(obj)
        return False

    def property_text(self, obj, getter, setter, key):
        value = getter()
        if not isinstance(value, str) or not value:
            return
        cached = obj.property('_locale_' + key)
        if cached and value == cached[1]:
            source = cached[0]
        else:
            source = value
        translated = tr(source)
        if value != translated:
            setter(translated)
        obj.setProperty('_locale_' + key, [source, translated])

    def apply(self, root):
        if self._busy:
            return
        self._busy = True
        try:
            objects = [root, *root.findChildren(QObject)]
            for obj in objects:
                if isinstance(obj, QWidget):
                    self.property_text(obj, obj.windowTitle, obj.setWindowTitle, 'window')
                    self.property_text(obj, obj.toolTip, obj.setToolTip, 'tooltip')
                if isinstance(obj, (QLabel, QAbstractButton, QAction)):
                    # Project titles and user-authored values are not UI strings.
                    if not obj.property('userText'):
                        self.property_text(obj, obj.text, obj.setText, 'text')
                if isinstance(obj, QGroupBox):
                    self.property_text(obj, obj.title, obj.setTitle, 'group')
                if isinstance(obj, QLineEdit):
                    self.property_text(obj, obj.placeholderText, obj.setPlaceholderText, 'placeholder')
                if isinstance(obj, QTabWidget):
                    for index in range(obj.count()):
                        self.property_text(obj.widget(index), lambda i=index: obj.tabText(i),
                                           lambda text, i=index: obj.setTabText(i, text), 'tab')
            # Deliberately exclude item models and combo-box values: these can contain
            # geological names or option keys used by calculations.
        finally:
            self._busy = False


def set_language(code, root=None, persist=True):
    global _LANGUAGE
    if code not in ('mn', 'en'):
        raise ValueError('Unsupported language')
    _LANGUAGE = code
    if persist:
        QSettings('Rainy Studio', 'RAINYMINE').setValue('ui/language', code)
    if root is not None:
        root.localizer.apply(root)
    app = QApplication.instance()
    if app:
        for widget in app.topLevelWidgets():
            if root is not None:
                root.localizer.apply(widget)

CATALOG.update({'Төслийн багц':'Project bundle','Төслийн бүрэн багц хадгалах…':'Save complete project bundle…','Төслийн багц сэргээх…':'Restore project bundle…'})

CATALOG.update({'Муруй хагарлын сүлжээ JSON…':'Curved fault network JSON…','Дискэн Pseudoflow pit…':'Disk pseudoflow pit…','Pit RF хувилбар / үе шат…':'Pit RF scenarios / phases…'})

CATALOG.update({'Шинж':'Properties','Шинж ба туслах':'Properties and help','3D эсвэл хүснэгтээс блок сонгоно уу.':'Select a block in 3D or the table.'})

CATALOG.update({'Тоо':'Count','Эзлэхүүн (м³)':'Volume (m³)','Төлөв':'Status'})
