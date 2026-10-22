"""Survey geometry and screening tools; no explosive loading or slope certification."""
import math
import numpy as np
from .geometry import validate_mesh_data


def _clip_values(vertices,positive=True):
    result=[]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        inside_a=a[2]>=0 if positive else a[2]<=0;inside_b=b[2]>=0 if positive else b[2]<=0
        if inside_a:result.append(a)
        if inside_a!=inside_b:
            t=a[2]/(a[2]-b[2]);result.append([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),0.])
    return result


def _integral(vertices):
    if len(vertices)<3:return 0.
    a=np.array(vertices[0]);total=0.
    for i in range(1,len(vertices)-1):
        b,c=np.array(vertices[i]),np.array(vertices[i+1]);ab,ac=b[:2]-a[:2],c[:2]-a[:2];area=abs(float(ab[0]*ac[1]-ab[1]*ac[0]))/2
        total+=area*(a[2]+b[2]+c[2])/3
    return total


def tin_cut_fill(before,after,density=None,cancel=None):
    """Exact vertical integration over triangle overlay; positive delta is fill."""
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    for mesh in (before,after):validate_mesh_data(mesh)
    if max(len(before['faces']),len(after['faces']))>50000:raise ValueError('TIN overlay supports up to 50000 faces per surface')
    if density is not None and (not math.isfinite(density) or density<=0):raise ValueError('Positive declared bulk density required')
    origin=np.asarray(before['vertices'],float)[:,:2].mean(axis=0)
    def triangles(mesh):
        vertices=np.asarray(mesh['vertices'],float).copy();vertices[:,:2]-=origin;polygons=[];planes=[]
        for face in mesh['faces']:
            if len(face)!=3:raise ValueError('Triangular TIN required')
            tri=vertices[face];poly=Polygon(tri[:,:2])
            if poly.area<=1e-10:raise ValueError('Vertical/degenerate triangle is not a terrain TIN')
            planes.append(np.linalg.solve(np.column_stack((tri[:,:2],np.ones(3))),tri[:,2]));polygons.append(poly)
        tree=STRtree(polygons)
        for i,poly in enumerate(polygons):
            if cancel and cancel():raise RuntimeError('TIN validation cancelled')
            for j in tree.query(poly):
                if int(j)>i and poly.intersection(polygons[int(j)]).area>1e-8:raise ValueError('TIN triangles overlap in XY; terrain must be single-valued')
        return polygons,planes,tree
    a,ap,_=triangles(before);b,bp,tree=triangles(after);cut=fill=area=0.;pairs=0
    for i,poly in enumerate(a):
        if cancel and cancel():raise RuntimeError('Cut/fill cancelled')
        for j in tree.query(poly):
            overlap=poly.intersection(b[int(j)])
            if overlap.is_empty or overlap.area<=1e-10:continue
            if overlap.geom_type!='Polygon':raise ValueError('Unexpected TIN overlay geometry')
            delta=bp[int(j)]-ap[i];vertices=[[x,y,float(delta@[x,y,1])] for x,y in list(overlap.exterior.coords)[:-1]]
            fill+=_integral(_clip_values(vertices,True));cut-=_integral(_clip_values(vertices,False));area+=overlap.area;pairs+=1
    if not pairs:raise ValueError('Surfaces have no common XY coverage')
    before_area=sum(p.area for p in a);after_area=sum(p.area for p in b)
    return {'cut_m3':max(0.,cut),'fill_m3':max(0.,fill),'net_fill_m3':fill-cut,
            'cut_tonnes':cut*density if density is not None else None,'fill_tonnes':fill*density if density is not None else None,
            'density_t_m3':density,'common_area_m2':area,'before_area_m2':before_area,'after_area_m2':after_area,
            'before_coverage_fraction':area/before_area,'after_coverage_fraction':area/after_area,
            'triangle_intersections':pairs,'scope':'vertical TIN-to-TIN overlay on common XY coverage only; no volume outside supplied surfaces; no overhangs'}


def survey_pattern(polygon,spacing,burden,top,bottom,staggered=False,azimuth=90,maximum=10000):
    """Survey/sample-hole coordinates only; no explosive quantities or blast design."""
    from shapely.geometry import Polygon,Point
    from .spatial import search_basis
    numbers=[spacing,burden,top,bottom,azimuth]
    if not all(math.isfinite(v) for v in numbers) or min(spacing,burden)<=0 or bottom>=top:raise ValueError('Positive spacing and top > bottom required')
    outline=Polygon(np.asarray(polygon,float)[:,:2])
    if not outline.is_valid or outline.area<=0:raise ValueError('Valid survey boundary required')
    basis=search_basis(azimuth,0,0)[:2,:2];origin=np.asarray(outline.centroid.coords[0]);local=(np.asarray(polygon,float)[:,:2]-origin)@basis
    low=local.min(axis=0);high=local.max(axis=0);nx=math.floor((high[0]-low[0])/spacing)+1;ny=math.floor((high[1]-low[1])/burden)+1
    if nx*ny>maximum*4:raise ValueError('Pattern exceeds bounded candidate budget')
    rows=[]
    for j in range(ny):
        for i in range(nx):
            xy=origin+(low+[i*spacing+(spacing/2 if staggered and j%2 else 0),j*burden])@basis.T
            if outline.covers(Point(xy)):
                rows.append({'hole_id':f'GC-{len(rows)+1:05d}','x':float(xy[0]),'y':float(xy[1]),'z':top,'depth':top-bottom,'azimuth':0,'dip':-90})
                if len(rows)>maximum:raise ValueError('Pattern hole limit exceeded')
    return rows


