"""Bounded CSV -> SQLite block store; supports varying axis-aligned leaf sizes.

No implicit regular-grid indexing or rotated geometry is invented on import.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile


def import_disk_csv(source,destination,mapping,crs,grade_unit,maximum=20_000_000,
                    cancel=None,progress=None,batch_size=32768):
    from pyproj import CRS
    reference=CRS.from_user_input(crs)
    if not reference.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in reference.axis_info[:2]):raise ValueError('Projected metre CRS required')
    if grade_unit not in ('%','g/t','ppm') or type(maximum)!=int or not 1<=maximum<=20_000_000 or type(batch_size)!=int or not 1<=batch_size<=65536:raise ValueError('Invalid import limits / units')
    required=('x','y','z','dx','dy','dz','grade')
    if not all(mapping.get(k) for k in required) or len(set(mapping.values()))!=len(mapping):raise ValueError('Distinct mapped columns required')
    if set(mapping)-set(required)-{'density','domain'}:raise ValueError('Unknown mapped field')
    source,destination=Path(source),Path(destination)
    if destination.exists():raise ValueError('Destination already exists; choose a new store')
    if source.resolve()==destination.resolve():raise ValueError('Source and destination must differ')
    fd,temp=tempfile.mkstemp(dir=destination.parent,prefix='.rainymine-import-');os.close(fd)
    db=sqlite3.connect(temp);digest=hashlib.sha256();count=0;unknown=0
    try:
        db.executescript('''PRAGMA application_id=1380795458;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE blocks(id INTEGER PRIMARY KEY,x REAL,y REAL,z REAL,dx REAL,dy REAL,dz REAL,grade REAL,density REAL,domain TEXT);
        CREATE TABLE revisions(id INTEGER PRIMARY KEY,label TEXT NOT NULL);
        CREATE TABLE changes(revision INTEGER,block_id INTEGER,og REAL,od REAL,oz TEXT,ng REAL,nd REAL,nz TEXT,PRIMARY KEY(revision,block_id));''')
        total_bytes=source.stat().st_size
        with source.open('rb') as raw:
            def lines():
                first=True
                while True:
                    line=raw.readline(1_048_577)
                    if not line:break
                    if len(line)>1_048_576:raise ValueError('CSV physical line exceeds 1 MiB')
                    digest.update(line)
                    yield line.decode('utf-8-sig' if first else 'utf-8')
                    first=False
            reader=csv.DictReader(lines());headers=reader.fieldnames or []
            if len(headers)>256 or len(headers)!=len(set(headers)) or not set(mapping.values())<=set(headers):raise ValueError('Missing/duplicate CSV columns')
            for key in ('grid_azimuth','grid_dip','grid_roll'):
                if key in headers:raise ValueError('Rotation metadata present: disk CSV import only accepts explicitly unrotated geometry')
            batch=[]
            for row in reader:
                if count%batch_size==0:
                    if cancel and cancel():raise RuntimeError('Disk CSV import cancelled')
                    if progress:progress(raw.tell(),total_bytes)
                if count>=maximum:raise ValueError('Disk import block limit exceeded')
                if None in row or any(v is None for v in row.values()):raise ValueError(f'CSV row {reader.line_num}: column count mismatch')
                values={}
                for key in required+('density',):
                    value=row[mapping[key]].strip() if key in mapping else ''
                    if key in ('grade','density') and value.upper() in ('','NULL','NONE','NAN'):
                        values[key]=None;continue
                    try:value=float(value)
                    except ValueError:raise ValueError(f'CSV row {reader.line_num}: invalid {key}') from None
                    if not math.isfinite(value) or (key in ('dx','dy','dz','density') and value<=0) or (key=='grade' and (value<0 or (grade_unit=='%' and value>100))):raise ValueError(f'CSV row {reader.line_num}: invalid {key}')
                    if key in ('x','y','z') and abs(value)>1e9:raise ValueError('Block coordinate exceeds supported metric range')
                    if key in ('dx','dy','dz') and not 1e-6<=value<=1e7:raise ValueError('Block dimensions outside supported metric range')
                    values[key]=value
                domain=row[mapping['domain']] if 'domain' in mapping else None
                if domain is not None and len(domain)>200:raise ValueError('Domain label exceeds 200 characters')
                batch.append((count,*[values[k] for k in ('x','y','z','dx','dy','dz','grade','density')],domain))
                unknown+=values['grade'] is None;count+=1
                if len(batch)>=batch_size:
                    db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?)',batch);batch=[];db.commit()
            if batch:db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?)',batch)
        if not count:raise ValueError('No block records')
        if cancel and cancel():raise RuntimeError('Disk CSV import cancelled')
        meta={'version':1,'origin':[0,0,0],'grid_kind':'unstructured_axis_aligned','crs':reference.to_string(),
              'grade_unit':grade_unit,'support':'axis-aligned imported block centres; overlap not certified',
              'classification':'UNCLASSIFIED','source_sha256':digest.hexdigest(),'source_name':source.name,
              'mapping':mapping,'blocks':count}
        db.executemany('INSERT INTO metadata VALUES(?,?)',[('model',json.dumps(meta)),('cursor','0')]);db.commit();db.close();db=None
        with open(temp,'r+b') as stream:os.fsync(stream.fileno())
        if destination.exists():raise ValueError('Destination was created by another operation')
        os.rename(temp,destination)
        if progress:progress(total_bytes,total_bytes)
        return {'path':str(destination),'blocks':count,'unestimated_blocks':unknown,'source_sha256':digest.hexdigest(),
                'maximum_batch_rows':batch_size,'regular_grid_verified':False,'geometry_overlap_verified':False}
    finally:
        if db is not None:db.close()
        if os.path.exists(temp):os.unlink(temp)
