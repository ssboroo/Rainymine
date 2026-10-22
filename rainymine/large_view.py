"""Bounded external-data previews using native GPU glyph/point mappers and RTC."""
import math
import numpy as np
from .block_store import scan_block_batches,block_metadata


def parquet_preview(path,maximum=250000,bounds=None,cutoff=None,cancel=None,memory_budget_mib=512):
    import pyarrow.parquet as pq
    if type(maximum) is not int or not 1<=maximum<=10000000:raise ValueError('Preview limit 1…10000000 байна.')
    if cutoff is not None and not math.isfinite(cutoff):raise ValueError('Cutoff буруу.')
    metadata=block_metadata(path);count=pq.ParquetFile(path).metadata.num_rows;stride=max(1,math.ceil(count/maximum))
    admitted=min(count,maximum)*256
    if not math.isfinite(memory_budget_mib) or memory_budget_mib<=0 or admitted>memory_budget_mib*1024**2:raise ValueError('Preview allocation estimate exceeds selected RAM budget (256 bytes/displayed block)')
    xyz=[];sizes=[];grades=[];ids=[];matched=0
    for batch in scan_block_batches(path,bounds,columns=['row_id','xc','yc','zc','dx','dy','dz','grade']):
        if cancel and cancel():raise RuntimeError('Parquet preview cancelled.')
        column=lambda name:batch.column(batch.schema.get_field_index(name)).to_numpy(zero_copy_only=False)
        row=np.asarray(column('row_id'),dtype=np.int64);grade=np.asarray(column('grade'),dtype=float)
        valid=np.ones(len(grade),dtype=bool)
        if cutoff is not None:valid&=grade>=cutoff
        matched+=int(valid.sum());valid&=row%stride==0
        xyz.append(np.column_stack([column(k) for k in ('xc','yc','zc')])[valid]+metadata['origin'])
        sizes.append(np.column_stack([column(k) for k in ('dx','dy','dz')])[valid]);grades.append(grade[valid]);ids.append(row[valid])
    return {'xyz':np.concatenate(xyz) if xyz else np.empty((0,3)), 'sizes':np.concatenate(sizes) if sizes else np.empty((0,3)),
            'grade':np.concatenate(grades) if grades else np.empty(0),'source_index':np.concatenate(ids) if ids else np.empty(0,dtype=np.int64),
            'source_points':count,'matched_before_sampling':matched,'stride':stride,'crs':metadata.get('crs'),
            'grid_angles':metadata['model'].get('grid_angles',[90,0,0]),'kind':'blocks','grade_unit':metadata.get('grade_unit',''),
            'allocation_admission_bytes':admitted,'memory_budget_mib':memory_budget_mib,
            'null_rendering':'NaN grade shown grey; never assigned zero grade'}


def preview_polydata(payload):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
    xyz=np.asarray(payload['xyz'],dtype=float);ids=np.asarray(payload['source_index'],dtype=np.int64)
    if xyz.ndim!=2 or xyz.shape[1]!=3 or len(xyz)!=len(ids) or not len(xyz) or not np.isfinite(xyz).all():raise ValueError('Preview-д finite цэг алга.')
    origin=(xyz.min(axis=0)+xyz.max(axis=0))/2;local=np.asarray(xyz-origin,dtype=np.float32)
    points=vtk.vtkPoints();points.SetData(numpy_to_vtk(local,deep=False));poly=vtk.vtkPolyData();poly.SetPoints(points)
    identifier=numpy_to_vtkIdTypeArray(ids,deep=False);identifier.SetName('source_index');poly.GetPointData().AddArray(identifier)
    if payload.get('kind')=='blocks':
        sizes=np.asarray(payload['sizes'],dtype=np.float32)
        if sizes.shape!=xyz.shape or not np.isfinite(sizes).all() or np.any(sizes<=0):raise ValueError('Preview block хэмжээ буруу.')
        scales=numpy_to_vtk(sizes,deep=False);scales.SetName('size');poly.GetPointData().AddArray(scales)
        values=np.asarray(payload['grade'],dtype=np.float32)
    else:values=np.asarray(payload.get('intensity',xyz[:,2]),dtype=np.float32)
    if values.shape!=(len(xyz),) or np.isinf(values).any() or (payload.get('kind')!='blocks' and not np.isfinite(values).all()):raise ValueError('Preview scalar буруу.')
    scalar=numpy_to_vtk(values,deep=False);scalar.SetName('value');poly.GetPointData().SetScalars(scalar)
    # Keep every backing array alive for the full native VTK dataset lifetime.
    poly._numpy_buffers=(local,ids,values)+((sizes,) if payload.get('kind')=='blocks' else ())
    return poly,origin


