"""Strict exchange reader for unrotated, regular parent-block CSV models."""
import csv
import hashlib
import io
import math
from pathlib import Path

KEYS = ('x', 'y', 'z', 'dx', 'dy', 'dz', 'grade')


def read_block_csv(path, mapping, crs, grade_unit, maximum=50000, cancel=None):
    from pyproj import CRS
    if type(maximum) is not int or not 1 <= maximum <= 50000:
        raise ValueError('Maximum 1…50000 байна.')
    reference = CRS.from_user_input(crs)
    if not reference.is_projected or any(abs(a.unit_conversion_factor-1) > 1e-9 for a in reference.axis_info[:2]):
        raise ValueError('Projected metre CRS шаардлагатай.')
    if not str(grade_unit).strip():
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
    blocks = []
    for line, row in enumerate(reader, 2):
        if cancel and cancel():
            raise RuntimeError('Импортыг цуцаллаа.')
        if len(blocks) >= maximum:
            raise ValueError('Desktop блокийн хязгаар хэтэрсэн.')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Мөр {line}: баганын тоо зөрсөн.')
        for key, expected in (('grid_azimuth',90),('grid_dip',0),('grid_roll',0)):
            if key in row and row[key].strip() and not math.isclose(float(row[key]),expected,abs_tol=1e-9):
                raise ValueError('Эргэлттэй CSV энэ импортод дэмжихгүй.')
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
        block.update(variance=None, status='imported' if block['grade'] is not None else 'unestimated')
        blocks.append(block)
    if not blocks:
        raise ValueError('Блокийн CSV хоосон.')
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
    report = {'tool':'block CSV import','source':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
              'crs':reference.to_string(),'grade_unit':grade_unit,'mapping':dict(mapping),'blocks':len(blocks),
              'null_grades':sum(b['grade'] is None for b in blocks),'extra_columns': [h for h in headers if h not in required],
              'geometry':'world-axis regular parent blocks; centres in metres',
              'classification':'UNCLASSIFIED; source classification not imported'}
    model = {'blocks':blocks,'bounds':low+high,'size':size,'grid_origin':low,'grid_angles':[90.,0.,0.],
             'params':{},'classification':'UNCLASSIFIED','support':'imported block grades; source support unverified',
             'import_report':report}
    return model, report
