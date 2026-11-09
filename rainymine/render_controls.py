"""Persisted, validated rendering preferences and world-space camera bookmarks."""
from copy import deepcopy
import math
import numpy as np


def options(workspace):
    value=workspace.get('render_options',{})
    if not isinstance(value,dict) or set(value)-{'profile','clip_bounds','scalar_range','show_null_blocks'}:raise ValueError('Unsupported render preferences')
    result={'profile':'balanced','clip_bounds':None,'scalar_range':None,'show_null_blocks':False,**value}
    if result['profile'] not in ('fast','balanced','quality'):raise ValueError('Render profile must be fast, balanced or quality')
    if type(result['show_null_blocks']) is not bool:raise ValueError('Boolean NULL display setting required')
    for name,size in (('clip_bounds',6),('scalar_range',2)):
        v=result[name]
        if v is None:continue
        if not isinstance(v,(list,tuple)) or len(v)!=size or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in v):raise ValueError('Finite render bounds/range required')
        if size==6 and any(v[i]>=v[i+3] for i in range(3)):raise ValueError('Clipping minimum must be below maximum')
        if size==2 and v[0]>=v[1]:raise ValueError('Scalar minimum must be below maximum')
    return result


def validate_camera(value):
    if not isinstance(value,dict) or set(value)!={'position','focal_point','view_up','parallel','parallel_scale','view_angle'}:raise ValueError('Invalid camera bookmark')
    for key in ('position','focal_point','view_up'):
        a=value[key]
        if not isinstance(a,(list,tuple)) or len(a)!=3 or not np.isfinite(np.asarray(a,float)).all():raise ValueError('Finite XYZ camera vectors required')
    direction=np.asarray(value['focal_point'])-value['position'];up=np.asarray(value['view_up'])
    if np.linalg.norm(direction)<1e-9 or np.linalg.norm(up)<1e-9 or np.linalg.norm(np.cross(direction/np.linalg.norm(direction),up/np.linalg.norm(up)))<1e-8:raise ValueError('Camera direction and up cannot be degenerate')
    if type(value['parallel']) is not bool:raise ValueError('Boolean camera projection required')
    for key in ('parallel_scale','view_angle'):
        v=value[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('Positive camera scale/angle required')
    if value['view_angle']>=180:raise ValueError('Camera angle must be below 180')


def validate_workspace(workspace):
    options(workspace);bookmarks=workspace.get('camera_bookmarks',{})
    if not isinstance(bookmarks,dict) or len(bookmarks)>30:raise ValueError('Maximum 30 named cameras')
    for name,camera in bookmarks.items():
        if not isinstance(name,str) or not name.strip() or len(name)>80:raise ValueError('Camera name 1–80 characters required')
        validate_camera(camera)


def capture_camera(scene):
    c=scene.renderer.GetActiveCamera()
    result={'position':(np.asarray(c.GetPosition())+scene.origin).tolist(),'focal_point':(np.asarray(c.GetFocalPoint())+scene.origin).tolist(),
            'view_up':list(c.GetViewUp()),'parallel':bool(c.GetParallelProjection()),'parallel_scale':c.GetParallelScale(),'view_angle':c.GetViewAngle()}
    validate_camera(result);return result


def restore_camera(scene,value,render=True):
    validate_camera(value);c=scene.renderer.GetActiveCamera()
    c.SetPosition(*scene.local(value['position']));c.SetFocalPoint(*scene.local(value['focal_point']));c.SetViewUp(*value['view_up'])
    c.SetParallelProjection(value['parallel']);c.SetParallelScale(value['parallel_scale']);c.SetViewAngle(value['view_angle']);scene.renderer.ResetCameraClippingRange()
    if render:scene.window.Render()


def clip_actor(scene,actor):
    import vtk
    actor.GetMapper().RemoveAllClippingPlanes();bounds=options(scene.project.workspace)['clip_bounds']
    if bounds is None:return
    # Mapper planes compose with existing slab/cutaway pipelines and retain IDs.
    for i in range(3):
        for side in (0,1):
            plane=vtk.vtkPlane();normal=[0.,0.,0.];normal[i]=1 if side==0 else -1
            point=[0.,0.,0.];point[i]=bounds[i+side*3]-scene.origin[i];plane.SetNormal(*normal);plane.SetOrigin(*point)
            actor.GetMapper().AddClippingPlane(plane)


def apply_render_options(scene):
    if scene.project is None:return
    value=options(scene.project.workspace);quality=value['profile']=='quality'
    window=getattr(scene.window,'window',scene.window)
    window.SetMultiSamples(0);window.SetAlphaBitPlanes(1)
    scene.renderer.SetUseDepthPeeling(value['profile']!='fast');scene.renderer.SetMaximumNumberOfPeels(100);scene.renderer.SetOcclusionRatio(.1)
    scene.renderer.SetUseFXAA(value['profile']!='fast')
    for key,actor in scene.actors.items():
        clip_actor(scene,actor)
        actor.GetProperty().SetEdgeVisibility(key=='surface' or (quality and key not in ('holes','collars','selected')))
        actor.GetProperty().SetEdgeColor(.15,.22,.27);actor.GetProperty().SetLineWidth(1 if key not in ('holes','selected') else 4 if key=='holes' else 7)
    limits=value['scalar_range'] or [0,scene.grade_max]
    scene.lut.SetTableRange(*limits)
    for key in ('blocks','holes'):
        if key in scene.actors:scene.actors[key].GetMapper().SetScalarRange(*limits)


class RenderTools:
    def build_render_controls(self):
        from PySide6.QtWidgets import QGroupBox,QGridLayout
        from .ribbon import RibbonButton
        from .workbench import icon
        group=QGroupBox('Дүрслэлийн хяналт');group.setObjectName('ribbonGroup');grid=QGridLayout(group);grid.setContentsMargins(5,2,5,18)
        commands=[('Render тохиргоо',self.render_settings),('Камер хадгалах',self.save_camera),('Камер сэргээх',self.load_camera),('3D clipping box',self.clip_box),('Render хэмжилт',self.render_measure)]
        for i,(caption,callback) in enumerate(commands):
            button=RibbonButton();button.setText(caption);button.setProperty('commandSource',caption);button.setIcon(icon('cube'));button.clicked.connect(lambda checked=False,cb=callback:self.guard(cb));grid.addWidget(button,i%2,i//2)
        layout=self.ribbon.widget(5).widget().layout();layout.insertWidget(0,group)

    def setup_render_hover(self):
        from PySide6.QtCore import QTimer,QPoint
        from PySide6.QtWidgets import QToolTip
        import vtk
        self._render_hover=QTimer(self);self._render_hover.setSingleShot(True);self._render_hover.setInterval(300)
        def show():
            style=self.vtk.GetInteractorStyle()
            if style and style.GetState()!=0:return
            if self.computing or self._engineering_tasks or self.measure_mode:return
            x,y=self.vtk.GetEventPosition();picker=vtk.vtkCellPicker();picker.SetTolerance(.006)
            if not picker.Pick(x,y,0,self.scene.renderer):QToolTip.hideText();return
            info=self.scene.identify(picker.GetActor(),picker.GetCellId())
            if not info:return
            if 'block_index' in info:
                grade=info.get('grade');text=f"Block #{info['block_index']+1} | Grade: {grade if grade is not None else 'NULL'} {self.project.grade_unit}\nX {info['x']:.3f} Y {info['y']:.3f} Z {info['z']:.3f}"
            elif 'hole_id' in info:text='Drillhole: '+info['hole_id']
            else:text=info['layer']
            ratio=self.vtk.devicePixelRatioF();point=QPoint(round(x/ratio),round(self.vtk.height()-y/ratio));QToolTip.showText(self.vtk.mapToGlobal(point),text,self.vtk)
        self._render_hover.timeout.connect(show)
        self.vtk.AddObserver('MouseMoveEvent',lambda obj,event:self._render_hover.start())

    def render_settings(self):
        value=options(self.project.workspace)
        data=self.params('Render — source grades unchanged',{'Profile':[value['profile']]+[s for s in ('fast','balanced','quality') if s!=value['profile']],
            'Show NULL blocks':['Yes','No'] if value['show_null_blocks'] else ['No','Yes'],'Fixed grade range (blank=auto)':','.join(map(str,value['scalar_range'])) if value['scalar_range'] else ''})
        if not data:return
        value['profile']=data['Profile'];value['show_null_blocks']=data['Show NULL blocks']=='Yes';raw=data['Fixed grade range (blank=auto)'].strip();value['scalar_range']=[float(s) for s in raw.split(',')] if raw else None
        p=deepcopy(self.project);p.workspace['render_options']=value;p.validate();view=capture_camera(self.scene);self.commit(p);restore_camera(self.scene,view)

    def save_camera(self):
        from PySide6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,'Камер хадгалах','Нэр / Name')
        if not ok:return
        view=capture_camera(self.scene);p=deepcopy(self.project);p.workspace.setdefault('camera_bookmarks',{})[name.strip()]=view;p.validate();self.commit(p);restore_camera(self.scene,view)

    def load_camera(self):
        views=self.project.workspace.get('camera_bookmarks',{});names=list(views);index=self.choose('Камер сэргээх',names)
        if index is not None:restore_camera(self.scene,views[names[index]])

    def clip_box(self):
        value=options(self.project.workspace);bounds=value['clip_bounds']
        if bounds is None:
            local=self.scene.renderer.ComputeVisiblePropBounds();bounds=[local[0]+self.scene.origin[0],local[2]+self.scene.origin[1],local[4]+self.scene.origin[2],local[1]+self.scene.origin[0],local[3]+self.scene.origin[1],local[5]+self.scene.origin[2]]
        data=self.params('Clipping box — world metres; open faces, no certified caps',{'Enabled':['Yes','No'] if value['clip_bounds'] else ['No','Yes'],**dict(zip(('Min X','Min Y','Min Z','Max X','Max Y','Max Z'),bounds))})
        if not data:return
        value['clip_bounds']=[float(data[k]) for k in ('Min X','Min Y','Min Z','Max X','Max Y','Max Z')] if data['Enabled']=='Yes' else None
        view=capture_camera(self.scene);p=deepcopy(self.project);p.workspace['render_options']=value;p.validate();self.commit(p);restore_camera(self.scene,view)

    def render_measure(self):
        import time,platform
        import numpy as np
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QProgressDialog
        if getattr(self,'_render_measuring',False):raise ValueError('A render measurement is already active')
        self._render_measuring=True
        camera=capture_camera(self.scene);times=[];cancel=[False];progress=QProgressDialog('12 rendered frames — hardware dependent','Цуцлах',0,12,self);progress.canceled.connect(lambda:cancel.__setitem__(0,True));progress.show()
        source=self.project
        def tick():
            if cancel[0] or source is not self.project or not self.isVisible():
                if source is self.project and self.isVisible():restore_camera(self.scene,camera)
                self._render_measuring=False;progress.close();progress.deleteLater();return
            self.scene.renderer.GetActiveCamera().Azimuth(2);start=time.perf_counter();self.scene.window.Render();times.append(time.perf_counter()-start);progress.setValue(len(times))
            if len(times)<12:QTimer.singleShot(1,tick);return
            restore_camera(self.scene,camera);self._render_measuring=False;progress.close();progress.deleteLater()
            self.show_rows('Render timing — this device only',[{'os':platform.platform(),'vtk':__import__('vtk').vtkVersion.GetVTKVersion(),'frames':12,'viewport_px':str(self.scene.window.GetSize()),'median_frame_ms':float(np.median(times))*1000,'p95_frame_ms':float(np.percentile(times,95))*1000,'median_fps':1/max(1e-9,float(np.median(times))),'depth_peeling_used':bool(self.scene.renderer.GetLastRenderingUsedDepthPeeling()),'profile':options(self.project.workspace)['profile'],'scope':'current desktop scene, not a 10M-block workflow or Windows certification'}])
        QTimer.singleShot(1,tick)
