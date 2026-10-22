"""Section-click contact guides with explicit geologist-specified normal signs."""
from copy import deepcopy
import numpy as np
from PySide6.QtCore import Qt,QPointF,QLineF
from PySide6.QtGui import QPen,QColor,QPolygonF
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QGraphicsView,QGraphicsScene,QPushButton,QLabel


def edit_contacts(parent):
    model=parent.project.workspace.get('block_model')
    if not model:raise ValueError('A block-model extent is required for the section editor')
    bounds=model['bounds'];values=parent.params('Контакт чиглүүлэгч — normal-ийн эерэг/сөрөг талыг геологич тогтооно',
        {'Section Y':(bounds[1]+bounds[4])/2,'Normal X':0,'Normal Y':0,'Normal Z':1,'Signed offset m':5,'Resolution':25})
    if not values:return
    normal=np.array([float(values['Normal '+a]) for a in 'XYZ']);length=np.linalg.norm(normal);offset=float(values['Signed offset m'])
    if not np.isfinite(normal).all() or length<1e-12 or not np.isfinite(offset) or offset<=0:raise ValueError('Nonzero finite normal and positive offset required')
    normal/=length;y=float(values['Section Y']);points=[]
    dialog=QDialog(parent);dialog.setWindowTitle('XZ — contact / structural guide');dialog.resize(1000,750);layout=QVBoxLayout(dialog);scene=QGraphicsScene(0,0,900,600)
    from .map_composer import prepare_layout
    display=prepare_layout(parent.project,{'view':'XZ','position':y,'slab_width':10})
    def xy(p):return QPointF((p[0]-bounds[0])/(bounds[3]-bounds[0])*900,(bounds[5]-p[1])/(bounds[5]-bounds[2])*600)
    for polygon in display['polygons']:scene.addPolygon(QPolygonF([xy(p) for p in polygon['points']]),QPen(QColor('#becfd8')),QColor('#e5eef3'))
    for line in display['lines']:scene.addLine(QLineF(xy(line['points'][0]),xy(line['points'][1])),QPen(QColor('#728fa0')))
    class View(QGraphicsView):
        def mousePressEvent(self,event):
            if event.button()==Qt.MouseButton.LeftButton:
                p=self.mapToScene(event.position().toPoint())
                if 0<=p.x()<=900 and 0<=p.y()<=600:
                    xyz=[bounds[0]+p.x()/900*(bounds[3]-bounds[0]),y,bounds[5]-p.y()/600*(bounds[5]-bounds[2])]
                    points.append(xyz);scene.addEllipse(p.x()-3,p.y()-3,6,6,QPen(QColor('#008e95')));status.setText(f'{len(points)} contact • X {xyz[0]:.2f}, Y {y:.2f}, Z {xyz[2]:.2f}')
            super().mousePressEvent(event)
    view=View(scene);layout.addWidget(view);status=QLabel('Зүүн товчоор contact/guide цэг нэмнэ. XZ координат нь загварын extent; зураг нь хэвлэх масштаб биш.');status.setWordWrap(True);layout.addWidget(status)
    row=QHBoxLayout();save=QPushButton('Контакт / шугам хадгалах');update=QPushButton('Хадгалаад RBF Update');row.addWidget(save);row.addWidget(update);layout.addLayout(row)
    saved=[0]
    def commit_points():
        new=points[saved[0]:]
        if not new:raise ValueError('Add new contact points first')
        p=deepcopy(parent.project);controls=p.workspace.setdefault('contact_controls',[])
        if len(controls)+len(new)*3>10000:raise ValueError('Contact surface limit 10000 signed controls')
        known={tuple(round(c[k],6) for k in 'xyz'):c['value'] for c in controls}
        for point in new:
            for side in (0,1,-1):
                xyz=(np.array(point)+side*offset*normal).tolist();key=tuple(round(v,6) for v in xyz)
                if key in known:
                    if abs(known[key]-side*offset)>1e-6:raise ValueError('Conflicting signed control at the same location')
                    continue
                known[key]=side*offset;controls.append({**dict(zip('xyz',xyz)),'value':side*offset})
        if len(new)>1:p.workspace.setdefault('strings',[]).append({'name':'Contact guide','closed':False,'points':deepcopy(new)})
        p.workspace['contact_guides_review_pending']=True;parent.commit(p);saved[0]=len(points)
    def run():
        if len(points)>saved[0]:commit_points()
        if not parent.project.workspace.get('contact_controls'):raise ValueError('Add signed contact controls first')
        from .implicit_domains import contact_surface
        controls=deepcopy(parent.project.workspace['contact_controls']);resolution=int(values['Resolution']);faults=deepcopy(parent.project.workspace.get('faults',[]));dialog.accept()
        def apply(result):
            mesh,report=result;mesh['contact_guide_surface']=True;p=deepcopy(parent.project);p.workspace['meshes']=[m for m in p.workspace.get('meshes',[]) if not m.get('contact_guide_surface')]+[mesh];parent.commit(p);parent.record_step('contact_rbf',{'bounds':bounds,'resolution':resolution,'kernel':'linear','faults':faults});parent.show_rows('RBF Update — геологийн хяналт шаардлагатай',[report])
        parent.launch_task('Contact RBF Update…',lambda cancel:contact_surface(controls,bounds,resolution,kernel='linear',faults=faults,cancel=cancel),apply)
    save.clicked.connect(lambda:parent.guard(commit_points));update.clicked.connect(lambda:parent.guard(run));dialog.exec()
