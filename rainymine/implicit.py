"""Bounded RBF grade isosurfaces. No fault, structural or stratigraphic constraints."""
import math
import numpy as np
from scipy.interpolate import RBFInterpolator
from .core import finite
from .geometry import validate_mesh_data, mesh_report


def implicit_surface(samples, bounds, cutoff, resolution=31, smoothing=0., neighbors=32,cancel=None):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    finite(*bounds, cutoff, smoothing)
    if len(bounds)!=6 or any(bounds[i]>=bounds[i+3] for i in range(3)):
        raise ValueError('RBF bounds буруу.')
    if type(resolution)!=int or not 5<=resolution<=60 or smoothing<0 or not 4<=neighbors<=128:
        raise ValueError('RBF resolution 5–60, smoothing ≥ 0, neighbors 4–128 байна.')
    if not 4<=len(samples)<=10000:raise ValueError('RBF-д 4–10000 композит шаардлагатай.')
    xyz=np.asarray([s['xyz'] for s in samples],dtype=float)
    values=np.asarray([s['grade'] for s in samples],dtype=float)
    if xyz.shape!=(len(samples),3) or not np.isfinite(xyz).all() or not np.isfinite(values).all():
        raise ValueError('RBF сорьцын координат/агуулга буруу.')
    if len(np.unique(xyz,axis=0))!=len(xyz):raise ValueError('RBF сорьцын координат давхардсан.')
    if not values.min()<cutoff<values.max():raise ValueError('Cutoff нь сорьцын min/max хооронд байна.')
    origin=np.asarray(bounds[:3],dtype=float);scale=float(max(np.subtract(bounds[3:],bounds[:3])))
    # A single scale preserves metric isotropy and avoids large-coordinate cancellation.
    rbf=RBFInterpolator((xyz-origin)/scale,values,kernel='linear',degree=0,
                        neighbors=min(neighbors,len(xyz)),smoothing=smoothing)
    axes=[np.linspace(bounds[i],bounds[i+3],resolution) for i in range(3)]
    zz,yy,xx=np.meshgrid(axes[2],axes[1],axes[0],indexing='ij')
    targets=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()))
    field=np.empty(len(targets))
    for start in range(0,len(targets),4096):
        if cancel and cancel():raise RuntimeError('RBF тооцоо цуцлагдлаа.')
        field[start:start+4096]=rbf((targets[start:start+4096]-origin)/scale)
    if not np.isfinite(field).all():raise ValueError('RBF finite бус үр дүн гаргалаа.')
    image=vtk.vtkImageData();image.SetDimensions(resolution,resolution,resolution)
    image.SetOrigin(0,0,0)
    image.SetSpacing(*[(bounds[i+3]-bounds[i])/(resolution-1) for i in range(3)])
    scalars=numpy_to_vtk(field,deep=True);scalars.SetName('RBF grade');image.GetPointData().SetScalars(scalars)
    contour=vtk.vtkFlyingEdges3D();contour.SetInputData(image);contour.SetValue(0,cutoff);contour.Update()
    # A contour passing exactly through grid vertices can emit coincident points
    # and zero-area triangles (including platform-dependent rounding cases).
    cleaner=vtk.vtkCleanPolyData();cleaner.SetInputConnection(contour.GetOutputPort())
    cleaner.ToleranceIsAbsoluteOn();cleaner.SetAbsoluteTolerance(scale*1e-10)
    triangles=vtk.vtkTriangleFilter();triangles.SetInputConnection(cleaner.GetOutputPort())
    triangles.PassLinesOff();triangles.PassVertsOff();triangles.Update()
    poly=triangles.GetOutput()
    if poly.GetNumberOfCells()==0:raise ValueError('Bounds дотор cutoff гадарга олдсонгүй.')
    vertices=[(np.asarray(poly.GetPoint(i))+origin).tolist() for i in range(poly.GetNumberOfPoints())]
    faces=[]
    for i in range(poly.GetNumberOfCells()):
        if i%1024==0 and cancel and cancel():raise RuntimeError('RBF тооцоо цуцлагдлаа.')
        face=[int(poly.GetCell(i).GetPointId(j)) for j in range(3)]
        if len(set(face))!=3:continue
        a,b,c=[np.asarray(vertices[j]) for j in face]
        if np.linalg.norm(np.cross(b-a,c-a))<=scale**2*1e-14:continue
        faces.append(face)
    if not faces:raise ValueError('RBF contour бүх гурвалжин талбайгүй байна.')
    mesh={'name':f'RBF grade iso {cutoff:g}','vertices':vertices,'faces':faces,'role':'implicit_grade'}
    validate_mesh_data(mesh)
    metadata={'algorithm':'local linear RBF grade isosurface','cutoff':cutoff,'bounds':list(bounds),
              'resolution':resolution,'smoothing':smoothing,'neighbors':min(neighbors,len(xyz)),
              'sample_count':len(samples),'extrapolation':'unconstrained inside user bounds',
              'removed_degenerate_triangles':contour.GetOutput().GetNumberOfCells()-len(faces),
              'fault_constraints':False,'geological_review':False,'mesh_report':mesh_report(mesh)}
    return mesh,metadata
