"""VTK 3D scene; all coordinates are shifted around the local origin."""
import math
import vtk
from .core import Trajectory

class Scene:
    def __init__(self,window):
        self.window=window;self.renderer=vtk.vtkRenderer();window.AddRenderer(self.renderer)
        self.renderer.SetBackground(.035,.055,.09);self.renderer.SetBackground2(.10,.15,.22);self.renderer.GradientBackgroundOn()
        self.project=None;self.origin=(0,0,0);self.sources={};self.actors={};self.labels=[]
        self.section=None;self.pipeline=[];self.paths={};self.grade_max=1
        light=vtk.vtkLight();light.SetLightTypeToHeadlight();self.renderer.AddLight(light)
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        self.lut=vtk.vtkLookupTable();self.lut.SetNumberOfTableValues(256);self.lut.SetNanColor(.45,.5,.6,1)
        self.lut.SetBelowRangeColor(.4,.45,.55,1);self.lut.UseBelowRangeColorOn()
        for i in range(256):
            t=i/255
            self.lut.SetTableValue(i,.16+.78*t,.8-.53*t,.65-.37*t,1)
        self.lut.Build()
        self.legend=vtk.vtkScalarBarActor();self.legend.SetLookupTable(self.lut);self.legend.SetNumberOfLabels(5)
        self.legend.SetWidth(.11);self.legend.SetHeight(.35);self.legend.SetPosition(.87,.12)
        self.legend.GetLabelTextProperty().SetColor(.8,.86,.94)
        self.legend.GetTitleTextProperty().SetColor(.8,.86,.94)
        self.renderer.AddActor2D(self.legend)
        self.marker=None

    def local(self,p):return tuple(p[i]-self.origin[i] for i in range(3))

    def polyline(self,points,lines,scalars,trajectory,start,end,value):
        samples=trajectory.sample(start,end,step=max(5,trajectory.collar.depth/80))
        for (_,p),(_,q) in zip(samples,samples[1:]):
            a=points.InsertNextPoint(*self.local(p));b=points.InsertNextPoint(*self.local(q))
            lines.InsertNextCell(2);lines.InsertCellPoint(a);lines.InsertCellPoint(b);scalars.InsertNextValue(value)

    def load(self,project):
        project.validate();self.project=project
        for actor in self.actors.values():self.renderer.RemoveActor(actor)
        for actor in self.labels:self.renderer.RemoveActor(actor)
        self.actors={};self.sources={};self.labels=[];self.paths={}
        coords=[(h.x,h.y,h.z) for h in project.collars]+[tuple(p) for p in project.surface]
        self.origin=tuple(sum(p[i] for p in coords)/len(coords) for i in range(3)) if coords else (0,0,0)
        self.grade_max=max(1,max((a.grade for a in project.assays),default=1))
        self.lut.SetTableRange(0,self.grade_max);self.legend.SetTitle(project.grade_unit)
        points=vtk.vtkPoints();points.SetDataTypeToDouble();lines=vtk.vtkCellArray();scalars=vtk.vtkFloatArray();scalars.SetName('grade')
        collars=vtk.vtkPoints();collars.SetDataTypeToDouble()
        assays={}
        for a in project.assays:assays.setdefault(a.hole_id,[]).append(a)
        for h in project.collars:
            tr=Trajectory(h,project.surveys);self.paths[h.hole_id]=tr
            collars.InsertNextPoint(*self.local((h.x,h.y,h.z)))
            previous=0
            for a in sorted(assays.get(h.hole_id,[]),key=lambda a:a.from_m):
                if a.from_m>previous:self.polyline(points,lines,scalars,tr,previous,a.from_m,-1)
                self.polyline(points,lines,scalars,tr,a.from_m,a.to_m,a.grade);previous=a.to_m
            if previous<h.depth:self.polyline(points,lines,scalars,tr,previous,h.depth,-1)
        poly=vtk.vtkPolyData();poly.SetPoints(points);poly.SetLines(lines);poly.GetCellData().SetScalars(scalars)
        self.sources['holes']=poly
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(poly);mapper.SetLookupTable(self.lut);mapper.SetScalarRange(0,self.grade_max);mapper.SetScalarModeToUseCellData()
        actor=vtk.vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetLineWidth(4)
        self.renderer.AddActor(actor);self.actors['holes']=actor
        cp=vtk.vtkPolyData();cp.SetPoints(collars)
        vertices=vtk.vtkVertexGlyphFilter();vertices.SetInputData(cp);vertices.Update()
        self.sources['collars']=vertices.GetOutput()
        cm=vtk.vtkPolyDataMapper();cm.SetInputData(vertices.GetOutput())
        ca=vtk.vtkActor();ca.SetMapper(cm);ca.GetProperty().SetColor(.8,.9,1);ca.GetProperty().SetPointSize(7)
        self.renderer.AddActor(ca);self.actors['collars']=ca
        if project.surface:
            sp=vtk.vtkPoints();sp.SetDataTypeToDouble()
            for p in project.surface:sp.InsertNextPoint(*self.local(p))
            surf=vtk.vtkPolyData();surf.SetPoints(sp)
            delaunay=vtk.vtkDelaunay2D();delaunay.SetInputData(surf);delaunay.SetTolerance(0.00001);delaunay.Update()
            self.sources['surface']=delaunay.GetOutput()
            sm=vtk.vtkPolyDataMapper();sm.SetInputData(delaunay.GetOutput());sm.ScalarVisibilityOff()
            sa=vtk.vtkActor();sa.SetMapper(sm);sa.GetProperty().SetColor(.33,.47,.39);sa.GetProperty().SetOpacity(.4)
            sa.GetProperty().EdgeVisibilityOn();sa.GetProperty().SetEdgeColor(.17,.27,.23)
            self.renderer.AddActor(sa);self.actors['surface']=sa
        if self.marker:self.marker.EnabledOff();self.marker=None
        if self.window.GetInteractor():
            axes=vtk.vtkAxesActor();self.marker=vtk.vtkOrientationMarkerWidget();self.marker.SetOrientationMarker(axes)
            self.marker.SetInteractor(self.window.GetInteractor());self.marker.SetViewport(0,0,.18,.18);self.marker.EnabledOn();self.marker.InteractiveOff()
        self.set_section(None,render=False);self.reset()

    def reset(self):
        camera=self.renderer.GetActiveCamera();camera.SetPosition(1,-1,1);camera.SetFocalPoint(0,0,0);camera.SetViewUp(0,0,1)
        self.renderer.ResetCamera();self.renderer.ResetCameraClippingRange();self.window.Render()

    def view(self,name):
        camera=self.renderer.GetActiveCamera();focus=camera.GetFocalPoint();distance=max(1,camera.GetDistance())
        direction={'top':(0,0,1),'north':(0,-1,0),'east':(1,0,0)}.get(name,(1,-1,1))
        camera.SetPosition(*(focus[i]+direction[i]*distance for i in range(3)))
        camera.SetViewUp(*( (0,1,0) if name=='top' else (0,0,1)))
        self.renderer.ResetCamera();self.window.Render()

    def set_section(self,section,render=True):
        """Clip to a true vertical slab. Angle is normal azimuth north clockwise."""
        self.section=section;self.pipeline=[]
        for name,poly in self.sources.items():
            mapper=self.actors[name].GetMapper()
            if section is None:mapper.SetInputData(poly);continue
            az,offset,width=section;normal=(math.sin(math.radians(az)),math.cos(math.radians(az)),0)
            pipeline=poly
            for sign in (1,-1):
                plane=vtk.vtkPlane();plane.SetNormal(*(sign*n for n in normal))
                plane.SetOrigin(*(n*(offset-sign*width/2) for n in normal))
                clip=vtk.vtkClipPolyData();clip.SetClipFunction(plane);clip.SetValue(0)
                if isinstance(pipeline,vtk.vtkPolyData):clip.SetInputData(pipeline)
                else:clip.SetInputConnection(pipeline.GetOutputPort())
                self.pipeline.extend([plane,clip]);pipeline=clip
            mapper.SetInputConnection(pipeline.GetOutputPort())
        self.select(None,render=False)
        if render:self.window.Render()

    def visible(self,name,value):
        if name in self.actors:self.actors[name].SetVisibility(value)
        if name=='holes':self.legend.SetVisibility(value)
        self.window.Render()

    def select(self,hole_id,render=True):
        if 'selected' in self.actors:self.renderer.RemoveActor(self.actors.pop('selected'))
        if hole_id in self.paths:
            pts=vtk.vtkPoints();pts.SetDataTypeToDouble();cells=vtk.vtkCellArray();tr=self.paths[hole_id];samples=tr.sample()
            cells.InsertNextCell(len(samples))
            for _,p in samples:cells.InsertCellPoint(pts.InsertNextPoint(*self.local(p)))
            poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetLines(cells)
            mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(poly)
            a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(1,1,1);a.GetProperty().SetLineWidth(7)
            # Selection is hidden in a slab to avoid displaying unclipped geometry.
            a.SetVisibility(self.section is None);self.renderer.AddActor(a);self.actors['selected']=a
        if render:self.window.Render()

    def screenshot(self,path):
        self.window.Render();capture=vtk.vtkWindowToImageFilter();capture.SetInput(self.window);capture.ReadFrontBufferOff();capture.Update()
        writer=vtk.vtkPNGWriter();writer.SetFileName(str(path));writer.SetInputConnection(capture.GetOutputPort());writer.Write()

    def export_vtp(self,path):
        writer=vtk.vtkXMLPolyDataWriter();writer.SetFileName(str(path));writer.SetInputData(self.sources['holes'])
        if writer.Write()!=1:raise OSError('VTP файл бичиж чадсангүй.')
