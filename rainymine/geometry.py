"""Explicit geometry exchange and validation. Coordinates remain in project metres."""
from pathlib import Path
import math
from .core import finite, atomic_write

def points_valid(points,minimum=1):
    if not isinstance(points,list) or not minimum<=len(points)<=200000:raise ValueError('Геометрийн цэгийн тоо буруу.')
    for p in points:
        if not isinstance(p,(list,tuple)) or len(p)!=3:raise ValueError('XYZ цэг шаардлагатай.')
        finite(*p)
        if max(map(abs,p))>1e9:raise ValueError('Координат хэт их.')

def validate_workspace(workspace):
    for s in workspace.get('strings',[]):
        points_valid(s['points'],3 if s.get('closed') else 2)
        if not isinstance(s.get('name'),str):raise ValueError('String нэр буруу.')
        if s.get('closed'):validate_polygon(s['points'])
    for mesh in workspace.get('meshes',[]):validate_mesh_data(mesh)
    model=workspace.get('block_model')
    if model:
        from .spatial import model_basis
        model_basis(model)
        if 'grid_origin' in model:points_valid([model['grid_origin']])
        if len(model['blocks'])>50000:raise ValueError('Блокийн тоо хэт их.')
        for b in model['blocks']:
            finite(b['x'],b['y'],b['z'],b['dx'],b['dy'],b['dz'])
            if min(b['dx'],b['dy'],b['dz'])<=0:raise ValueError('Блокийн хэмжээ эерэг байна.')
            if b.get('grade') is not None:finite(b['grade'])
            if b.get('variance') is not None:finite(b['variance'])
    # Disallow non-finite values anywhere in persisted runs or planning metadata.
    def check(value,depth=0):
        if depth>30:raise ValueError('Өгөгдлийн бүтэц хэт гүн.')
        if isinstance(value,float):finite(value)
        elif isinstance(value,dict):
            for item in value.values():check(item,depth+1)
        elif isinstance(value,(list,tuple)):
            for item in value:check(item,depth+1)
    check(workspace)

def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def intersects(a,b,c,d):
    # Includes collinear/touching edges; callers exempt adjacent endpoints.
    c1,c2,c3,c4=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if c1*c2<0 and c3*c4<0:return True
    def on(p,q,r):return abs(cross(p,q,r))<1e-8 and min(p[0],q[0])-1e-8<=r[0]<=max(p[0],q[0])+1e-8 and min(p[1],q[1])-1e-8<=r[1]<=max(p[1],q[1])+1e-8
    return any((on(a,b,c),on(a,b,d),on(c,d,a),on(c,d,b)))

def validate_polygon(points):
    points_valid(points,3)
    if points[0]==points[-1]:raise ValueError('Хаалттай polygon-ийн эхний цэгийг сүүлд давтахгүй.')
    if len({(p[0],p[1]) for p in points})!=len(points):raise ValueError('Polygon XY цэг давхардсан.')
    # Shift before area calculation to avoid cancellation in large mine coordinates.
    x0,y0,_=points[0]
    area=sum((a[0]-x0)*(b[1]-y0)-(b[0]-x0)*(a[1]-y0) for a,b in zip(points,points[1:]+points[:1]))/2
    if abs(area)<1e-8:raise ValueError('Polygon талбай 0 байна.')
    if len(points)>2000:raise ValueError('Polygon 2000 цэгээс их.')
    n=len(points)
    for i in range(n):
        for j in range(i+1,n):
            if j in (i,(i+1)%n) or i==(j+1)%n:continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):raise ValueError('Polygon өөрийгөө огтолж байна.')
    return abs(area)

def inside_polygon(x,y,points):
    inside=False
    for a,b in zip(points,points[1:]+points[:1]):
        if abs(cross(a,b,(x,y)))<1e-8 and min(a[0],b[0])-1e-8<=x<=max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8<=y<=max(a[1],b[1])+1e-8:return True
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside

def validate_mesh_data(mesh):
    points_valid(mesh['vertices'],3)
    if not isinstance(mesh['faces'],list) or not 1<=len(mesh['faces'])<=400000:raise ValueError('Mesh face тоо буруу.')
    for face in mesh['faces']:
        if len(face)!=3 or any(type(i)!=int or not 0<=i<len(mesh['vertices']) for i in face) or len(set(face))!=3:raise ValueError('Гурвалжны индекс буруу.')

