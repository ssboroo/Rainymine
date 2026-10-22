"""Metric vector plan/section output, independent of a 3D screenshot."""
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import tempfile
import numpy as np
from scipy.spatial import ConvexHull,QhullError
from .core import Trajectory
from .spatial import model_basis


def block_section(block,basis,axes,position):
    u,v,n=axes;centre=np.array([block[k] for k in 'xyz']);size=np.array([block[k] for k in ('dx','dy','dz')])
    signs=np.array(list(itertools.product((-1,1),repeat=3)));vertices=centre+(signs*size/2)@basis.T
    if not vertices[:,n].min()<=position<vertices[:,n].max():return None
    points=[]
    for i in range(8):
        for j in range(i+1,8):
            if np.count_nonzero(signs[i]!=signs[j])!=1:continue
            a,b=vertices[i],vertices[j];da,db=a[n]-position,b[n]-position
            if abs(da)<1e-9:points.append(a[[u,v]])
            if da*db<0:points.append((a+(b-a)*da/(da-db))[[u,v]])
    if len(points)<3:return None
    points=np.unique(np.round(np.array(points),9),axis=0)
    if len(points)<3:return None
    try:return points[ConvexHull(points).vertices].tolist()
    except QhullError:return None


def prepare_layout(project,settings,cancel=None):
    view=settings.get('view','XZ');axes={'XZ':(0,2,1),'YZ':(1,2,0),'XY':(0,1,2)}.get(view)
    if axes is None:raise ValueError('View must be XZ, YZ or XY')
    position=float(settings['position']);width=float(settings.get('slab_width',10))
    if not math.isfinite(position) or not math.isfinite(width) or width<=0:raise ValueError('Finite section position and positive drillhole slab width required')
    u,v,n=axes;model=project.workspace.get('block_model',{});basis=model_basis(model);polygons=[];lines=[];labels=[];bars=[]
    for i,b in enumerate(model.get('blocks',[])):
        if i%500==0 and cancel and cancel():raise RuntimeError('Map preparation cancelled')
        polygon=block_section(b,basis,axes,position)
        if polygon:
            tonnes=math.prod(b[k] for k in ('dx','dy','dz'))*b['density'] if b.get('density') is not None else None
            polygons.append({'points':polygon,'grade':b.get('grade'),'block':i+1,'tonnes':tonnes})
    surveys={}
    for s in project.surveys:surveys.setdefault(s.hole_id,[]).append(s)
    for h in project.collars:
        if cancel and cancel():raise RuntimeError('Drillhole plot cancelled')
        trajectory=Trajectory(h,surveys.get(h.hole_id,[]));points=[xyz for _,xyz in trajectory.sample(step=max(1,h.depth/150))]
        visible=[]
        for a,b in zip(points,points[1:]):
            a,b=np.asarray(a),np.asarray(b);delta=b[n]-a[n]
            if abs(delta)<1e-12:
                if abs(a[n]-position)>width/2:continue
                lo,hi=0.,1.
            else:
                t=sorted(((position-width/2-a[n])/delta,(position+width/2-a[n])/delta));lo,hi=max(0,t[0]),min(1,t[1])
                if lo>hi:continue
            segment=[(a+(b-a)*f)[[u,v]].tolist() for f in (lo,hi)];lines.append({'points':segment,'kind':'hole'});visible.extend(segment)
        if visible:labels.append({'point':visible[0],'text':h.hole_id,'kind':'hole'})
        for depth in np.linspace(0,h.depth,6):
            xyz=np.array(trajectory.at(float(depth)))
            if abs(xyz[n]-position)<=width/2:labels.append({'point':xyz[[u,v]].tolist(),'text':f'{depth:g} m','kind':'depth'})
        for row in project.lithology:
            if row.hole_id!=h.hole_id:continue
            middle=np.array(trajectory.at((row.from_m+row.to_m)/2))
            if abs(middle[n]-position)<=width/2:
                lines.append({'points':[np.array(trajectory.at(d))[[u,v]].tolist() for d in (row.from_m,row.to_m)],'kind':'lithology','rock':row.rock})
        for row in project.assays:
            if row.hole_id!=h.hole_id:continue
            xyz=np.array(trajectory.at((row.from_m+row.to_m)/2))
            if abs(xyz[n]-position)<=width/2:bars.append({'point':xyz[[u,v]].tolist(),'grade':row.grade})
    for mesh in project.workspace.get('meshes',[]):
        vertices=np.asarray(mesh['vertices'],float)
        for face in mesh['faces']:
            if len(face)!=3:continue
            tri=vertices[face];hits=[]
            if np.all(np.abs(tri[:,n]-position)<1e-9):continue
            for a,b in zip(tri,np.roll(tri,-1,axis=0)):
                da,db=a[n]-position,b[n]-position
                if abs(da)<1e-9:hits.append(a[[u,v]].tolist())
                if da*db<0:hits.append((a+(b-a)*da/(da-db))[[u,v]].tolist())
            hits=np.unique(np.round(hits,9),axis=0).tolist() if hits else []
            if len(hits)==2:lines.append({'points':hits,'kind':'contour'})
    allpoints=[p for poly in polygons for p in poly['points']]+[p for line in lines for p in line['points']]
    if not allpoints:raise ValueError('Selected plane/slab has no plot geometry')
    xy=np.asarray(allpoints);low=xy.min(axis=0);high=xy.max(axis=0)
    if np.any(high-low<1e-6):raise ValueError('Plot extent is degenerate')
    return {'view':view,'axes':axes,'position':position,'slab_width':width,'bounds':[*low,*high],
            'polygons':polygons,'lines':lines,'labels':labels,'bars':bars,'grade_unit':project.grade_unit}


