"""Documented external geometry readers. CRS is reported, never guessed or relabelled."""
import csv
import io
import math
from pathlib import Path
import numpy as np
from .core import finite,atomic_write


def read_surpac(path):
    path=Path(path)
    if path.stat().st_size>32_000_000:raise ValueError('STR 32 MB-аас их; хувааж импортлоно уу.')
    text=path.read_text(encoding='utf-8-sig');records=list(csv.reader(io.StringIO(text)))
    if len(records)<3:raise ValueError('STR хоёр header ба point records шаардлагатай.')
    result=[];single=[];all_points=[];current=[];descriptions=[];number=None;ended=False
    def flush():
        if current:
            closed=len(current)>2 and current[0]==current[-1]
            points=current[:-1] if closed else list(current)
            if len(points)>=2:result.append({'name':f'{path.stem} · {number} · {len(result)+1}','points':points,'closed':closed,
                                             'surpac_number':number,'descriptions':list(descriptions)})
            else:single.extend(points)
        current.clear();descriptions.clear()
    for line,row in enumerate(records[2:],3):
        if not row or not any(v.strip() for v in row):continue
        try:
            if len(row)<4:raise ValueError('Дөрвөн багана шаардлагатай.')
            code=int(row[0]);y,x,z=map(float,row[1:4]);finite(x,y,z)
            if code==0:
                flush();number=None
                if len(row)>4 and row[4].strip().upper()=='END':ended=True;break
                continue
            if not 1<=code<=32000:raise ValueError('String number 1…32000 байна.')
            if number is not None and number!=code:flush()
            number=code;point=[x,y,z];current.append(point);all_points.append(point);descriptions.append(row[4:])
            if len(all_points)>200000:raise ValueError('STR point хязгаар хэтэрсэн.')
        except (ValueError,OverflowError) as exc:raise ValueError(f'STR мөр {line}: {exc}') from exc
    flush()
    if not ended:raise ValueError('STR END record алга; тасарсан файл байж болзошгүй.')
    return {'strings':result,'isolated_points':single,'source_points':all_points,'header':records[:2],
            'crs':None,'coordinate_order':'Y,X,Z in file; X,Y,Z internally'}


def write_surpac(path,strings):
    output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow([Path(path).stem,'','','RAINYMINE']);writer.writerow([0]*7)
    for i,string in enumerate(strings,1):
        code=int(string.get('surpac_number',i))
        if not 1<=code<=32000:raise ValueError('Surpac string number буруу.')
        points=list(string['points'])
        if string.get('closed'):points.append(points[0])
        descriptions=string.get('descriptions',[])
        for j,point in enumerate(points):
            finite(*point);writer.writerow([code,format(point[1],'.12g'),format(point[0],'.12g'),format(point[2],'.12g'),*(descriptions[j] if j<len(descriptions) else [])])
        writer.writerow([0,0,0,0])
    writer.writerow([0,0,0,0,'END']);atomic_write(path,output.getvalue())


def read_surpac_dtm(path):
    """ASCII TRISOLATION only; binary DTMs and unverified checksums are rejected."""
    path=Path(path)
    if path.stat().st_size>32_000_000:raise ValueError('DTM хэт том.')
    try:rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    except UnicodeError as exc:raise ValueError('Binary Surpac DTM энэ reader-т дэмжигдэхгүй.') from exc
    if not rows or not rows[0]:raise ValueError('DTM header алга.')
    referenced=rows[0][0].strip()
    if Path(referenced).name!=referenced or '\\' in referenced:raise ValueError('DTM STR reference нь ижил хавтасны basename байна.')
    if len(rows[0])>1 and rows[0][1].strip():raise ValueError('DTM checksum-ийг баталгаажуулах decoder дутуу; checksum-гүй ASCII export хэрэглэнэ үү.')
    vertices=read_surpac(path.parent/referenced)['source_points'];faces=[];active=False
    for row in rows[1:]:
        if not row:continue
        tag=row[0].strip().upper()
        if tag=='TRISOLATION':active=True;continue
        if tag in ('OBJECT','END'):active=False;continue
        if not active:continue
        if len(row)<4:raise ValueError('DTM triangle record буруу.')
        face=[int(v.strip())-1 for v in row[1:4]]
        if len(set(face))!=3 or any(v<0 or v>=len(vertices) for v in face):raise ValueError('DTM vertex reference буруу.')
        faces.append(face)
    if not faces:raise ValueError('ASCII TRISOLATION triangles алга.')
    return {'name':path.stem,'vertices':vertices,'faces':faces,'role':'imported_dtm'}


