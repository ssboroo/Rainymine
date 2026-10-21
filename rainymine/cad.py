"""Native solid Boolean, conservative repair, local affine editing and snapping."""
from copy import deepcopy
import numpy as np
from scipy.spatial import cKDTree
from .geometry import validate_mesh_data,mesh_report
from .spatial import search_basis


def _solid(mesh,origin):
    import manifold3d as md
    validate_mesh_data(mesh)
    vertices=np.ascontiguousarray(np.asarray(mesh['vertices'],dtype=np.float64)-origin)
    faces=np.ascontiguousarray(mesh['faces'],dtype=np.uint64)
    solid=md.Manifold(md.Mesh64(vertices,faces))
    if solid.status()==md.Error.NoError and solid.volume()<0:
        solid=md.Manifold(md.Mesh64(vertices,np.ascontiguousarray(faces[:,::-1])))
    if solid.status()!=md.Error.NoError or solid.is_empty() or solid.volume()<=0:
        raise ValueError('CSG-д oriented watertight 2-manifold solid шаардлагатай: '+str(solid.status()))
    return solid


def boolean_mesh(first,second,operation):
    import manifold3d as md
    if operation not in ('union','intersection','difference'):raise ValueError('Boolean operation буруу.')
    origin=np.asarray(first['vertices'],dtype=float).mean(axis=0)
    a,b=_solid(first,origin),_solid(second,origin)
    result={'union':lambda:a+b,'intersection':lambda:a^b,'difference':lambda:a-b}[operation]()
    if result.status()!=md.Error.NoError:raise ValueError('Boolean failed: '+str(result.status()))
    if result.is_empty():return None,{'empty':True,'operation':operation,'volume_m3':0.}
    output=result.to_mesh64()
    mesh={'name':operation+' · '+first['name']+' · '+second['name'],'role':'boolean_solid',
          'vertices':(np.asarray(output.vert_properties)[:,:3]+origin).tolist(),
          'faces':np.asarray(output.tri_verts,dtype=np.int64).tolist()}
    validate_mesh_data(mesh)
    return mesh,{'empty':False,'operation':operation,'volume_m3':float(result.volume()),'report':mesh_report(mesh),
                 'kernel':'Manifold double precision; common local origin','reviewed':False}


def repair_mesh(mesh,merge_tolerance=1e-6,fill_holes=0):
    """Clean duplicate vertices, orient connected normals and optionally cap small holes.

    No silent self-intersection removal or guarantee that a repaired surface is ore.
    The before/after topology report is required for review.
    """
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    validate_mesh_data(mesh)
    if not np.isfinite([merge_tolerance,fill_holes]).all() or merge_tolerance<0 or fill_holes<0:
        raise ValueError('Repair tolerance буруу.')
    origin=np.asarray(mesh['vertices'],dtype=float).mean(axis=0)
    points=vtk.vtkPoints();points.SetData(numpy_to_vtk(np.asarray(mesh['vertices'])-origin,deep=True))
    cells=vtk.vtkCellArray()
    for face in mesh['faces']:
        cells.InsertNextCell(3)
        for i in face:cells.InsertCellPoint(i)
    poly=vtk.vtkPolyData();poly.SetPoints(points);poly.SetPolys(cells)
    clean=vtk.vtkCleanPolyData();clean.SetInputData(poly);clean.ToleranceIsAbsoluteOn();clean.SetAbsoluteTolerance(merge_tolerance)
    upstream=clean
    if fill_holes:
        fill=vtk.vtkFillHolesFilter();fill.SetInputConnection(clean.GetOutputPort());fill.SetHoleSize(fill_holes);upstream=fill
    triangle=vtk.vtkTriangleFilter();triangle.SetInputConnection(upstream.GetOutputPort());triangle.PassLinesOff();triangle.PassVertsOff()
    normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(triangle.GetOutputPort());normals.ConsistencyOn();normals.AutoOrientNormalsOn();normals.SplittingOff();normals.Update()
    output=normals.GetOutput();faces=[];seen=set()
    vertices=np.asarray([output.GetPoint(i) for i in range(output.GetNumberOfPoints())])
    for i in range(output.GetNumberOfCells()):
        cell=output.GetCell(i)
        if cell.GetNumberOfPoints()!=3:continue
        face=[cell.GetPointId(j) for j in range(3)];key=tuple(sorted(face))
        if key in seen or len(set(face))!=3:continue
        a,b,c=vertices[face]
        if np.linalg.norm(np.cross(b-a,c-a))<=1e-14:continue
        faces.append(face);seen.add(key)
    repaired={**deepcopy(mesh),'name':mesh['name']+' · repaired','vertices':(vertices+origin).tolist(),'faces':faces}
    return repaired,{'before':mesh_report(mesh),'after':mesh_report(repaired),'self_intersections_checked':False,
                     'merge_tolerance_m':merge_tolerance,'fill_hole_radius_m':fill_holes}


def transform_geometry(geometry,translation=(0,0,0),angles=(90,0,0),scale=(1,1,1),pivot=None):
    """ENU affine: scale in local axes then rotate around explicit world pivot."""
    key='vertices' if 'vertices' in geometry else 'points';xyz=np.asarray(geometry[key],dtype=float)
    t=np.asarray(translation,dtype=float);scale=np.asarray(scale,dtype=float);basis=search_basis(*angles)
    pivot=xyz.mean(axis=0) if pivot is None else np.asarray(pivot,dtype=float)
    if xyz.ndim!=2 or xyz.shape[1]!=3 or t.shape!=(3,) or scale.shape!=(3,) or pivot.shape!=(3,) or not all(np.isfinite(a).all() for a in (xyz,t,scale,pivot)) or np.any(scale<=0):
        raise ValueError('Transform утга буруу; scale эерэг байна.')
    result=deepcopy(geometry);result[key]=(((xyz-pivot)*scale)@basis.T+pivot+t).tolist()
    return result


class SnapIndex:
    def __init__(self,points,segments=()):
        self.points=np.asarray(points,dtype=float);self.segments=np.asarray(segments,dtype=np.int64).reshape(-1,2)
        if self.points.ndim!=2 or self.points.shape[1]!=3 or not np.isfinite(self.points).all() or not len(self.points):raise ValueError('Snap points буруу.')
        if self.segments.size and (self.segments.min()<0 or self.segments.max()>=len(points)):raise ValueError('Snap segment индекс буруу.')
        self.origin=self.points[0];self.tree=cKDTree(self.points-self.origin)
    def nearest(self,point,tolerance,include_segments=True):
        p=np.asarray(point,dtype=float)
        if p.shape!=(3,) or not np.isfinite(p).all() or not np.isfinite(tolerance) or tolerance<0:raise ValueError('Snap query буруу.')
        distance,index=self.tree.query(p-self.origin);answer={'kind':'vertex','index':int(index),'point':self.points[index].tolist(),'distance':float(distance)}
        if include_segments and len(self.segments):
            a=self.points[self.segments[:,0]]-self.origin;b=self.points[self.segments[:,1]]-self.origin;d=b-a
            denominator=np.einsum('ij,ij->i',d,d);fraction=np.divide(np.einsum('ij,ij->i',(p-self.origin)-a,d),denominator,out=np.zeros(len(a)),where=denominator>0)
            q=a+np.clip(fraction,0,1)[:,None]*d;dist=np.linalg.norm(q-(p-self.origin),axis=1);i=int(np.argmin(dist))
            if dist[i]<answer['distance']:answer={'kind':'segment','index':i,'point':(q[i]+self.origin).tolist(),'distance':float(dist[i])}
        return answer if answer['distance']<=tolerance else None