def paint_layout(painter,project,layout,settings,paper_mm):
    from PySide6.QtCore import Qt,QRectF,QPointF
    from PySide6.QtGui import QColor,QFont,QPen,QPolygonF,QBrush,QFontMetricsF
    w,h=paper_mm;low=np.array(layout['bounds'][:2]);high=np.array(layout['bounds'][2:]);span=high-low
    usable=np.array([w-60,h-95]);required=max(span/(usable/1000))
    chosen=settings.get('scale','auto');scale=next((x for x in (100,200,500,1000,2000,2500,5000,10000,20000,50000,100000) if x>=required),math.ceil(required/100000)*100000) if chosen in ('auto','',None) else float(chosen)
    if not math.isfinite(scale) or scale<required:raise ValueError('Selected scale does not fit the paper; choose auto or a smaller map scale')
    factor=1000/scale;left=30+(usable[0]-span[0]*factor)/2;bottom=40+(usable[1]+span[1]*factor)/2
    def xy(point):return QPointF(left+(point[0]-low[0])*factor,bottom-(point[1]-low[1])*factor)
    def text(x,y,width,height,value,size=3):
        painter.setPen(QColor('#173449'));font=QFont('DejaVu Sans');font.setPixelSize(max(1,round(size*10)));painter.setFont(font)
        painter.save();painter.translate(x,y);painter.scale(.1,.1);painter.drawText(QRectF(0,0,width*10,height*10),Qt.TextFlag.TextWordWrap,str(value));painter.restore()
    occupied=[]
    plot_rect=QRectF(left,bottom-span[1]*factor,span[0]*factor,span[1]*factor)
    def annotation(x,y,value,size=2.3):
        font=QFont('DejaVu Sans');font.setPixelSize(round(size*10));metrics=QFontMetricsF(font)
        width=metrics.horizontalAdvance(str(value))*.1+.6;height=metrics.height()*.1+.4
        rect=QRectF(x,y,width,height)
        if not plot_rect.contains(rect) or any(rect.adjusted(-.5,-.5,.5,.5).intersects(r) for r in occupied):return False
        occupied.append(rect);painter.fillRect(rect,QColor(255,255,255,205));text(x+.2,y,width,height,value,size);return True
    painter.setPen(QPen(QColor('#9eb5bf'),.15));painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(QRectF(10,10,w-20,h-20))
    text(18,15,w-35,8,'RAINYMINE | '+project.name,5);text(18,25,w-40,8,f'{layout["view"]} • {"XYZ"[layout["axes"][2]]}={layout["position"]:,.2f} m • 1:{scale:g} • Drillhole slab {layout["slab_width"]:g} m',3)
    for i in range(6):
        p=low+span*i/5
        painter.setPen(QPen(QColor('#d6e0e4'),.1));painter.drawLine(xy([p[0],low[1]]),xy([p[0],high[1]]));painter.drawLine(xy([low[0],p[1]]),xy([high[0],p[1]]))
        text(xy(p).x()-8,bottom+2,25,6,f'{p[0]:,.1f}',2.5);text(left-25,xy(p).y()-2,24,5,f'{p[1]:,.1f}',2.5)
    maximum=max([p['grade'] for p in layout['polygons'] if p['grade'] is not None]+[b['grade'] for b in layout['bars']]+[1e-12])
    for polygon in layout['polygons']:
        grade=polygon['grade'];color=QColor('#d2dce2') if grade is None else QColor.fromHsvF((1-min(1,max(0,grade/maximum)))*.65,.65,.95)
        painter.setBrush(color);painter.setPen(QPen(QColor('#8ca0ab'),.08));points=[xy(p) for p in polygon['points']];painter.drawPolygon(QPolygonF(points))
    rocks=sorted({l.get('rock') for l in layout['lines'] if l.get('rock')})
    for line in layout['lines']:
        a,b=[xy(p) for p in line['points']]
        if line['kind']=='lithology':
            painter.setPen(QPen(QColor('#386b74'),.3));brush=QBrush(QColor.fromHsvF((rocks.index(line['rock'])*.618)%1,.5,.8),Qt.BrushStyle.BDiagPattern);painter.setBrush(brush)
            painter.drawPolygon(QPolygonF([QPointF(a.x()-2,a.y()),a,b,QPointF(b.x()-2,b.y())]))
        else:painter.setPen(QPen(QColor('#aa552d') if line['kind']=='contour' else QColor('#142f46'),.35 if line['kind']=='contour' else .25));painter.drawLine(a,b)
    for label in sorted(layout['labels'],key=lambda r:r['kind']!='hole'):
        p=xy(label['point']);annotation(p.x()-12,p.y(),label['text'],2.4)
    for bar in layout['bars']:
        p=xy(bar['point']);painter.setPen(QPen(QColor('#087e83'),.45));painter.drawLine(QPointF(p.x()+2,p.y()),QPointF(p.x()+2+8*bar['grade']/maximum,p.y()));annotation(p.x()+11,p.y()-2,f'{bar["grade"]:.3g}',2.1)
    if settings.get('block_labels'):
        for polygon in layout['polygons']:
            points=[xy(p) for p in polygon['points']]
            if max(p.x() for p in points)-min(p.x() for p in points)<=12:continue
            point=xy(np.mean(polygon['points'],axis=0));grade=polygon['grade']
            value=f'{grade:.3g} {project.grade_unit}' if grade is not None else 'NULL'
            annotation(point.x()-8,point.y()-2,value)
            if polygon['tonnes'] is not None:annotation(point.x()-8,point.y()+2,f'{polygon["tonnes"]:,.0f} t',2.1)
    text(left,bottom+9,110,6,'XYZ'[layout['axes'][0]]+' (m)',2.7)
    text(max(12,left-25),max(36,plot_rect.top()-7),90,6,'XYZ'[layout['axes'][1]]+' (m)',2.7)
    text(18,h-49,w-40,7,'CRS: '+(project.crs_code or 'ЛОКАЛ / ТОДОРХОЙГҮЙ')+' | '+project.grade_unit+' | ХЯНАХ ЗУРАГ • 100% хэвлэнэ',2.7)
    text(18,h-40,w*.45,15,'Байгууллага: '+str(settings.get('company','—'))+'\nТЗ: '+str(settings.get('license','—')),2.7)
    text(w*.5,h-40,w*.45,15,'Боловсруулсан: '+str(settings.get('author','—'))+'\nХянасан: '+str(settings.get('reviewer','—')),2.7)
    bar_m=min(span[0]/4,scale*.04);painter.setPen(QPen(QColor('#173449'),.7));painter.drawLine(QPointF(25,h-55),QPointF(25+bar_m*factor,h-55));text(25,h-62,90,6,f'0 — {bar_m:g} m',2.7)
    text(w-110,h-62,95,9,f'Grade 0 → {maximum:.3g} {project.grade_unit}; grey = NULL',2.7)
    if layout['view']=='XY':
        painter.drawLine(QPointF(w-30,65),QPointF(w-30,45));painter.drawLine(QPointF(w-30,45),QPointF(w-33,50));painter.drawLine(QPointF(w-30,45),QPointF(w-27,50));text(w-32,37,15,8,'N',4)
    return scale


