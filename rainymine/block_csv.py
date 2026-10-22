"""Validated world-centre CSV exchange, with explicit rotated parent/leaf geometry."""
import csv
import hashlib
import io
import math
from pathlib import Path

KEYS = ('x', 'y', 'z', 'dx', 'dy', 'dz', 'grade')


def read_block_csv(path, mapping, crs, grade_unit, maximum=50000, cancel=None, geometry=None, skip_rows=0, attributes=None):
    from pyproj import CRS
    if type(maximum) is not int or not 1 <= maximum <= 50000:
        raise ValueError('Maximum 1…50000 байна.')
    if type(skip_rows) is not int or not 0 <= skip_rows <= 3:
        raise ValueError('Skip rows 0…3 байна; зөвхөн header-ийн дараах metadata мөр.')
    reference = CRS.from_user_input(crs)
    if not reference.is_projected or any(abs(a.unit_conversion_factor-1) > 1e-9 for a in reference.axis_info[:2]):
        raise ValueError('Projected metre CRS шаардлагатай.')
    if grade_unit not in ('%','g/t','ppm'):
        raise ValueError('Агуулгын нэгж шаардлагатай.')
    path = Path(path)
    if path.stat().st_size > 32_000_000:
        raise ValueError('CSV 32 MB-аас их байна.')
    raw = path.read_bytes()
    if len(raw) > 32_000_000:
        raise ValueError('CSV 32 MB-аас их байна.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    headers = reader.fieldnames or []
    required = [mapping.get(k) for k in KEYS]
    if len(headers) != len(set(headers)) or not all(required) or len(set(required)) != len(required) or any(k not in headers for k in required):
        raise ValueError('Багана давхардсан / mapping дутуу байна.')
    attributes=attributes or {}
    if not isinstance(attributes,dict) or len(attributes)>64:raise ValueError('Нэмэлт багана 64-өөс их / mapping буруу.')
    for name,spec in attributes.items():
        if not isinstance(name,str) or not name or len(name)>120 or not isinstance(spec,dict) or spec.get('column') not in headers or spec.get('kind') not in ('number','text','boolean') or not isinstance(spec.get('unit',''),str):
            raise ValueError('Нэмэлт баганын mapping буруу.')
        if name=='density' and (spec['kind']!='number' or spec.get('unit') not in ('t/m3','t/m³')):raise ValueError('Нягт number, t/m3 байна.')
        if name=='domain' and spec['kind']!='text':raise ValueError('Домэйн text байна.')
    metadata_rows = []
    for _ in range(skip_rows):
        try:
            metadata=next(reader)
            metadata_rows.append({'columns':[metadata.get(h) for h in headers],'extra':metadata.get(None,[])})
        except StopIteration as exc: raise ValueError('Metadata мөр дутуу.') from exc
    # Explicit geometry uses RAINYMINE ENU basis, never guessed vendor Euler angles.
    grid = _grid_parameters(geometry) if geometry is not None else None
    blocks = []
    for line, row in enumerate(reader, 2+skip_rows):
        if cancel and cancel():
            raise RuntimeError('Импортыг цуцаллаа.')
        if len(blocks) >= maximum:
            raise ValueError('Desktop блокийн хязгаар хэтэрсэн.')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Мөр {line}: баганын тоо зөрсөн.')
        expected_angles = grid[2] if grid is not None else [90.,0.,0.]
        for key, expected in zip(('grid_azimuth','grid_dip','grid_roll'),expected_angles):
            if key in row and row[key].strip() and not math.isclose(float(row[key]),expected,abs_tol=1e-9):
                raise ValueError('CSV rotation metadata нь сонгосон RAINYMINE өнцөгтэй зөрсөн.')
        if grid is not None:
            for axis,key in enumerate(('origin_x','origin_y','origin_z')):
                if key in row and row[key].strip() and not math.isclose(float(row[key]),grid[0][axis],rel_tol=0,abs_tol=1e-6):
                    raise ValueError('CSV origin metadata зөрсөн.')
        block = {}
        for key in KEYS:
            value = row[mapping[key]].strip()
            if key == 'grade' and value.upper() in ('', 'NULL', 'NONE', 'NAN'):
                block[key] = None
                continue
            try:
                number = float(value)
            except ValueError as exc:
                raise ValueError(f'Мөр {line}: {key} тоон утга биш.') from exc
            if not math.isfinite(number) or (key in ('x','y','z') and abs(number)>1e9) or (key in ('dx','dy','dz') and number <= 0) or (key == 'grade' and number < 0):
                raise ValueError(f'Мөр {line}: {key} утга буруу.')
            block[key] = number
        if grade_unit=='%' and block['grade'] is not None and block['grade']>100:raise ValueError(f'Мөр {line}: хувь агуулга 100-аас их.')
        extra={}
        for name,spec in attributes.items():
            token=row[spec['column']]
            value=_attribute(token,spec['kind'])
            if name=='density' and value is not None and value<=0:raise ValueError(f'Мөр {line}: нягт эерэг байна.')
            if name in ('density','domain'):block[name]=value
            else:extra[name]=value
        if extra:block['attributes']=extra
        block.update(variance=None, status='imported' if block['grade'] is not None else 'unestimated')
        blocks.append(block)
    if not blocks:
        raise ValueError('Блокийн CSV хоосон.')
    if grid is not None:
        low, high, size, angles, leaf_count = _assign_leaves(blocks, grid, cancel)
    else:
        size = [blocks[0][k] for k in ('dx','dy','dz')]
        low = [min(b[k]-size[a]/2 for b in blocks) for a,k in enumerate(('x','y','z'))]
        occupied = set()
        for block in blocks:
            index = []
            for axis, (key, dim) in enumerate(zip(('x','y','z'), ('dx','dy','dz'))):
                if not math.isclose(block[dim], size[axis], rel_tol=1e-9, abs_tol=1e-8):
                    raise ValueError('Ижил хэмжээтэй parent blocks шаардлагатай; sub-block энэ импортод дэмжихгүй.')
                position = (block[key]-low[axis])/size[axis]-.5
                integer = round(position)
                if not math.isclose(position, integer, rel_tol=0, abs_tol=1e-6):
                    raise ValueError('Блокийн төв regular world-axis торонд таарахгүй. Эргэлт / давхцлыг шалгана уу.')
                index.append(integer)
            if tuple(index) in occupied:
                raise ValueError('Давхардсан блокийн төв байна.')
            occupied.add(tuple(index))
            block.update(zip(('i','j','k'), index))
        high = [max(b[k]+size[a]/2 for b in blocks) for a,k in enumerate(('x','y','z'))]
        angles = [90.,0.,0.]
        leaf_count = 0
    report = {'tool':'block CSV import','source':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
              'crs':reference.to_string(),'grade_unit':grade_unit,'mapping':dict(mapping),'blocks':len(blocks),
              'null_grades':sum(b['grade'] is None for b in blocks),'extra_columns': [h for h in headers if h not in required and h not in {s['column'] for s in attributes.values()}],
              'preserved_attributes':list(attributes),
              'geometry':'explicit rotated parent/leaf grid' if grid is not None else 'world-axis regular parents',
              'grid_angles':angles,'grid_origin':low,'parent_size':size,'subblocks':leaf_count,
              'skipped_metadata_rows':skip_rows, 'metadata_rows_uninterpreted':metadata_rows,
              'classification':'UNCLASSIFIED; source classification not imported'}
    model = {'blocks':blocks,'bounds':low+high,'size':size,'grid_origin':low,'grid_angles':angles,
             'attribute_schema':attributes,'params':{},'classification':'UNCLASSIFIED','support':'imported block grades; source support unverified',
             'import_report':report}
    if geometry and geometry.get('source_orientation'):
        model['source_orientation']=geometry['source_orientation']
        report['source_orientation']=geometry['source_orientation']
    return model, report


def _grid_parameters(geometry):
    import numpy as np
    from .spatial import search_basis
    origin=np.asarray(geometry['origin'],dtype=float)
    size=np.asarray(geometry['parent_size'],dtype=float)
    angles=np.asarray(geometry['angles'],dtype=float)
    if any(a.shape!=(3,) or not np.isfinite(a).all() for a in (origin,size,angles)) or np.any(size<1e-6) or np.any(size>1e7) or np.any(abs(origin)>1e9):
        raise ValueError('Origin / parent size / angles буруу.')
    return origin,size,angles.tolist(),search_basis(*angles)


def _assign_leaves(blocks, grid, cancel):
    """Validate non-overlapping freeform leaves within explicit rotated parents.

    Parent buckets bound comparisons at 512 leaves each. Source world coordinates
    and dimensions are preserved; tolerances affect validation only.
    """
    import numpy as np
    origin,size,angles,basis=grid
    groups={};counts=np.zeros(3,dtype=np.int64);leaf_count=0
    for block in blocks:
        if cancel and cancel():raise RuntimeError('Импортыг цуцаллаа.')
        center=(np.array([block[k] for k in 'xyz'])-origin)@basis
        dims=np.array([block[k] for k in ('dx','dy','dz')])
        if np.any(dims/size<1e-5):raise ValueError('Leaf хэмжээ parent-ийн 1e-5-аас бага; validation нарийвчлал хүрэхгүй.')
        low=(center-dims/2)/size;high=(center+dims/2)/size
        if not np.isfinite(low).all() or not np.isfinite(high).all() or np.any(abs(low)>=2**31):
            raise ValueError('Grid координат хэт их.')
        nearest=np.round(low)
        low=np.where(abs(low-nearest)<=1e-7,nearest,low)
        parent=np.floor(low).astype(np.int64)
        if np.any(parent<0) or np.any(parent>=2**31) or np.any(high>parent+1+1e-7) or np.any(high<=low):
            raise ValueError('Leaf нь parent boundary давсан / origin-оос доогуур / grid хэт их.')
        key=tuple(parent.tolist());siblings=groups.setdefault(key,[])
        if len(siblings)>=512:raise ValueError('Нэг parent-д 512-оос олон leaf байна.')
        if siblings:
            old=np.asarray(siblings)
            if np.any(np.all(np.minimum(high,old[:,1])-np.maximum(low,old[:,0])>1e-7,axis=1)):
                raise ValueError('Давхардсан / огтлолцсон parent буюу sub-block байна.')
        siblings.append((low,high));counts=np.maximum(counts,parent+1)
        is_leaf=not np.allclose(dims,size,rtol=1e-9,atol=1e-8)
        leaf_count+=int(is_leaf)
        block.update(zip(('i','j','k'),key))
        block.update(parent_id=':'.join(map(str,key)),imported_subblock=bool(is_leaf))
    # Bounds follow the existing local-grid coordinates anchored at world origin.
    return origin.tolist(),(origin+counts*size).tolist(),size.tolist(),angles,leaf_count


def _attribute(token,kind):
    if token.strip().upper() in ('NULL','NONE','NAN'):return None
    if kind=='text':return token
    if not token.strip():return None
    if kind=='boolean':
        if token.strip().lower() not in ('true','false','1','0'):raise ValueError('Boolean нь true/false/1/0 байна.')
        return token.strip().lower() in ('true','1')
    value=float(token)
    if not math.isfinite(value):raise ValueError('Нэмэлт тоон утга finite байна.')
    return value
