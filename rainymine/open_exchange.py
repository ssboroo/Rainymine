"""Atomic open exchange exports; world metres, explicit CRS/units and real NULLs.

OMF targets GMG 2.0-beta.1. GeoPackage is a GIS exchange, not a block-model store.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import csv,gzip,hashlib,io,json,math,os,sqlite3,sys,tempfile,zipfile
import numpy as np
from pyproj import CRS
from .core import Trajectory,finite
from .spatial import model_basis

OMF_VERSION='2.0-beta.1'
SPEC_COMMIT='64d305790b3415618a01f00a94cd914acd0b80ba'


@contextmanager
def atomic_destination(path):
    path=Path(path);fd,name=tempfile.mkstemp(prefix='.rainymine-exchange-',suffix=path.suffix,dir=path.parent);os.close(fd)
    try:
        yield Path(name)
        with open(name,'r+b') as stream:os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def contract(project):
    project.validate()
    if not project.crs_code:raise ValueError('Экспортын өмнө төслийн CRS-ийг тодорхойлно уу.')
    crs=CRS.from_user_input(project.crs_code)
    if not crs.is_projected or len(crs.axis_info)<2 or any(abs(a.unit_conversion_factor-1)>1e-9 for a in crs.axis_info[:2]):
        raise ValueError('Солилцоонд projected metre CRS шаардлагатай; эхлээд CRS хөрвүүлнэ үү.')
    if not project.grade_unit:raise ValueError('Агуулгын нэгж тодорхойгүй.')
    model=project.workspace.get('block_model')
    return {'schema':'rainymine.exchange/1','crs':crs.to_string(),'crs_wkt':crs.to_wkt(),
            'axis_order':'X=easting, Y=northing, Z=elevation; always XY','coordinate_unit':'m','depth_unit':'m',
            'vertical_datum':'unspecified; requires site confirmation','grade_unit':project.grade_unit,
            'density_unit':'t/m3','null':'native NULL; CSV empty field; never zero or -999',
            'rotation_convention':'azimuth clockwise from north, dip upwards, roll; basis columns local axes in world ENU',
            'block_model':None if not model else {k:deepcopy(v) for k,v in model.items() if k!='blocks'},
            'classification':'UNCLASSIFIED; export does not certify resources'}


def _cancel(cancel):
    if cancel and cancel():raise RuntimeError('Экспорт цуцлагдлаа; өмнөх файл хэвээр.')


def _traces(project,step=5):
    surveys={}
    for s in project.surveys:surveys.setdefault(s.hole_id,[]).append(s)
    total=0
    for h in project.collars:
        total+=math.ceil(h.depth/step)+len(surveys.get(h.hole_id,[]))+2
        if total>1000000:raise ValueError('Нийт замналын 1000000 цэгийн экспортын хязгаар хэтэрсэн.')
        trace=Trajectory(h,surveys.get(h.hole_id,[]));depths=sorted(set([0.,h.depth]+[s.depth for s in surveys.get(h.hole_id,[])]+np.arange(0,h.depth,step).tolist()))
        if len(depths)>200000:raise ValueError('Цооногийн замналын цэг хэт олон.')
        yield h,depths,[list(trace.at(d)) for d in depths]


class OmfWriter:
    def __init__(self,archive):self.archive=archive;self.counter=0
    def array(self,columns,types,nullable=False):
        import pyarrow as pa
        import pyarrow.parquet as pq
        fields=[pa.field(name,kind,nullable=nullable) for name,kind in types.items()]
        table=pa.Table.from_arrays([pa.array(columns[f.name],type=f.type) for f in fields],schema=pa.schema(fields))
        if not nullable and any(c.null_count for c in table.columns):raise ValueError('OMF required array-д NULL байна.')
        buffer=io.BytesIO();pq.write_table(table,buffer,compression='zstd',version='2.4',use_dictionary=False)
        self.counter+=1;name=f'{self.counter}.parquet';self.archive.writestr(name,buffer.getvalue())
        return {'filename':name,'item_count':table.num_rows}
    def vertices(self,points,origin):
        import pyarrow as pa
        points=np.asarray(points,dtype=np.float64)-origin
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('OMF vertex буруу.')
        return self.array({k:points[:,i] for i,k in enumerate('xyz')},{k:pa.float64() for k in 'xyz'})
    def attributes(self,rows,location,units):
        import pyarrow as pa
        output=[]
        for key in sorted(set().union(*(r.keys() for r in rows))):
            values=[r.get(key) for r in rows];present=[v for v in values if v is not None];metadata={}
            if present and all(isinstance(v,bool) for v in present):kind='Boolean';column='bool';dtype=pa.bool_()
            elif all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in present):
                kind='Number';column='number';dtype=pa.int64() if present and all(isinstance(v,int) for v in present) else pa.float64()
                for value in present:finite(value)
            else:
                kind='Text';column='text';dtype=pa.string()
                if any(not isinstance(v,str) for v in present):
                    values=[None if v is None else json.dumps(v,ensure_ascii=False,allow_nan=False) for v in values];metadata={'encoding':'JSON'}
            output.append({'name':key,'location':location,'units':units.get(key,''),'metadata':metadata,
                           'data':{'type':kind,'values':self.array({column:values},{column:dtype},True)}})
        return output


def _omf_blocks(model,writer,origin,grade_unit):
    import pyarrow as pa
    blocks=model['blocks'];size=np.asarray(model.get('size'),dtype=float);bounds=np.asarray(model.get('bounds'),dtype=float)
    if size.shape!=(3,) or bounds.shape!=(6,) or not np.isfinite(size).all() or np.any(size<=0) or not np.isfinite(bounds).all() or np.any(bounds[3:]<=bounds[:3]):raise ValueError('OMF parent size/bounds шаардлагатай.')
    counts=np.ceil((bounds[3:]-bounds[:3])/size).astype(np.int64)
    if np.any(counts>=2**32):raise ValueError('OMF grid count uint32 хязгаараас их.')
    pivot=np.asarray(model.get('grid_origin',bounds[:3]),dtype=float);basis=model_basis(model)
    xyz=np.array([[b[k] for k in 'xyz'] for b in blocks]);dims=np.array([[b[k] for k in ('dx','dy','dz')] for b in blocks]);local=(xyz-pivot)@basis
    low=local-dims/2;parents=np.floor(low/size+1e-8).astype(np.int64);mins=(low-parents*size)/size;maxs=mins+dims/size
    if np.any(parents<0) or np.any(parents>=counts) or np.any(mins< -1e-7) or np.any(maxs>1+1e-7):raise ValueError('Блок parent grid-ээс гарсан / parent boundary давсан байна.')
    mins=np.clip(mins,0,1);maxs=np.clip(maxs,0,1)
    # Source model may be sparse or contain clipped edge parents. Store every
    # actual leaf as one freeform sub-block, including full undivided parents.
    groups={}
    for i,key in enumerate(map(tuple,parents)):
        siblings=groups.setdefault(key,[])
        if len(siblings)>=512:raise ValueError('Нэг parent-д 512-оос олон leaf байна.')
        for j in siblings:
            if np.all(np.minimum(maxs[i],maxs[j])-np.maximum(mins[i],mins[j])>1e-8):raise ValueError('OMF давхардсан block/sub-block; экспорт цуцлагдав.')
        siblings.append(i)
    columns={f'parent_{a}':parents[:,i] for i,a in enumerate('uvw')};types={k:pa.uint32() for k in columns}
    for prefix,values in [('min',mins),('max',maxs)]:
        for i,a in enumerate('uvw'):key=f'corner_{prefix}_{a}';columns[key]=values[:,i];types[key]=pa.float64()
    geometry={'type':'BlockModel','orient':{'origin':(pivot-origin).tolist(),**{a:basis[:,i].tolist() for i,a in enumerate('uvw')}},
              'grid':{'type':'Regular','size':size.tolist(),'count':counts.tolist()},
              'subblocks':{'type':'Freeform','subblocks':writer.array(columns,types)}}
    rows=[{'rainymine_row_id':i,**b} for i,b in enumerate(blocks)]
    return {'name':'Block model','geometry':geometry,'metadata':{'rainymine':{k:v for k,v in model.items() if k!='blocks'},'layout':'actual leaves; absent parents remain absent'},
            'attributes':writer.attributes(rows,'Subblocks',{'x':'m','y':'m','z':'m','dx':'m','dy':'m','dz':'m','grade':grade_unit,'variance':grade_unit+'^2','density':'t/m3'})}


def write_omf(path,project,cancel=None):
    import pyarrow as pa
    import jsonschema
    meta=contract(project);model=project.workspace.get('block_model');origin=np.asarray(model.get('grid_origin',model['bounds'][:3]) if model else [0,0,0],dtype=float)
    index={'name':'RAINYMINE exchange','date':datetime.now(timezone.utc).isoformat(),'application':'RAINYMINE','units':'m',
           'coordinate_reference_system':meta['crs_wkt'],'origin':origin.tolist(),'metadata':{'rainymine_exchange':meta},'elements':[]}
    with atomic_destination(path) as temp:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            archive.comment=('Open Mining Format '+OMF_VERSION).encode();writer=OmfWriter(archive)
            if project.collars:
                rows=[asdict(h) for h in project.collars];index['elements'].append({'name':'Collars','geometry':{'type':'PointSet','origin':[0,0,0],'vertices':writer.vertices([[h.x,h.y,h.z] for h in project.collars],origin)},'attributes':writer.attributes(rows,'Vertices',{'x':'m','y':'m','z':'m','depth':'m'})})
            if project.surface:
                rows=[dict(zip('xyz',p)) for p in project.surface];index['elements'].append({'name':'Surface points','geometry':{'type':'PointSet','origin':[0,0,0],'vertices':writer.vertices(project.surface,origin)},'attributes':writer.attributes(rows,'Vertices',{'x':'m','y':'m','z':'m'})})
            for h,depths,points in _traces(project):
                _cancel(cancel)
                if len(points)<2:continue
                segments={'a':list(range(len(points)-1)),'b':list(range(1,len(points)))}
                index['elements'].append({'name':'Hole '+h.hole_id,'geometry':{'type':'LineSet','origin':[0,0,0],'vertices':writer.vertices(points,origin),'segments':writer.array(segments,{k:pa.uint32() for k in segments})},'attributes':writer.attributes([{'depth':d} for d in depths],'Vertices',{'depth':'m'}),'metadata':{'hole_id':h.hole_id,'trajectory_step_m':5}})
            for i,string in enumerate(project.workspace.get('strings',[])):
                _cancel(cancel);points=string['points'];pairs=[[j,j+1] for j in range(len(points)-1)]
                if string.get('closed'):pairs.append([len(points)-1,0])
                index['elements'].append({'name':f'String {i+1} · '+string['name'],'geometry':{'type':'LineSet','origin':[0,0,0],'vertices':writer.vertices(points,origin),'segments':writer.array({k:[p[j] for p in pairs] for j,k in enumerate('ab')},{k:pa.uint32() for k in 'ab'})},'metadata':{'rainymine':{k:v for k,v in string.items() if k!='points'}}})
            for i,mesh in enumerate(project.workspace.get('meshes',[])):
                _cancel(cancel);index['elements'].append({'name':f'Surface {i+1} · '+mesh['name'],'geometry':{'type':'Surface','origin':[0,0,0],'vertices':writer.vertices(mesh['vertices'],origin),'triangles':writer.array({k:[f[j] for f in mesh['faces']] for j,k in enumerate('abc')},{k:pa.uint32() for k in 'abc'})},'metadata':{'rainymine':{k:v for k,v in mesh.items() if k not in ('vertices','faces')}}})
            if model and model.get('blocks'):_cancel(cancel);index['elements'].append(_omf_blocks(model,writer,origin,project.grade_unit))
            schema_path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'assets/formats/omf2.schema.json'
            jsonschema.Draft201909Validator(json.loads(schema_path.read_text(encoding='utf-8'))).validate(index)
            _cancel(cancel);archive.writestr('index.json.gz',gzip.compress(json.dumps(index,ensure_ascii=False,allow_nan=False).encode(),mtime=0))
    return {'format':'OMF '+OMF_VERSION,'elements':len(index['elements']),'bytes':Path(path).stat().st_size,'scope':'geometry, trajectories, block leaves and attributes; full drill database stays .rmine / CSV bundle','schema_commit':SPEC_COMMIT}


def write_geopackage(path,project,cancel=None):
    import fiona
    meta=contract(project);count=0
    def layer(target,name,geometry,properties,records):
        nonlocal count
        with fiona.open(str(target),'w',driver='GPKG',layer=name,crs_wkt=meta['crs_wkt'],schema={'geometry':'3D '+geometry,'properties':properties},SPATIAL_INDEX='NO') as output:
            def checked():
                nonlocal count
                for record in records:
                    _cancel(cancel);count+=1;yield record
            output.writerecords(checked())
    def feature(kind,coordinates,properties):return {'geometry':{'type':kind,'coordinates':coordinates},'properties':properties}
    with atomic_destination(path) as temp:
        # GDAL must create the file rather than opening an empty SQLite placeholder.
        temp.unlink()
        if project.collars:layer(temp,'collars','Point',{'hole_id':'str','depth_m':'float'},(feature('Point',[h.x,h.y,h.z],{'hole_id':h.hole_id,'depth_m':h.depth}) for h in project.collars))
        if project.collars:layer(temp,'drill_traces','LineString',{'hole_id':'str','step_m':'float'},(feature('LineString',points,{'hole_id':h.hole_id,'step_m':5.}) for h,depths,points in _traces(project) if len(points)>=2))
        if project.surface:layer(temp,'surface_points','Point',{'source_id':'int'},(feature('Point',point,{'source_id':i}) for i,point in enumerate(project.surface)))
        strings=project.workspace.get('strings',[])
        for closed,name,kind in [(False,'strings','LineString'),(True,'polygons','Polygon')]:
            selected=[s for s in strings if bool(s.get('closed'))==closed]
            if selected:layer(temp,name,kind,{'name':'str','source_id':'int'},(feature(kind,[s['points']+[s['points'][0]]] if closed else s['points'],{'name':s['name'],'source_id':i}) for i,s in enumerate(selected)))
        meshes=project.workspace.get('meshes',[])
        if meshes:layer(temp,'surface_triangles','Polygon',{'name':'str','mesh_id':'int','face_id':'int'},(feature('Polygon',[[mesh['vertices'][j] for j in face]+[mesh['vertices'][face[0]]]],{'name':mesh['name'],'mesh_id':i,'face_id':j}) for i,mesh in enumerate(meshes) for j,face in enumerate(mesh['faces'])))
        if not temp.exists():
            with fiona.open(str(temp),'w',driver='GPKG',layer='collars',crs_wkt=meta['crs_wkt'],schema={'geometry':'3D Point','properties':{'hole_id':'str'}}):pass
        with sqlite3.connect(temp) as db:
            db.execute('CREATE TABLE rainymine_exchange (id INTEGER PRIMARY KEY, metadata_json TEXT NOT NULL)')
            db.execute('INSERT INTO rainymine_exchange VALUES (1,?)',(json.dumps({**meta,'scope':'GIS only; blocks and drill interval tables are in OMF/CSV, not this GeoPackage'},ensure_ascii=False,allow_nan=False),))
            db.execute("INSERT INTO gpkg_contents(table_name,data_type,identifier,description) VALUES ('rainymine_exchange','attributes','RAINYMINE exchange contract','CRS and units; GIS scope only')")
        _cancel(cancel)
    return {'format':'OGC GeoPackage','features':count,'bytes':Path(path).stat().st_size,'blocks_exported':False}


def read_geopackage(path,layer):
    import fiona
    path=Path(path)
    if path.stat().st_size>256_000_000:raise ValueError('GeoPackage 256MB-аас их; давхаргыг хуваана уу.')
    strings=[];points=[];attributes=[];count=0
    with fiona.open(str(path),layer=layer,enabled_drivers=['GPKG']) as source:
        crs=source.crs_wkt;assumed=False
        def xyz(p):
            nonlocal count,assumed
            count+=1
            if count>200000:raise ValueError('GeoPackage 200000 vertex хязгаартай.')
            if len(p)<3:assumed=True
            result=list(p[:3]) if len(p)>=3 else [*p,0.];finite(*result);return result
        def add(geometry,props,name):
            kind=geometry['type'];coords=geometry['coordinates']
            if kind=='Point':points.append(xyz(coords));attributes.append(props)
            elif kind=='MultiPoint':
                for p in coords:points.append(xyz(p));attributes.append(props)
            elif kind in ('LineString','Polygon'):
                rings=[coords] if kind=='LineString' else coords
                for i,ring in enumerate(rings):
                    values=[xyz(p) for p in ring];closed=kind=='Polygon'
                    if closed and values and values[0]==values[-1]:values.pop()
                    strings.append({'name':name+f' · part {i+1}','points':values,'closed':closed,'attributes':props,'ring_role':('exterior' if i==0 else 'hole') if closed else 'line'})
            elif kind in ('MultiLineString','MultiPolygon'):
                for i,part in enumerate(coords):add({'type':'LineString' if kind=='MultiLineString' else 'Polygon','coordinates':part},props,name+f':{i+1}')
            else:raise ValueError('GeoPackage geometry дэмжихгүй: '+kind)
        for row in source:
            if row['geometry'] is None:raise ValueError('NULL geometry байна; импорт цуцлав.')
            props=dict(row['properties']);add(row['geometry'],props,str(props.get('name') or row['id']))
    return {'strings':strings,'points':points,'point_attributes':attributes,'crs':crs,'z_assumed_zero':assumed,'layer':layer,
            'note':'polygon rings retained separately; hole rings are marked and must not be treated as ore solids'}


def write_exchange_bundle(path,project,cancel=None):
    from .data_tools import SCHEMAS
    from .geometry import write_dxf,write_obj
    from .exchange import write_stl
    meta=contract(project);files={};manifest={**meta,'files':{},'csv_null_row_index':'zero-based data rows, excluding header; null_rows distinguishes NULL from empty text','geometry_limit':'DXF/OBJ/STL carry geometry; scientific attributes are CSV/metadata only'}
    def add(name,data):files[name]=data;manifest['files'][name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    def table(name,rows,fields=None):
        fields=list(fields or sorted(set().union(*(r.keys() for r in rows))))
        output=io.StringIO(newline='');writer=csv.DictWriter(output,fields);writer.writeheader()
        for row in rows:
            _cancel(cancel);writer.writerow({k:('' if row.get(k) is None else json.dumps(row[k],ensure_ascii=False,allow_nan=False) if isinstance(row[k],(dict,list,tuple)) else format(row[k],'.17g') if isinstance(row[k],float) else row[k]) for k in fields})
        add(name,output.getvalue().encode('utf-8-sig'))
        manifest['files'][name]['columns']={k:{'types':sorted({type(r[k]).__name__ for r in rows if r.get(k) is not None}),'nullable':any(r.get(k) is None for r in rows),'null_rows':[i for i,r in enumerate(rows) if r.get(k) is None]} for k in fields}
    for kind in ('collars','surveys','assays','lithology','structure','geotech','surface'):
        rows=[dict(zip('xyz',r)) if kind=='surface' else asdict(r) for r in getattr(project,kind,[])];table(kind+'.csv',rows,SCHEMAS[kind])
    model=project.workspace.get('block_model')
    if model and model.get('blocks'):table('blocks.csv',[{'rainymine_row_id':i,**b} for i,b in enumerate(model['blocks'])])
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);workspace=project.workspace
        if workspace.get('strings') or workspace.get('meshes'):
            write_dxf(root/'geometry.dxf',workspace);add('geometry.dxf',(root/'geometry.dxf').read_bytes())
        manifest['meshes']=[]
        for i,mesh in enumerate(workspace.get('meshes',[])):
            _cancel(cancel);name=f'mesh-{i+1:04}'
            for ext,writer in [('obj',write_obj),('stl',write_stl)]:writer(root/(name+'.'+ext),mesh);add(name+'.'+ext,(root/(name+'.'+ext)).read_bytes())
            manifest['meshes'].append({'file_prefix':name,'name':mesh['name'],'metadata':{k:v for k,v in mesh.items() if k not in ('vertices','faces')}})
    manifest['strings_metadata']=[{k:v for k,v in s.items() if k!='points'} for s in project.workspace.get('strings',[])]
    with atomic_destination(path) as temp:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for name,data in files.items():_cancel(cancel);archive.writestr(name,data)
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,allow_nan=False,indent=2).encode())
        _cancel(cancel)
    return {'format':'CSV/CAD exchange bundle','files':len(files)+1,'bytes':Path(path).stat().st_size}