def read_shapefile(path):
    import shapefile
    from pyproj import CRS
    path=Path(path);strings=[];points=[];attributes=[];point_count=0
    prj=path.with_suffix('.prj');crs=CRS.from_wkt(prj.read_text(encoding='utf-8')).to_string() if prj.exists() else None
    with shapefile.Reader(str(path),encoding='utf-8') as reader:
        fields=[r[0] for r in reader.fields[1:]]
        for i,record in enumerate(reader.iterShapeRecords()):
            shape=record.shape;attrs={key:(value.isoformat() if hasattr(value,'isoformat') else value) for key,value in zip(fields,list(record.record))};attributes.append(attrs)
            z=list(getattr(shape,'z',[0.]*len(shape.points)))
            xyz=[[float(p[0]),float(p[1]),float(z[j])] for j,p in enumerate(shape.points)]
            if not np.isfinite(xyz).all():raise ValueError('SHP finite бус координат.')
            if shape.shapeType in (shapefile.POINT,shapefile.POINTZ,shapefile.MULTIPOINT,shapefile.MULTIPOINTZ):points.extend(xyz)
            elif shape.shapeType in (shapefile.POLYLINE,shapefile.POLYLINEZ,shapefile.POLYGON,shapefile.POLYGONZ):
                parts=list(shape.parts)+[len(xyz)]
                for part,(start,end) in enumerate(zip(parts,parts[1:])):
                    part_points=xyz[start:end];closed=shape.shapeType in (5,15)
                    if closed and part_points and part_points[0]==part_points[-1]:part_points=part_points[:-1]
                    if len(part_points)<(3 if closed else 2):raise ValueError('SHP part-д цэг хүрэлцэхгүй.')
                    strings.append({'name':f'{path.stem} · {i+1}:{part+1}','points':part_points,'closed':closed,'attributes':attrs,'source_feature':i,'source_part':part})
            elif shape.shapeType!=shapefile.NULL:raise ValueError('SHP geometry type дэмжигдээгүй: '+str(shape.shapeType))
            point_count+=len(xyz)
            if point_count>200000:raise ValueError('SHP point хязгаар хэтэрсэн.')
    return {'strings':strings,'points':points,'attributes':attributes,'crs':crs,'z_assumed_zero':reader.shapeType in (1,3,5,8)}


def las_preview(path,maximum=250000,bounds=None,classes=None,chunk_size=250000,cancel=None):
    """Bounded deterministic stride preview; original LAS/LAZ remains untouched.

    Selection preserves source point indices, intensity and classification.
    This is an explicitly sampled preview, not a lossy replacement of source data.
    """
    import laspy
    if type(maximum) is not int or not 1<=maximum<=1000000:raise ValueError('Preview limit 1…1000000 байна.')
    if type(chunk_size) is not int or not 1<=chunk_size<=1000000:raise ValueError('Chunk хэмжээ буруу.')
    b=None if bounds is None else np.asarray(bounds,dtype=float)
    if b is not None and (b.shape!=(6,) or not np.isfinite(b).all() or np.any(b[:3]>b[3:])):raise ValueError('LAS bounds буруу.')
    pieces=[];indices=[];intensities=[];labels=[];offset=0;matched=0
    with laspy.open(path) as reader:
        count=reader.header.point_count;stride=max(1,math.ceil(count/maximum));crs=reader.header.parse_crs()
        for chunk in reader.chunk_iterator(chunk_size):
            if cancel and cancel():raise RuntimeError('LAS preview cancelled.')
            xyz=np.column_stack((chunk.x,chunk.y,chunk.z));ids=np.arange(offset,offset+len(chunk),dtype=np.int64);offset+=len(chunk)
            mask=np.isfinite(xyz).all(axis=1)
            if b is not None:mask&=np.all((xyz>=b[:3])&(xyz<=b[3:]),axis=1)
            if classes is not None:mask&=np.isin(np.asarray(chunk.classification),classes)
            matched+=int(mask.sum());mask&=ids%stride==0
            pieces.append(xyz[mask]);indices.append(ids[mask]);intensities.append(np.asarray(chunk.intensity)[mask]);labels.append(np.asarray(chunk.classification)[mask])
        metadata={'source_points':count,'matched_before_sampling':matched,'stride':stride,'crs':crs.to_string() if crs else None,
                  'dimensions':list(reader.header.point_format.dimension_names),'point_format':reader.header.point_format.id}
    return {'xyz':np.concatenate(pieces) if pieces else np.empty((0,3)),
            'source_index':np.concatenate(indices) if indices else np.empty(0,dtype=np.int64),
            'intensity':np.concatenate(intensities) if intensities else np.empty(0),
            'classification':np.concatenate(labels) if labels else np.empty(0),**metadata}