def pick_blocks_ray(ray_origin,ray_direction,payload):
    """Vectorised world-space ray/oriented-box test, returning original source ID."""
    from .spatial import search_basis
    origin=np.asarray(ray_origin,dtype=float);direction=np.asarray(ray_direction,dtype=float)
    if origin.shape!=(3,) or direction.shape!=(3,) or not np.isfinite(origin).all() or not np.isfinite(direction).all() or np.linalg.norm(direction)<1e-12:
        raise ValueError('Picking ray буруу.')
    direction/=np.linalg.norm(direction);basis=search_basis(*payload.get('grid_angles',[90,0,0]))
    xyz=np.asarray(payload['xyz']);sizes=np.asarray(payload['sizes']);d=direction@basis
    best_distance=float('inf');best_index=None
    for start in range(0,len(xyz),65536):
        delta=(origin-xyz[start:start+65536])@basis;half=sizes[start:start+65536]/2
        low=np.full_like(delta,-np.inf);high=np.full_like(delta,np.inf);valid=np.ones(len(delta),dtype=bool)
        for axis in range(3):
            if abs(d[axis])<1e-12:valid&=abs(delta[:,axis])<=half[:,axis]
            else:
                a=(-half[:,axis]-delta[:,axis])/d[axis];b=(half[:,axis]-delta[:,axis])/d[axis]
                low[:,axis]=np.minimum(a,b);high[:,axis]=np.maximum(a,b)
        entry=np.maximum(low.max(axis=1),0);exit=high.min(axis=1);valid&=exit>=entry
        if valid.any():
            distances=np.where(valid,entry,np.inf);index=int(np.argmin(distances))
            if distances[index]<best_distance:best_distance=float(distances[index]);best_index=start+index
    if best_index is None:return None
    return {'source_index':int(payload['source_index'][best_index]),'distance':best_distance,
            'world_point':(origin+best_distance*direction).tolist()}



