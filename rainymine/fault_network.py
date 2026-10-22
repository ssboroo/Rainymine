"""Signed-RBF fault barriers with scoped DAG relationships and explicit restoration.

No slip is inferred from a surface. Geometry is sampled and requires interpretation.
"""
from copy import deepcopy
import numpy as np
from scipy.interpolate import RBFInterpolator


class FaultNetwork:
    def __init__(self,faults):
        if not isinstance(faults,list) or len(faults)>8:raise ValueError('Fault network: 0–8 faults required')
        self.faults=deepcopy(faults);self.fields=[];self.names={};self.order=[]
        for i,f in enumerate(self.faults):
            name=f.get('name')
            if not isinstance(name,str) or not name.strip() or name in self.names:raise ValueError('Fault name empty/duplicate')
            self.names[name]=i
            slip=np.asarray(f.get('slip',[0,0,0]),dtype=float)
            if slip.shape!=(3,) or not np.isfinite(slip).all():raise ValueError('Explicit slip must be finite XYZ')
            if f.get('kind','plane')=='plane':
                p=np.asarray(f.get('point'),dtype=float);n=np.asarray(f.get('normal'),dtype=float)
                if p.shape!=(3,) or n.shape!=(3,) or not np.isfinite(p).all() or not np.isfinite(n).all() or np.linalg.norm(n)<1e-12:raise ValueError('Invalid fault plane')
                self.fields.append(('plane',p,n/np.linalg.norm(n)))
            elif f['kind']=='rbf':
                controls=f.get('constraints',[])
                if not 4<=len(controls)<=10000:raise ValueError('RBF fault needs 4–10000 signed controls')
                xyz=np.asarray([[r[a] for a in ('x','y','z')] for r in controls],dtype=float)
                values=np.asarray([r['value'] for r in controls],dtype=float)
                ranges=np.asarray(f.get('ranges',[100,100,100]),dtype=float)
                smooth=float(f.get('smoothing',0));kernel=f.get('kernel','linear');neighbors=f.get('neighbors',32)
                if not np.isfinite(xyz).all() or not np.isfinite(values).all() or not values.min()<0<values.max() or len(np.unique(xyz,axis=0))!=len(xyz):raise ValueError('Invalid/duplicate RBF controls; positive and negative signs required')
                if ranges.shape!=(3,) or not np.isfinite(ranges).all() or np.any(ranges<=0) or not np.isfinite(smooth) or smooth<0 or kernel not in ('linear','cubic','thin_plate_spline') or type(neighbors)!=int or not 4<=neighbors<=128:raise ValueError('Invalid RBF fault settings')
                origin=xyz.mean(axis=0)
                rbf=RBFInterpolator((xyz-origin)/ranges,values,kernel=kernel,degree=0 if kernel=='linear' else 1,neighbors=min(neighbors,len(values)),smoothing=smooth)
                self.fields.append(('rbf',origin,ranges,rbf))
            else:raise ValueError('Unknown fault kind')
        visiting=set();visited=set()
        def visit(i):
            if i in visiting:raise ValueError('Fault DAG cycle')
            if i in visited:return
            visiting.add(i);conditions=self.faults[i].get('active_if',{})
            if not isinstance(conditions,dict):raise ValueError('active_if must map parent name to side 0/1')
            for parent,side in conditions.items():
                if parent not in self.names or type(side)!=int or side not in (0,1):raise ValueError('Unknown fault parent / side')
                visit(self.names[parent])
            visiting.remove(i);visited.add(i);self.order.append(i)
        for i in range(len(faults)):visit(i)

    def signed(self,index,points):
        points=np.asarray(points,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Fault targets must be finite N×3')
        field=self.fields[index]
        if field[0]=='plane':return (points-field[1])@field[2]
        result=field[3]((points-field[1])/field[2])
        if not np.isfinite(result).all():raise ValueError('Non-finite fault RBF')
        return result

    def classify(self,points,cancel=None):
        points=np.asarray(points,dtype=float)
        if points.size==0:points=points.reshape(0,3)
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Fault targets must be finite')
        codes=np.zeros(len(points),dtype=np.int64);sides={};active={}
        for i in self.order:
            if cancel and cancel():raise RuntimeError('Fault classification cancelled')
            enabled=np.ones(len(points),dtype=bool)
            for parent,side in self.faults[i].get('active_if',{}).items():
                p=self.names[parent];enabled&=active[p]&(sides[p]==side)
            values=np.zeros(len(points))
            indices=np.flatnonzero(enabled)
            for start in range(0,len(indices),4096):
                if cancel and cancel():raise RuntimeError('Fault classification cancelled')
                ids=indices[start:start+4096];values[ids]=self.signed(i,points[ids])
            positive=values>=-1e-9;sides[i]=positive.astype(int);active[i]=enabled
            codes[enabled&positive]|=1<<i
            # Scoped inactive regions must not merge with an active negative side.
            if self.faults[i].get('active_if'):codes[enabled]|=1<<(len(self.faults)+i)
        return codes

    def zone(self,point):return int(self.classify([point])[0])

    def restore(self,points,cancel=None):
        """Explicit piecewise translation, youngest (DAG parent) first.

        Parent relationships are geometric scopes, not inferred fault chronology.
        Input order defines restoration chronology when faults are independent.
        """
        restored=np.array(points,dtype=float,copy=True)
        if restored.size==0:restored=restored.reshape(0,3)
        if restored.ndim!=2 or restored.shape[1]!=3 or not np.isfinite(restored).all():raise ValueError('Restoration targets must be finite N×3')
        for i in self.order:
            codes=self.classify(restored,cancel);enabled=(codes&(1<<i))!=0
            if self.faults[i].get('active_if'):enabled&=(codes&(1<<(len(self.faults)+i)))!=0
            restored[enabled]-=np.asarray(self.faults[i].get('slip',[0,0,0]))
        return restored


def fault_mesh(network,index,bounds,resolution=25,cancel=None):
    """Sample one fault's zero field; scope clipped at cell resolution."""
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    bounds=np.asarray(bounds,dtype=float)
    if bounds.shape!=(6,) or not np.isfinite(bounds).all() or np.any(bounds[:3]>=bounds[3:]) or type(resolution)!=int or not 5<=resolution<=60:raise ValueError('Invalid fault mesh bounds/resolution')
    axes=[np.linspace(bounds[i],bounds[i+3],resolution) for i in range(3)]
    zz,yy,xx=np.meshgrid(axes[2],axes[1],axes[0],indexing='ij');points=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()))
    signed=np.empty(len(points))
    for start in range(0,len(points),4096):
        if cancel and cancel():raise RuntimeError('Fault mesh cancelled')
        signed[start:start+4096]=network.signed(index,points[start:start+4096])
    image=vtk.vtkImageData();image.SetDimensions(resolution,resolution,resolution);image.SetOrigin(0,0,0);image.SetSpacing(*((bounds[3:]-bounds[:3])/(resolution-1)))
    image.GetPointData().SetScalars(numpy_to_vtk(signed,deep=True))
    contour=vtk.vtkFlyingEdges3D();contour.SetInputData(image);contour.SetValue(0,0);contour.Update();poly=contour.GetOutput()
    vertices=[(np.asarray(poly.GetPoint(i))+bounds[:3]).tolist() for i in range(poly.GetNumberOfPoints())];faces=[]
    centers=[]
    for i in range(poly.GetNumberOfCells()):
        cell=poly.GetCell(i);centers.append(np.mean([vertices[cell.GetPointId(j)] for j in range(cell.GetNumberOfPoints())],axis=0))
    codes_all=network.classify(centers,cancel)
    for i in range(poly.GetNumberOfCells()):
        if i%1024==0 and cancel and cancel():raise RuntimeError('Fault mesh cancelled')
        cell=poly.GetCell(i)
        if cell.GetNumberOfPoints()!=3:continue
        face=[cell.GetPointId(j) for j in range(3)];center=np.mean([vertices[j] for j in face],axis=0)
        # Display clipping uses centroid; estimation uses exact evaluated zone codes.
        visible=True;codes=codes_all[i]
        for parent,side in network.faults[index].get('active_if',{}).items():
            p=network.names[parent]
            if bool(codes&(1<<p))!=bool(side):visible=False
            if network.faults[p].get('active_if') and not codes&(1<<(len(network.faults)+p)):visible=False
        if visible:faces.append(face)
    if not faces:raise ValueError('No fault zero surface within bounds')
    return {'name':'Fault • '+network.faults[index]['name'],'vertices':vertices,'faces':faces,'role':'fault_guide','sampling_resolution':resolution,'geological_review':False}