def ore_control_polygons(model,elevation,cutoff,cancel=None):
    from shapely.geometry import box
    from shapely.ops import unary_union
    from .spatial import model_basis
    if not math.isfinite(elevation) or not math.isfinite(cutoff) or cutoff<0 or not np.allclose(model_basis(model),np.eye(3),atol=1e-8):raise ValueError('Ore control currently requires an axis-aligned model and valid bench/cutoff')
    groups={'ore':[],'waste':[],'unknown':[]}
    for i,b in enumerate(model.get('blocks',[])):
        if i%1000==0 and cancel and cancel():raise RuntimeError('Ore control cancelled')
        if b['z']-b['dz']/2<=elevation<b['z']+b['dz']/2:
            kind='unknown' if b.get('grade') is None else 'ore' if b['grade']>=cutoff else 'waste'
            groups[kind].append(box(b['x']-b['dx']/2,b['y']-b['dy']/2,b['x']+b['dx']/2,b['y']+b['dy']/2))
    output=[]
    for kind,polys in groups.items():
        merged=unary_union(polys)
        for polygon in ([merged] if merged.geom_type=='Polygon' else list(getattr(merged,'geoms',[]))):
            if polygon.is_empty:continue
            output.append({'kind':kind,'area_m2':polygon.area,'elevation':elevation,
                           'outer':[[x,y,elevation] for x,y in list(polygon.exterior.coords)[:-1]],
                           'holes':[[[x,y,elevation] for x,y in list(r.coords)[:-1]] for r in polygon.interiors]})
    if not output:raise ValueError('No blocks intersect the selected elevation')
    # Classification boundaries must not hide overlapping source blocks.
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    outlines=[Polygon(np.asarray(a['outer'])[:,:2],[np.asarray(r)[:,:2] for r in a['holes']]) for a in output];tree=STRtree(outlines)
    for i,pa in enumerate(outlines):
        for j in tree.query(pa):
            if int(j)>i and pa.intersection(outlines[int(j)]).area>1e-8:raise ValueError('Ore/waste source geometry overlaps')
    return output


def stereonet(planes,projection='Schmidt',slope_direction=None,slope_dip=None,friction=None,lateral_limit=20):
    """Lower-hemisphere poles and geometric susceptibility, not a safety factor."""
    if not 1<=len(planes)<=500 or projection not in ('Schmidt','Wulff'):raise ValueError('1–500 oriented planes and Schmidt/Wulff projection required')
    rows=[];normals=[]
    for i,p in enumerate(planes):
        dd,dip=float(p['dip_direction']),float(p['dip'])
        if not math.isfinite(dd) or not math.isfinite(dip) or not 0<=dip<=90:raise ValueError('Dip direction and dip 0–90 required; unorientated alpha/beta is insufficient')
        trend=math.radians((dd+180)%360);theta=math.radians(dip);radius=math.sqrt(2)*math.sin(theta/2) if projection=='Schmidt' else math.tan(theta/2)
        normals.append(np.array([math.sin(trend)*math.sin(theta),math.cos(trend)*math.sin(theta),-math.cos(theta)]))
        rows.append({'index':i+1,'dip_direction':dd%360,'dip':dip,'x':radius*math.sin(trend),'y':radius*math.cos(trend)})
    checks=[];wedges=[]
    if slope_direction is not None:
        if any(v is None or not math.isfinite(v) for v in (slope_direction,slope_dip,friction,lateral_limit)) or not 0< slope_dip<90 or not 0<=friction<90 or not 0<lateral_limit<=90:raise ValueError('Valid slope/friction screening settings required')
        angle=lambda a,b:abs((a-b+180)%360-180)
        for r in rows:
            planar=angle(r['dip_direction'],slope_direction)<=lateral_limit and friction<r['dip']<slope_dip
            toppling=angle(r['dip_direction'],slope_direction+180)<=lateral_limit and r['dip']>90-slope_dip+friction
            checks.append({'index':r['index'],'planar_screen':planar,'flexural_toppling_screen':toppling})
        for i,n in enumerate(normals):
            for j,m in enumerate(normals[i+1:],i+1):
                line=np.cross(n,m);length=np.linalg.norm(line)
                if length<1e-10:continue
                line/=length
                if line[2]>0:line=-line
                trend=math.degrees(math.atan2(line[0],line[1]))%360;plunge=math.degrees(math.asin(np.clip(-line[2],-1,1)))
                delta=math.radians(angle(trend,slope_direction));apparent=math.degrees(math.atan(math.tan(math.radians(slope_dip))*math.cos(delta)))
                if friction<plunge<apparent:wedges.append({'plane_a':i+1,'plane_b':j+1,'trend':trend,'plunge':plunge,'wedge_screen':True})
    return {'projection':projection,'poles':rows,'plane_checks':checks,'wedge_candidates':wedges,
            'scope':'preliminary orientation/friction screening; no persistence, water pressure, forces, direct-toppling or factor-of-safety analysis; qualified geotechnical review required'}