def export_map(project,settings,destination,cancel=None):
    from PySide6.QtCore import QMarginsF,QSize,QRectF
    from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QPainter
    from PySide6.QtSvg import QSvgGenerator
    sizes={'A3':(420,297),'A1':(841,594),'A0':(1189,841)};paper=settings.get('paper','A3')
    if paper not in sizes:raise ValueError('Paper A3, A1 or A0 required')
    layout=prepare_layout(project,settings,cancel);destination=Path(destination)
    if destination.exists():raise ValueError('Choose a new plot folder')
    stage=Path(tempfile.mkdtemp(prefix='.rainymine-plot-',dir=destination.parent));w,h=sizes[paper]
    try:
        pdf=QPdfWriter(str(stage/'map.pdf'));pdf.setResolution(254);pdf.setPageSize(QPageSize(getattr(QPageSize.PageSizeId,paper)));pdf.setPageOrientation(QPageLayout.Orientation.Landscape);pdf.setPageMargins(QMarginsF(0,0,0,0));p=QPainter(pdf)
        if not p.isActive():raise OSError('Cannot open PDF painter')
        try:p.scale(10,10);scale=paint_layout(p,project,layout,settings,(w,h))
        finally:p.end()
        del pdf
        if cancel and cancel():raise RuntimeError('Plot export cancelled')
        svg=QSvgGenerator();svg.setFileName(str(stage/'map.svg'));svg.setSize(QSize(w*10,h*10));svg.setViewBox(QRectF(0,0,w,h));svg.setResolution(254);p=QPainter(svg)
        if not p.isActive():raise OSError('Cannot open SVG painter')
        try:paint_layout(p,project,layout,settings,(w,h))
        finally:p.end()
        del svg
        manifest={'paper':paper,'scale':scale,'settings':settings,'crs':project.crs_code,'grade_unit':project.grade_unit,'block_intersections':len(layout['polygons']),
                  'title_block_status':'RAINYMINE review template; not an approved national form','drillhole_projection':'nearby traces clipped to a declared slab; lithology interval chords are schematic',
                  'label_policy':'hole/depth and assay labels before block labels; colliding/out-of-frame labels suppressed; all source values remain in the project',
                  'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}}
        (stage/'layout.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        stage.rename(destination);return str(destination)
    except BaseException:shutil.rmtree(stage,ignore_errors=True);raise
