"""VTK 3D scene; all coordinates are shifted around the local origin."""
import math
import colorsys
import vtk
import numpy as np
from .spatial import model_basis
from .core import Trajectory

class Scene:
    def __init__(self,window):
        self.window=window;self.renderer=vtk.vtkRenderer();window.AddRenderer(self.renderer)
        self.renderer.SetBackground(.035,.055,.09);self.renderer.SetBackground2(.10,.15,.22);self.renderer.GradientBackgroundOn()
        self.mode='assay';self.project=None;self.origin=(0,0,0);self.sources={};self.actors={};self.labels=[]
        self.section=None;self.pipeline=[];self.paths={};self.grade_max=1
        light=vtk.vtkLight();light.SetLightTypeToHeadlight();self.renderer.AddLight(light)
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        self.lut=vtk.vtkLookupTable();self.lut.SetNumberOfTableValues(256);self.lut.SetNanColor(.45,.5,.6,1)
        self.lut.SetBelowRangeColor(.4,.45,.55,1);self.lut.UseBelowRangeColorOn()
        for i in range(256):
            t=i/255
            self.lut.SetTableValue(i,*colorsys.hsv_to_rgb((1-t)*2/3,.85,.95),1)
        self.lut.Build()
        self.legend=vtk.vtkScalarBarActor();self.legend.SetLookupTable(self.lut);self.legend.SetNumberOfLabels(5)
        self.legend.SetWidth(.11);self.legend.SetHeight(.35);self.legend.SetPosition(.85,.12)
        self.legend.SetUnconstrainedFontSize(True)
        self.legend.GetTitleTextProperty().SetFontSize(14)
        self.legend.GetLabelTextProperty().SetFontSize(12)
        self.legend.GetTitleTextProperty().ItalicOff()
        self.legend.GetLabelTextProperty().ItalicOff()
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
        rock_codes={name:i+1 for i,name in enumerate(sorted({a.rock for a in project.lithology}))}
        self.grade_max=max(1,len(rock_codes)) if self.mode=='lithology' else max(1,max((a.grade for a in project.assays),default=1))
        self.lut.SetTableRange(0,self.grade_max);self.legend.SetTitle('Rock code' if self.mode=='lithology' else project.grade_unit)
        points=vtk.vtkPoints();points.SetDataTypeToDouble();lines=vtk.vtkCellArray();scalars=vtk.vtkFloatArray();scalars.SetName('grade')
        collars=vtk.vtkPoints();collars.SetDataTypeToDouble()
        assays={};surveys={}
        for station in project.surveys:surveys.setdefault(station.hole_id,[]).append(station)
        for a in (project.lithology if self.mode=='lithology' else project.assays):assays.setdefault(a.hole_id,[]).append(a)
        for h in project.collars:
            tr=Trajectory(h,surveys.get(h.hole_id,[]));self.paths[h.hole_id]=tr
            collars.InsertNextPoint(*self.local((h.x,h.y,h.z)))
            previous=0
            for a in sorted(assays.get(h.hole_id,[]),key=lambda a:a.from_m):
                if a.from_m>previous:self.polyline(points,lines,scalars,tr,previous,a.from_m,-1)
                self.polyline(points,lines,scalars,tr,a.from_m,a.to_m,rock_codes[a.rock] if self.mode=='lithology' else a.grade);previous=a.to_m
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
        if len(project.collars)<=200:
            for h in project.collars:
                text=vtk.vtkBillboardTextActor3D();text.SetInput(h.hole_id);p=self.local((h.x,h.y,h.z));text.SetPosition(p[0],p[1],p[2]+4)
                text.GetTextProperty().SetFontSize(11);text.GetTextProperty().SetColor(.12,.14,.2);text.GetTextProperty().SetOrientation(90)
                self.renderer.AddActor(text);self.labels.append(text)
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
        self.add_workspace(project.workspace)
        if self.marker:self.marker.EnabledOff();self.marker=None
        if self.window.GetInteractor():
            axes=vtk.vtkAxesActor();self.marker=vtk.vtkOrientationMarkerWidget();self.marker.SetOrientationMarker(axes)
            self.marker.SetInteractor(self.window.GetInteractor());self.marker.SetViewport(0,0,.18,.18);self.marker.EnabledOn();self.marker.InteractiveOff()
        self.set_section(None,render=False);self.reset()

    def add_workspace(self,workspace):
        for index,s in enumerate(workspace.get('strings',[])):
            pts=vtk.vtkPoints();pts.SetDataTypeToDouble();lines=vtk.vtkCellArray();pp=s['points']+(s['points'][:1] if s.get('closed') else [])
            lines.InsertNextCell(len(pp))
            for p in pp:lines.InsertCellPoint(pts.InsertNextPoint(*self.local(p)))
            poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetLines(lines)
            self.add_poly('string_'+str(index),poly,(.95,.75,.3),line=True)
        for index,m in enumerate(workspace.get('meshes',[])):
            pts=vtk.vtkPoints();pts.SetDataTypeToDouble();faces=vtk.vtkCellArray()
            for p in m['vertices']:pts.InsertNextPoint(*self.local(p))
            for face in m['faces']:
                faces.InsertNextCell(3)
                for i in face:faces.InsertCellPoint(i)
            poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetPolys(faces)
            self.add_poly('mesh_'+str(index),poly,(.52,.65,.83),opacity=.45)
        model=workspace.get('block_model')
        if model:
            basis=model_basis(model);pivot=np.asarray(model.get('grid_origin',model['bounds'][:3]))
            pts=vtk.vtkPoints();pts.SetDataTypeToDouble();faces=vtk.vtkCellArray();values=vtk.vtkFloatArray();values.SetName('grade')
            for b in model['blocks']:
                if b.get('grade') is None:continue
                world=np.array([b['x'],b['y'],b['z']]);grid_center=pivot+(world-pivot)@basis
                center=self.local(world);dims=[b['dx'],b['dy'],b['dz']]
                if workspace.get('block_display','slices')=='slices':
                    bounds=model['bounds'];planes=[(bounds[i]+bounds[i+3])/2 for i in range(3)]
                    for axis in range(3):
                        if not grid_center[axis]-dims[axis]/2<=planes[axis]<grid_center[axis]+dims[axis]/2:continue
                        axes=[i for i in range(3) if i!=axis];start=pts.GetNumberOfPoints()
                        for u,v in ((-1,-1),(1,-1),(1,1),(-1,1)):
                            p=list(grid_center);p[axis]=planes[axis];p[axes[0]]+=u*dims[axes[0]]/2;p[axes[1]]+=v*dims[axes[1]]/2;pts.InsertNextPoint(*self.local(pivot+(np.asarray(p)-pivot)@basis.T))
                        faces.InsertNextCell(4)
                        for i in range(4):faces.InsertCellPoint(start+i)
                        values.InsertNextValue(b['grade'])
                else:
                    start=pts.GetNumberOfPoints()
                    for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
                        offset=np.array([x*b['dx']/2,y*b['dy']/2,z*b['dz']/2])@basis.T
                        pts.InsertNextPoint(*(np.asarray(center)+offset))
                    for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                        faces.InsertNextCell(4)
                        for i in face:faces.InsertCellPoint(start+i)
                        values.InsertNextValue(b['grade'])
            poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetPolys(faces);poly.GetCellData().SetScalars(values)
            self.add_poly('blocks',poly,(.4,.8,.7),opacity=1.,scalar=True)
            self.actors['blocks'].SetVisibility(self.mode!='lithology')

    def add_poly(self,key,poly,color,opacity=1.,line=False,scalar=False):
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(poly)
        if scalar:mapper.SetLookupTable(self.lut);mapper.SetScalarRange(0,self.grade_max);mapper.SetScalarModeToUseCellData()
        else:mapper.ScalarVisibilityOff()
        actor=vtk.vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetColor(*color);actor.GetProperty().SetOpacity(opacity);actor.GetProperty().SetAmbient(.6);actor.GetProperty().SetDiffuse(.4)
        if line:actor.GetProperty().SetLineWidth(3)
        self.sources[key]=poly;self.actors[key]=actor;self.renderer.AddActor(actor)

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
        for label in self.labels:label.SetVisibility(section is None and self.actors['holes'].GetVisibility())
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
        if name=='holes':
            self.legend.SetVisibility(value)
            for label in self.labels:label.SetVisibility(value and self.section is None)
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