def read_dem(path,maximum_side=256):
    import rasterio
    from rasterio.enums import Resampling
    from affine import Affine
    from pyproj import CRS
    if type(maximum_side) is not int or not 2<=maximum_side<=400:raise ValueError('DEM preview side 2…400 байна.')
    with rasterio.open(path) as source:
        crs=CRS.from_user_input(source.crs) if source.crs else None
        if crs is None or not crs.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in crs.axis_info[:2]):
            raise ValueError('DEM projected metre CRS шаардлагатай; эхлээд reproject хийнэ үү.')
        factor=max(1,math.ceil(max(source.width,source.height)/maximum_side));height=math.ceil(source.height/factor);width=math.ceil(source.width/factor)
        if min(width,height)<2:raise ValueError('DEM 2×2-оос бага.')
        band=source.read(1,out_shape=(height,width),masked=True,resampling=Resampling.nearest)
        transform=source.transform*Affine.scale(source.width/width,source.height/height)
        rows,columns=np.indices((height,width));x=transform.a*(columns+.5)+transform.b*(rows+.5)+transform.c;y=transform.d*(columns+.5)+transform.e*(rows+.5)+transform.f
        valid=~np.ma.getmaskarray(band)&np.isfinite(np.asarray(band));lookup=np.full((height,width),-1,dtype=int);lookup[valid]=np.arange(valid.sum())
        vertices=np.column_stack((x[valid],y[valid],np.asarray(band)[valid])).tolist();faces=[]
        for row in range(height-1):
            for col in range(width-1):
                a,b,c,d=lookup[row,col],lookup[row,col+1],lookup[row+1,col],lookup[row+1,col+1]
                if min(a,b,c,d)>=0:faces.extend([[int(a),int(c),int(b)],[int(b),int(c),int(d)]])
        if not faces:raise ValueError('DEM valid surface алга.')
        if transform.a*transform.e-transform.b*transform.d>0:faces=[list(reversed(f)) for f in faces]
        if source.units[0] and source.units[0].lower() not in ('m','metre','meter','metres','meters'):raise ValueError('DEM vertical unit метр биш.')
        return {'name':Path(path).stem+' · DEM','vertices':vertices,'faces':faces,'role':'dem'}, {'crs':crs.to_string(),'source_size':[source.width,source.height],'preview_size':[width,height],'resampling':'nearest; nodata cells omitted','vertical_unit':source.units[0]}


def filter_las(source,destination,bounds=None,classes=None,cancel=None):
    """Atomic streamed LAS/LAZ subset, preserving raw point dimensions and CRS.

    Waveform formats are rejected: copying waveform offsets without their packet
    storage would corrupt those records. Input is never overwritten.
    """
    import laspy
    import os,tempfile
    source=Path(source);destination=Path(destination)
    if source.resolve()==destination.resolve():raise ValueError('Эх LAS/LAZ файлыг дарж бичихгүй; өөр output сонгоно уу.')
    if destination.suffix.lower() not in ('.las','.laz'):raise ValueError('Output LAS эсвэл LAZ байна.')
    box=None if bounds is None else np.asarray(bounds,dtype=float)
    if box is not None and (box.shape!=(6,) or not np.isfinite(box).all() or np.any(box[:3]>box[3:])):raise ValueError('LAS filter bounds буруу.')
    fd,temp=tempfile.mkstemp(prefix='.rainymine-las-',suffix=destination.suffix,dir=destination.parent);os.close(fd);written=0
    try:
        with laspy.open(source) as reader:
            if reader.header.point_format.id in (4,5,9,10):raise ValueError('Waveform point format packet copy хараахан дэмжихгүй.')
            total=reader.header.point_count;crs=reader.header.parse_crs()
            with laspy.open(temp,mode='w',header=reader.header.copy(),do_compress=destination.suffix.lower()=='.laz') as writer:
                for points in reader.chunk_iterator(250000):
                    if cancel and cancel():raise RuntimeError('LAS export cancelled; previous output unchanged.')
                    xyz=np.column_stack((points.x,points.y,points.z));mask=np.isfinite(xyz).all(axis=1)
                    if box is not None:mask&=np.all((xyz>=box[:3])&(xyz<=box[3:]),axis=1)
                    if classes is not None:mask&=np.isin(np.asarray(points.classification),classes)
                    writer.write_points(points[mask]);written+=int(mask.sum())
                if reader.evlrs is not None:writer.write_evlrs(reader.evlrs)
        with open(temp,'r+b') as output:os.fsync(output.fileno())
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'source_points':total,'written_points':written,'crs':crs.to_string() if crs else None,'raw_dimensions_preserved':True}
