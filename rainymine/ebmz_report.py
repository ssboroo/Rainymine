"""Reviewable Mongolian reporting pack; never an EBМЗ approval or reserve certificate.

CSV tables and vector A3 layouts use source blocks without re-estimating grades.
Only axis-aligned models are currently supported for exact plane intersections.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import html
import json
import math
import shutil
import tempfile

PROFILE = 'rainymine-ebmz-review-1'
NOTICE = 'ХЯНАХ ТӨСӨЛ • ЭБМЗ-өөр баталгаажсан тайлан биш'
SOURCES = [
    'https://legalinfo.mn/mn/detail?lawId=16230812497421',
    'https://mrpam.gov.mn/page/ashigt-maltmalyn-khaiguul',
    'https://mmhi.gov.mn/wp-content/uploads/2022/12/Аргачилсан-зөвлөмж-Боть-1.pdf',
]


def number(value, name, positive=False):
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(name + ': тоон утга шаардлагатай.') from None
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(name + ': хязгаартай, зөв утга оруулна уу.')
    return value


def build_tables(project, settings, cancel=lambda: False):
    model = project.workspace.get('block_model') or {}
    blocks = model.get('blocks', [])
    if not blocks:
        raise ValueError('Блок загвар алга. Эхлээд загвар үүсгэх эсвэл импортолно уу.')
    if len(blocks) > 200000:
        raise ValueError('Хэвлэх багцын одоогийн хязгаар 200,000 блок. Том загварыг хэсэгчилнэ үү.')
    if any(abs(a-b) > 1e-8 for a,b in zip(model.get('grid_angles', [90,0,0]), [90,0,0])):
        raise ValueError('Эргүүлсэн блок торны хэвлэх огтлол хараахан дэмжигдээгүй.')
    cutoff = number(settings.get('cutoff', 0), 'Заагийн агуулга')
    if cutoff < 0:
        raise ValueError('Заагийн агуулга сөрөг байж болохгүй.')
    fallback = settings.get('density')
    fallback = None if fallback in ('', None) else number(fallback, 'Нягт', True)
    if project.grade_unit not in ('%', 'g/t', 'ppm'):
        raise ValueError('Агуулгын нэгж %, g/t эсвэл ppm байна.')
    groups = {}
    missing_grade = missing_density = fallback_count = 0
    for i, b in enumerate(blocks):
        if i % 1000 == 0 and cancel():
            raise InterruptedError('Цуцалсан.')
        for key in ('x','y','z','dx','dy','dz'):
            number(b.get(key), key, key.startswith('d'))
        volume = number(math.prod(float(b[k]) for k in ('dx','dy','dz')), 'Эзлэхүүн', True)
        grade = b.get('grade')
        if grade is None:
            missing_grade += 1
            continue
        grade = number(grade, 'Агуулга')
        if grade < 0:
            raise ValueError('Сөрөг агуулгатай блок байна.')
        if project.grade_unit == '%' and grade > 100:
            raise ValueError('Хувийн агуулга 100%-аас их байж болохгүй.')
        if grade < cutoff:
            continue
        density = b.get('density')
        if density is None:
            density = fallback
            fallback_count += density is not None
        if density is not None:
            density = number(density, 'Блокийн нягт', True)
        else:
            missing_density += 1
        key = (str(b.get('domain') or 'Тодорхойгүй'), str(b.get('resource_class') or 'АНГИЛААГҮЙ'))
        if key not in groups and len(groups) >= 1000:
            raise ValueError('Хэвлэх тайлан 1000 хүртэл домэйн/ангиллын бүлэг дэмжинэ.')
        g = groups.setdefault(key, [0, 0., 0., 0., 0])
        g[0] += 1
        g[1] += volume
        if density is None:
            g[4] += 1
        else:
            g[2] = number(g[2]+volume*density, 'Нийт тонн')
            g[3] = number(g[3]+volume*density*grade, 'Жинлэсэн агуулга')
    ordered = sorted(groups.items())
    if groups:
        ordered.append((('НИЙТ', 'Нийлбэр'), [sum(v[i] for v in groups.values()) for i in range(5)]))
    rows = []
    for (domain, cls), (count, volume, tonnes, weighted, missing) in ordered:
        rows.append({'Домэйн': domain, 'Эх ангилал': cls, 'Блокийн тоо': count,
                     'Эзлэхүүн м³': volume, 'Нягт т/м³': tonnes/volume if not missing else None,
                     'Хүдэр т': tonnes if not missing else None,
                     'Агуулга '+project.grade_unit: weighted/tonnes if tonnes and not missing else None,
                     'Металл т': weighted/(100 if project.grade_unit == '%' else 1e6) if not missing else None,
                     'Нягтгүй блок': missing})
    warnings = [NOTICE, 'Ангилал нь зөвхөн эх өгөгдлийн шошго; нөөцийн ангиллыг программ тогтоохгүй.',
                f'Агуулгагүй блок: {missing_grade}; заагаас дээш нягтгүй блок: {missing_density}.',
                f'Орлуулах нягт хэрэглэсэн блок: {fallback_count}.',
                'Металл нь in-situ агуулагдах металл; авалт, хаягдал, бохирдол оруулаагүй.',
                'Зүсэлт нь блок загварын огтлол; геологийн тайлбар, цооног, гадарга, хагарлын зураг биш.']
    if not project.crs_code:
        warnings.append('CRS код тодорхойгүй: локал координат. Албан зурагт ашиглахаас өмнө хянана.')
    for key, label in [('company','Байгууллага'),('license','Тусгай зөвшөөрөл'),('author','Боловсруулсан'),('reviewer','Хянасан'),('commodity','Ашигт малтмал')]:
        if not str(settings.get(key, '')).strip():
            warnings.append(label + ': бөглөөгүй.')
    if not rows:
        warnings.append('Заагаас дээш агуулгатай блок байхгүй.')
    return rows, warnings


def safe_cell(value):
    # Prevent spreadsheet formula execution when source labels are opened in Excel.
    return "'"+value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([safe_cell(row.get(k)) for k in columns])


def plane_blocks(blocks, normal, position):
    dim = 'd'+normal
    # Half-open boundaries assign a face shared by adjacent blocks once.
    return [b for b in blocks if b[normal]-b[dim]/2 <= position < b[normal]+b[dim]/2]


def write_plots(path, project, settings, cancel=lambda: False):
    from PySide6.QtCore import QRectF, QMarginsF, Qt
    from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout, QPainter, QColor, QFont, QPen
    blocks = project.workspace['block_model']['blocks']
    writer = QPdfWriter(str(path))
    writer.setResolution(254)  # 10 device units/mm: explicit metric scale.
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A3))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(0,0,0,0))
    writer.setTitle(project.name + ' — Блок загварын зүсэлт')
    painter = QPainter(writer)
    layouts = []
    if not painter.isActive():
        raise OSError('PDF нээж чадсангүй.')
    try:
        for page, (axis, normal) in enumerate((('x','y'), ('y','x'))):
            if cancel():
                raise InterruptedError('Цуцалсан.')
            if page and not writer.newPage():
                raise OSError('PDF хуудас үүсгэж чадсангүй.')
            low = min(b[normal]-b['d'+normal]/2 for b in blocks)
            high = max(b[normal]+b['d'+normal]/2 for b in blocks)
            position = number(settings.get('section_'+normal, (low+high)/2), 'Зүсэлтийн байрлал')
            selected = plane_blocks(blocks, normal, position)
            if not selected:
                raise ValueError(normal.upper()+' зүсэлт блок загварыг огтлохгүй байна.')
            xmin = min(b[axis]-b['d'+axis]/2 for b in selected)
            xmax = max(b[axis]+b['d'+axis]/2 for b in selected)
            zmin = min(b['z']-b['dz']/2 for b in selected)
            zmax = max(b['z']+b['dz']/2 for b in selected)
            required = max((xmax-xmin)/.33, (zmax-zmin)/.18)
            fixed = settings.get('scale', '')
            scale = number(fixed, 'Масштаб', True) if fixed not in ('', None, 'auto') else next((s for s in (100,200,250,500,750,1000,1250,2000,2500,5000,10000,20000,25000,50000,100000) if s >= required), math.ceil(required/100000)*100000)
            if scale < required:
                raise ValueError('Сонгосон масштаб A3 хуудсанд багтахгүй. Auto эсвэл бага масштаб сонгоно уу.')
            layouts.append({'page':page+1,'plane':axis.upper()+'Z','normal_axis':normal.upper(),
                            'position_m':position,'scale_denominator':scale,'paper':'A3 landscape',
                            'print_percent':100,'block_count':len(selected),'bounds_m':[xmin,zmin,xmax,zmax]})
            factor = 10000/scale
            left = 400+(3300-(xmax-xmin)*factor)/2
            bottom = 530+(1800+(zmax-zmin)*factor)/2
            def text(x,y,w,h,value,size=10,bold=False):
                painter.setPen(QColor('#19364c'));painter.setFont(QFont('DejaVu Sans',size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
                painter.drawText(QRectF(x,y,w,h), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignVCenter, str(value))
            painter.setPen(QPen(QColor('#8aa4b4'), 2));painter.drawRect(QRectF(150,150,3900,2670))
            text(240,180,3600,100,'RAINYMINE  |  '+project.name,17,True)
            text(240,290,3600,90,f'{axis.upper()}Z зүсэлт • {normal.upper()} = {position:,.2f} м • 1:{scale:g} • A3 / 100% хэвлэнэ',12)
            text(240,385,3600,70,NOTICE,10)
            grades = [b['grade'] for b in blocks if b.get('grade') is not None]
            maximum = max(grades, default=0) or 1
            for i,b in enumerate(selected):
                if i % 500 == 0 and cancel():
                    raise InterruptedError('Цуцалсан.')
                grade = b.get('grade')
                color = QColor('#dbe3e9') if grade is None else QColor.fromHsvF((1-min(1,max(0,grade/maximum)))*.65,.75,.92)
                painter.setBrush(color);painter.setPen(QPen(QColor('#7a92a0'), .7))
                painter.drawRect(QRectF(left+(b[axis]-b['d'+axis]/2-xmin)*factor,bottom-(b['z']+b['dz']/2-zmin)*factor,b['d'+axis]*factor,b['dz']*factor))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for step in range(5):
                x = xmin+(xmax-xmin)*step/4
                z = zmin+(zmax-zmin)*step/4
                text(left+(x-xmin)*factor-140,bottom+20,400,60,f'{x:,.0f}',8)
                text(left-300,bottom-(z-zmin)*factor-30,280,60,f'{z:,.0f}',8)
            text(180,2350,3800,85,f'{axis.upper()}: {xmin:,.2f} → {xmax:,.2f} м   |   Z: {zmin:,.2f} → {zmax:,.2f} м   |   CRS: {project.crs_code or "ЛОКАЛ / ТОДОРХОЙГҮЙ"}',10)
            bar = min((xmax-xmin)/3, scale*.05)
            painter.setPen(QPen(QColor('#19364c'), 8));painter.drawLine(int(left),2450,int(left+bar*factor),2450)
            text(left,2470,1100,60,f'0 — {bar:g} м',9)
            for i in range(5):
                painter.fillRect(QRectF(2350+i*290,2440,290,50),QColor.fromHsvF((1-i/4)*.65,.75,.92))
                text(2350+i*290,2500,290,60,f'{maximum*i/4:.3g}',9)
            text(2350,2570,1500,55,'Агуулга '+project.grade_unit+' | саарал: агуулгагүй',9)
            text(240,2640,1750,140,f'Байгууллага: {settings.get("company") or "—"}\nТЗ: {settings.get("license") or "—"}',10)
            text(2070,2640,1700,140,f'Боловсруулсан: {settings.get("author") or "—"}   Хянасан: {settings.get("reviewer") or "—"}\nЗураг {page+1}/2 • Блок загварын огтлол',9)
    finally:
        painter.end()
    return layouts


def export_pack(project, settings, destination, cancel=lambda: False):
    """Write to a new directory atomically; a failed/cancelled pack is never published."""
    rows, warnings = build_tables(project, settings, cancel)
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Гаралтын хавтас аль хэдийн байна. Шинэ нэр сонгоно уу.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ebmz-', dir=destination.parent))
    try:
        columns = ['Домэйн','Эх ангилал','Блокийн тоо','Эзлэхүүн м³','Нягт т/м³','Хүдэр т','Агуулга '+project.grade_unit,'Металл т','Нягтгүй блок']
        write_csv(stage/'01-resource-summary.csv', rows, columns)
        for filename, records in [('02-collars',project.collars),('03-surveys',project.surveys),('04-assays',project.assays),('05-lithology',project.lithology)]:
            values = [asdict(r) for r in records]
            write_csv(stage/(filename+'.csv'),values,list(values[0]) if values else ['Өгөгдөл байхгүй'])
        write_csv(stage/'06-review-checklist.csv', [{'Хянах зүйл':w,'Хяналтын тэмдэглэл':''} for w in warnings], ['Хянах зүйл','Хяналтын тэмдэглэл'])
        esc = lambda x: html.escape('—' if x is None else f'{x:,.4f}' if isinstance(x,float) else str(x))
        def display(value, column):
            if isinstance(value,float):
                return f'{value:,.4f}' if column.startswith('Агуулга') else f'{value:,.2f}'
            return esc(value)
        table = '<table width="100%"><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in columns)+'</tr></thead>'+''.join('<tr>'+''.join('<td nowrap="nowrap">'+display(r[c],c)+'</td>' for c in columns)+'</tr>' for r in rows)+'</table>'
        content = '<html><head><meta charset="utf-8"><style>body{font-family:sans-serif;color:#19364c}table{border-collapse:collapse;font-size:9pt}td,th{border:1px solid #aabac6;padding:5px}th{background:#def0ef}</style></head><body><h1>RAINYMINE | '+esc(project.name)+'</h1><h3>'+NOTICE+'</h3>'
        labels = {'commodity':'Ашигт малтмал','company':'Байгууллага','license':'ТЗ','author':'Боловсруулсан','reviewer':'Хянасан'}
        content += '<p>'+esc(' | '.join(f'{label}: {settings.get(k) or "—"}' for k,label in labels.items()))+'<br>CRS: '+esc(project.crs_code or project.crs)+'<br>Заагийн агуулга: '+esc(settings.get('cutoff',0))+' '+esc(project.grade_unit)+'</p>'+table
        content += '<h2>Хяналтын жагсаалт</h2><ul>'+''.join('<li>'+esc(w)+'</li>' for w in warnings)+'</ul><h2>Арга ба эх сурвалж</h2><p>V = dx×dy×dz; T = V×ρ; G = Σ(T×g)/ΣT. Металл т: T×g/100 (%) эсвэл T×g/10⁶ (g/t, ppm). Нягт дутуу домэйны тонн, агуулга, металлыг хоосон үлдээнэ. Блокийн ангиллыг эх өгөгдлөөс авна. Тухайн ашигт малтмалын хүчинтэй заавар, батлагдсан маягтаар мэргэжилтэн нягтална.</p><p>'+'<br>'.join(esc(s) for s in SOURCES)+'</p></body></html>'
        (stage/'report.html').write_text(content,encoding='utf-8')
        from PySide6.QtCore import QMarginsF
        from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout
        writer = QPdfWriter(str(stage/'report.pdf'));writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4));writer.setPageOrientation(QPageLayout.Orientation.Landscape);writer.setPageMargins(QMarginsF(12,12,12,12));writer.setResolution(144)
        document = QTextDocument();document.setHtml(content);document.print_(writer)
        del writer
        layouts = write_plots(stage/'sections-A3.pdf',project,settings,cancel)
        if cancel():
            raise InterruptedError('Цуцалсан.')
        files = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
        manifest = {'profile':PROFILE,'status':'DRAFT_REVIEW_REQUIRED','created_utc':datetime.now(timezone.utc).isoformat(),'project':project.name,'settings':settings,'model_input_sha256':project.workspace['block_model'].get('input_sha256'),'model_run_sha256':project.workspace['block_model'].get('run_sha256'),'source_blocks_sha256':hashlib.sha256(json.dumps(project.workspace['block_model']['blocks'],sort_keys=True,allow_nan=False).encode()).hexdigest(),'grade_unit':project.grade_unit,'crs':project.crs_code or project.crs,'warnings':warnings,'files_sha256':files,'sources':SOURCES}
        manifest['layouts'] = layouts
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        stage.rename(destination)
        return str(destination)
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise
