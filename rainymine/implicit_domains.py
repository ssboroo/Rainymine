"""Contact-sign RBF surfaces with anisotropic trend and explicit fault-zone barriers."""
import numpy as np
from scipy.interpolate import RBFInterpolator
from .core import finite
from .spatial import search_basis
from .domains import validate_faults,fault_zone
from .geometry import mesh_report


def contact_surface(constraints,bounds,resolution=25,kernel='thin_plate_spline',smoothing=0.,neighbors=32,
                    ranges=(100,100,100),angles=(90,0,0),faults=(),cancel=None):
    """Input signed contact constraints x/y/z/value; zero is the contact.

    Each fault zone is solved independently. Cells crossing a zone boundary are
    removed before contouring, preventing interpolated connections across faults.
    Result is a surface with boundary gaps, not an automatically certified solid.
    """
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    finite(*bounds,smoothing,*ranges)
    if len(bounds)!=6 or any(bounds[i]>=bounds[i+3] for i in range(3)) or type(resolution) is not int or not 5<=resolution<=60 or min(ranges)<=0 or smoothing<0 or kernel not in ('linear','cubic','thin_plate_spline') or not 4<=neighbors<=128:
        raise ValueError('Contact RBF тохиргоо буруу.')
    if not 4<=len(constraints)<=10000:raise ValueError('4…10000 contact constraints шаардлагатай.')
    faults=list(faults);validate_faults(faults);origin=np.asarray(bounds[:3]);basis=search_basis(*angles)
    xyz=np.array([[r[k] for k in ('x','y','z')] for r in constraints],dtype=float);values=np.array([r['value'] for r in constraints],dtype=float)
    if not np.isfinite(xyz).all() or not np.isfinite(values).all() or len(np.unique(xyz,axis=0))!=len(xyz):raise ValueError('Contact finite бус / координат давхардсан.')
    zones=[fault_zone(p,faults) for p in xyz];unique=sorted(set(zones));axes=[np.linspace(bounds[i],bounds[i+3],resolution) for i in range(3)]
    zz,yy,xx=np.meshgrid(axes[2],axes[1],axes[0],indexing='ij');targets=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()))
    target_zones=[fault_zone(p,faults) for p in targets];vertices=[];faces=[];counts=[]
    for zone in unique:
        if cancel and cancel():raise RuntimeError('Contact modelling cancelled.')
        select=np.array([z==zone for z in zones]);valid=np.array([z==zone for z in target_zones]);v=values[select]
        if len(v)<4 or not v.min()<0<v.max():raise ValueError(f'Fault zone {zone}: ≥4 support, positive ба negative signs шаардлагатай.')
        transform=lambda p:((p-origin)@basis)/np.asarray(ranges)
        interpolator=RBFInterpolator(transform(xyz[select]),v,kernel=kernel,degree=0 if kernel=='linear' else 1,
                                     neighbors=min(neighbors,len(v)),smoothing=smoothing)
        field=np.zeros(len(targets));indices=np.flatnonzero(valid)
        for start in range(0,len(indices),4096):
            if cancel and cancel():raise RuntimeError('Contact modelling cancelled.')
            ids=indices[start:start+4096];field[ids]=interpolator(transform(targets[ids]))
        if not np.isfinite(field).all():raise ValueError('RBF finite бус field.')
        image=vtk.vtkImageData();image.SetDimensions(resolution,resolution,resolution);image.SetOrigin(0,0,0);image.SetSpacing(*[(bounds[i+3]-bounds[i])/(resolution-1) for i in range(3)])
        signed=numpy_to_vtk(field,deep=True);signed.SetName('signed');mask=numpy_to_vtk(valid.astype(np.uint8),deep=True);mask.SetName('valid');image.GetPointData().AddArray(signed);image.GetPointData().AddArray(mask)
        threshold=vtk.vtkThreshold();threshold.SetInputData(image);threshold.SetInputArrayToProcess(0,0,0,vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS,'valid');threshold.SetLowerThreshold(1);threshold.SetUpperThreshold(1);threshold.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN);threshold.AllScalarsOn()
        contour=vtk.vtkContourFilter();contour.SetInputConnection(threshold.GetOutputPort());contour.SetInputArrayToProcess(0,0,0,vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS,'signed');contour.SetValue(0,0)
        triangle=vtk.vtkTriangleFilter();triangle.SetInputConnection(contour.GetOutputPort());triangle.Update();poly=triangle.GetOutput();offset=len(vertices)
        vertices.extend((np.asarray(poly.GetPoint(i))+origin).tolist() for i in range(poly.GetNumberOfPoints()))
        count=0
        for i in range(poly.GetNumberOfCells()):
            cell=poly.GetCell(i)
            if cell.GetNumberOfPoints()!=3:continue
            face=[offset+cell.GetPointId(j) for j in range(3)];a,b,c=np.asarray([vertices[j] for j in face])
            if len(set(face))==3 and np.linalg.norm(np.cross(b-a,c-a))>1e-12:faces.append(face);count+=1
        counts.append({'zone':zone,'samples':len(v),'faces':count})
    if not faces:raise ValueError('Bounds дотор zero-contact surface алга.')
    mesh={'name':'Contact RBF · '+kernel,'role':'implicit_contact','vertices':vertices,'faces':faces}
    return mesh,{'kernel':kernel,'ranges':list(ranges),'angles':list(angles),'fault_zone_counts':counts,'fault_barrier':'crossing cells omitted; finite grid gap',
                 'bounds':list(bounds),'resolution':resolution,'extrapolation':'within supplied bounds','geological_review':False,'report':mesh_report(mesh)}


def lithology_constraints(project,rock,length=5):
    """Binary rock/non-rock midpoint controls from real logged intervals.

    A classification field, not a signed-distance measurement. Unlogged regions
    supply no constraints, and no outside rock is invented beyond the drillholes.
    """
    import math
    from .core import Trajectory
    finite(length)
    if length<=0:raise ValueError('Lithology support length эерэг байна.')
    project.validate();codes={r.rock for r in project.lithology}
    if rock not in codes or len(codes)<2:raise ValueError('Target ба non-target lithology logs шаардлагатай.')
    total=sum(math.ceil((r.to_m-r.from_m)/length) for r in project.lithology)
    if total>10000:raise ValueError('Lithology RBF >10000 support; support length-ийг нэмнэ үү.')
    surveys={}
    for s in project.surveys:surveys.setdefault(s.hole_id,[]).append(s)
    traces={h.hole_id:Trajectory(h,surveys.get(h.hole_id,[])) for h in project.collars};rows=[]
    for r in project.lithology:
        n=math.ceil((r.to_m-r.from_m)/length)
        for i in range(n):
            xyz=traces[r.hole_id].at(r.from_m+(i+.5)*(r.to_m-r.from_m)/n)
            rows.append({**dict(zip('xyz',xyz)),'value':1. if r.rock==rock else -1.})
    return rows