def mesh_report(mesh):
    import numpy as np
    validate_mesh_data(mesh);v=np.array(mesh['vertices'],dtype=float);origin=v.mean(axis=0);v=v-origin
    edges={};orientation={};volume=area=0.;degenerate=0;seen=set();duplicates=0
    for face in mesh['faces']:
        a,b,c=face;key=tuple(sorted(face))
        if key in seen:duplicates+=1
        seen.add(key);normal=np.cross(v[b]-v[a],v[c]-v[a]);ar=float(np.linalg.norm(normal))/2;area+=ar
        if ar<1e-10:degenerate+=1
        volume+=float(np.dot(v[a],np.cross(v[b],v[c])))/6
        for x,y in ((a,b),(b,c),(c,a)):
            key=tuple(sorted((x,y)));edges[key]=edges.get(key,0)+1;orientation[key]=orientation.get(key,0)+(1 if x<y else -1)
    open_edges=sum(n==1 for n in edges.values());nonmanifold=sum(n>2 for n in edges.values())
    inconsistent=sum(n==2 and orientation[k]!=0 for k,n in edges.items())
    closed=not any((open_edges,nonmanifold,inconsistent,degenerate,duplicates))
    return {'triangles':len(mesh['faces']),'area_m2':area,'open_edges':open_edges,'nonmanifold_edges':nonmanifold,'inconsistent_edges':inconsistent,'degenerate_faces':degenerate,'duplicate_faces':duplicates,'closed_oriented_topology':closed,'signed_volume_m3':volume if closed else None,'self_intersections_checked':False,'note':'Топологийн шалгалт. Self-intersection/геологийн хүчинтэй байдлыг батлаагүй.'}

def read_obj(path):
    if Path(path).stat().st_size>32_000_000:raise ValueError('OBJ файл хэт том.')
    vertices=[];faces=[]
    for number,line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(),1):
        tokens=line.split()
        if not tokens or tokens[0].startswith('#'):continue
        if tokens[0]=='v':
            if len(tokens)<4:raise ValueError(f'OBJ {number}: XYZ буруу.')
            vertices.append([float(t) for t in tokens[1:4]])
        elif tokens[0]=='f':
            indices=[]
            for token in tokens[1:]:
                n=int(token.split('/')[0]);index=n-1 if n>0 else len(vertices)+n
                if n==0 or not 0<=index<len(vertices):raise ValueError('OBJ face индекс буруу.')
                indices.append(index)
            # Require triangles: fan triangulation of a concave polygon is not safe.
            if len(indices)!=3:raise ValueError('OBJ нь triangulated mesh байна. N-gon дэмжихгүй.')
            faces.append(indices)
    mesh={'name':Path(path).stem,'vertices':vertices,'faces':faces};validate_mesh_data(mesh);return mesh

def write_obj(path,mesh):
    validate_mesh_data(mesh)
    text='# RAINYMINE coordinates: project metres\n'+''.join('v '+' '.join(f'{x:.12g}' for x in p)+'\n' for p in mesh['vertices'])
    text+=''.join('f '+' '.join(str(i+1) for i in f)+'\n' for f in mesh['faces']);atomic_write(path,text)

def read_dxf(path):
    import ezdxf
    if Path(path).stat().st_size>32_000_000:raise ValueError('DXF файл хэт том.')
    doc=ezdxf.readfile(path);strings=[];vertices=[];faces=[];unsupported={}
    for e in doc.modelspace():
        kind=e.dxftype();points=None;closed=False
        if kind=='LINE':points=[list(e.dxf.start),list(e.dxf.end)]
        elif kind=='LWPOLYLINE':
            if any(abs(p[4])>1e-12 for p in e.get_points()):raise ValueError('DXF bulge/нуман polyline дэмжихгүй.')
            points=[list(p) for p in e.vertices_in_wcs()];closed=e.closed
        elif kind=='POLYLINE' and not e.is_poly_face_mesh and not e.is_polygon_mesh:points=[list(v.dxf.location) for v in e.vertices];closed=e.is_closed
        elif kind=='3DFACE':
            p=[list(e.dxf.get(f'vtx{i}')) for i in range(4)];offset=len(vertices);vertices.extend(p[:3]);faces.append([offset,offset+1,offset+2])
            if p[3]!=p[2]:vertices.append(p[3]);faces.append([offset,offset+2,offset+3])
        else:unsupported[kind]=unsupported.get(kind,0)+1
        if points:
            if closed and points[0]==points[-1]:points.pop()
            strings.append({'name':f'{e.dxf.layer}-{len(strings)+1}','points':points,'closed':bool(closed)})
    # DXF 3DFACE uses repeated vertices; merge exact coordinates for topology.
    unique=[];lookup={};remap={}
    for i,p in enumerate(vertices):
        k=tuple(p)
        if k not in lookup:lookup[k]=len(unique);unique.append(p)
        remap[i]=lookup[k]
    meshes=[{'name':Path(path).stem,'vertices':unique,'faces':[[remap[i] for i in f] for f in faces]}] if faces else []
    result={'strings':strings,'meshes':meshes};validate_workspace(result)
    if not strings and not meshes:raise ValueError('Дэмжигдсэн LINE/POLYLINE/3DFACE олдсонгүй.')
    return result,unsupported