class LargePreviewFactory:
    @staticmethod
    def show(parent,payload,title):
        import vtk
        from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        from .spatial import search_basis
        from PySide6.QtCore import Qt
        dialog=QDialog(parent);dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True);dialog.setWindowTitle(title);dialog.resize(1100,800);layout=QVBoxLayout(dialog)
        summary=QLabel(f"Эх: {payload['source_points']:,} · Шүүлтэд: {payload['matched_before_sampling']:,} · Preview: {len(payload['xyz']):,} · stride {payload['stride']}")
        summary.setWordWrap(True);layout.addWidget(summary);widget=QVTKRenderWindowInteractor(dialog);layout.addWidget(widget,1)
        poly,origin=preview_polydata(payload);renderer=vtk.vtkRenderer();renderer.SetBackground(.94,.97,.99);widget.GetRenderWindow().AddRenderer(renderer)
        if payload.get('kind')=='blocks':
            source=vtk.vtkCubeSource();source.Update()
            basis=search_basis(*payload.get('grid_angles',[90,0,0]));matrix=vtk.vtkMatrix4x4();matrix.Identity()
            for i in range(3):
                for j in range(3):matrix.SetElement(i,j,basis[i,j])
            # Per-instance dimensions scale before source rotation. Source rotation
            # is only correct for equal XYZ scales, so use orientation per instance.
            mapper=vtk.vtkGlyph3DMapper();mapper.SetSourceConnection(source.GetOutputPort());mapper.SetInputData(poly);mapper.SetScaleArray('size');mapper.SetScaleModeToScaleByVectorComponents();mapper.SetScaleFactor(1);mapper.OrientOff();mapper.SetSelectionIdArray('source_index');mapper.UseSelectionIdsOn()
            if not np.allclose(basis,np.eye(3),atol=1e-8):
                # VTK accepts per-instance quaternion orientations, scalar first.
                from scipy.spatial.transform import Rotation
                from vtk.util.numpy_support import numpy_to_vtk
                q=Rotation.from_matrix(basis).as_quat();quaternions=np.tile([q[3],q[0],q[1],q[2]],(poly.GetNumberOfPoints(),1));array=numpy_to_vtk(quaternions,deep=False);array.SetName('orientation');poly.GetPointData().AddArray(array)
                poly._numpy_buffers += (quaternions,)
                mapper.SetOrientationArray('orientation');mapper.SetOrientationModeToQuaternion();mapper.OrientOn()
        else:
            mapper=vtk.vtkPointGaussianMapper();mapper.SetInputData(poly);mapper.SetScaleFactor(0);mapper.EmissiveOff()
        values=np.asarray(payload.get('grade',payload.get('intensity',payload['xyz'][:,2])),dtype=float)
        known=values[np.isfinite(values)];limits=(float(known.min()),float(known.max())) if len(known) else (0.,1.)
        if limits[0]==limits[1]:limits=(limits[0],limits[0]+1)
        lookup=vtk.vtkLookupTable();lookup.SetNanColor(.65,.69,.72,1);lookup.SetRange(*limits);lookup.Build()
        if payload.get('categories'):
            import colorsys
            categories=sorted(payload['categories'].items());lookup.SetNumberOfTableValues(len(categories));lookup.IndexedLookupOn();lookup.Build()
            for i,(code,name) in enumerate(categories):
                lookup.SetTableValue(i,*colorsys.hsv_to_rgb((i*.61803398875)%1,.65,.85),1)
                lookup.SetAnnotation(vtk.vtkVariant(float(code)),str(name))
        mapper.SetLookupTable(lookup);mapper.SetScalarRange(*limits);actor=vtk.vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetPointSize(3);renderer.AddActor(actor)
        legend=vtk.vtkScalarBarActor();legend.SetLookupTable(lookup);legend.SetTitle(payload.get('scalar_title') or ('Grade '+payload.get('grade_unit','') if payload.get('kind')=='blocks' else 'Value'))
        legend.SetWidth(.13);legend.SetHeight(.65);legend.SetPosition(.85,.2)
        from .scene import readable_text
        legend.DrawAnnotationsOn()
        for prop in (legend.GetLabelTextProperty(),legend.GetTitleTextProperty(),legend.GetAnnotationTextProperty()):
            prop.SetColor(.1,.2,.3);prop.SetFontSize(11);readable_text(prop)
        renderer.AddActor2D(legend)
        note='Саарал = харьяалалгүй материал.' if payload.get('categories') else 'Саарал = агуулгагүй (NULL).'
        picked=QLabel('Эх файлын индексийг хадгалсан GPU preview. '+note+' FPS нь төхөөрөмжөөс хамаарна.');picked.setWordWrap(True);layout.addWidget(picked)
        def select(obj,event):
            x,y=widget.GetEventPosition()
            if payload.get('kind')=='blocks':
                ray=[]
                for depth in (0,1):
                    renderer.SetDisplayPoint(x,y,depth);renderer.DisplayToWorld();value=renderer.GetWorldPoint();ray.append(np.array(value[:3])/value[3]+origin)
                result=pick_blocks_ray(ray[0],ray[1]-ray[0],payload)
                if result:picked.setText('Сонгосон эх индекс: '+str(result['source_index']))
                return
            selector=vtk.vtkHardwareSelector();selector.SetRenderer(renderer);selector.SetArea(x,y,x,y);selector.SetFieldAssociation(vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS);selection=selector.Select()
            if selection and selection.GetNumberOfNodes():
                values=selection.GetNode(0).GetSelectionList()
                if values.GetNumberOfTuples():
                    index=int(values.GetTuple1(0))
                    if payload.get('kind')!='blocks' and 0<=index<len(payload['source_index']):index=int(payload['source_index'][index])
                    picked.setText('Сонгосон эх индекс: '+str(index))
        widget.AddObserver('LeftButtonPressEvent',select);widget.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera());renderer.ResetCamera();renderer.GetActiveCamera().ParallelProjectionOn()
        renderer.GetActiveCamera().Azimuth(35);renderer.GetActiveCamera().Elevation(25);renderer.GetActiveCamera().Zoom(.72);renderer.ResetCameraClippingRange()
        widget.Initialize();dialog.finished.connect(lambda code:widget.Finalize());dialog.show();widget.GetRenderWindow().Render()
        # Retain C++ pipeline and numpy owners for the native widget lifetime.
        dialog.pipeline=(poly,origin,renderer,mapper,actor,widget,payload,lookup,legend);parent._preview_dialogs.append(dialog)
        dialog.finished.connect(lambda code:parent._preview_dialogs.remove(dialog) if dialog in parent._preview_dialogs else None)
        return dialog