def write_dxf(path,workspace):
    import ezdxf
    validate_workspace(workspace);doc=ezdxf.new('R2010');doc.header['$INSUNITS']=6;msp=doc.modelspace()
    for s in workspace.get('strings',[]):msp.add_polyline3d(s['points'],close=s.get('closed',False))
    for m in workspace.get('meshes',[]):
        for f in m['faces']:msp.add_3dface([m['vertices'][i] for i in f])
    # ezdxf writes to a string buffer before atomic replacement.
    import io
    out=io.StringIO();doc.write(out);atomic_write(path,out.getvalue())

def constrained_tin(surface,breaklines):
    import vtk
    points_valid(surface,3);vertices=[];lookup={};required=[]
    def insert(p):
        key=tuple(p[:2])
        if key in lookup:
            i=lookup[key]
            if abs(vertices[i][2]-p[2])>1e-6:raise ValueError('Ижил XY дээр зөрүүтэй Z байна.')
            return i
        i=len(vertices);vertices.append(list(p));lookup[key]=i;return i
    for p in surface:insert(p)
    for s in breaklines:
        pp=s['points'];points_valid(pp,2)
        edges=list(zip(pp,pp[1:]+(pp[:1] if s.get('closed') else [])))
        for a,b in edges:
            if a[:2]==b[:2]:raise ValueError('Босоо breakline дэмжихгүй.')
            required.append((insert(a),insert(b)))
    if len(required)>3000:raise ValueError('Breakline-ийн segment хэт олон.')
    for i,(a,b) in enumerate(required):
        for c,d in required[i+1:]:
            if len({a,b,c,d})<4:continue
            if intersects(vertices[a],vertices[b],vertices[c],vertices[d]):raise ValueError('Breakline огтлолцсон. Огтлолцолд ижил зангилаа нэмнэ үү.')
    # Shift to local origin to preserve triangulation precision.
    origin=vertices[0];pts=vtk.vtkPoints();pts.SetDataTypeToDouble()
    for p in vertices:pts.InsertNextPoint(*(p[i]-origin[i] for i in range(3)))
    poly=vtk.vtkPolyData();poly.SetPoints(pts);constraints=vtk.vtkPolyData();constraints.SetPoints(pts);lines=vtk.vtkCellArray()
    for a,b in required:lines.InsertNextCell(2);lines.InsertCellPoint(a);lines.InsertCellPoint(b)
    constraints.SetLines(lines);tri=vtk.vtkDelaunay2D();tri.SetInputData(poly);tri.SetSourceData(constraints);tri.SetTolerance(0);tri.Update();output=tri.GetOutput()
    faces=[];edges=set()
    for i in range(output.GetNumberOfCells()):
        cell=output.GetCell(i);f=[cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())]
        if len(f)==3:
            faces.append(f)
            for a,b in zip(f,f[1:]+f[:1]):edges.add(tuple(sorted((a,b))))
    if not faces:raise ValueError('TIN үүссэнгүй.')
    if any(tuple(sorted(e)) not in edges for e in required):raise ValueError('Breakline-ийг бүрэн мөрдсөнгүй. Геометрээ шалгана уу.')
    return {'name':'DTM • breakline','vertices':vertices,'faces':faces,'role':'dtm'}
