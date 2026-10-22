"""Disk-backed regular block grids, atomic IDW runs and persistent bounded undo.

Centre-support IDW only. This store is explicitly linked from .rmine, never
silently materialised into its limited in-memory block_model.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import numpy as np
from scipy.spatial import cKDTree
from .core import finite


class DiskModel:
    def __init__(self,path):
        self.path=Path(path)
        if not self.path.is_file():raise ValueError('Block store does not exist')
        self.db=sqlite3.connect(self.path)
        try:
            if self.db.execute('PRAGMA application_id').fetchone()[0]!=0x524d4442:raise ValueError('Not a RAINYMINE block store')
            row=self.db.execute('SELECT value FROM metadata WHERE key="model"').fetchone()
            if not row or not isinstance(row[0],str) or len(row[0])>1048576:raise ValueError('Invalid block-store metadata')
            self.meta=json.loads(row[0])
            if not isinstance(self.meta,dict) or self.meta.get('version')!=1:raise ValueError('Unsupported block-store schema')
            if self.meta.get('grade_unit') not in ('%','ppm','g/t') or not isinstance(self.meta.get('crs'),str):raise ValueError('Invalid block-store units/CRS')
        except Exception:self.db.close();raise

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):self.db.close()

    @classmethod
    def create(cls,path,origin,counts,size,crs,grade_unit,density=None,cancel=None):
        finite(*origin,*size)
        if len(origin)!=3 or len(size)!=3 or len(counts)!=3 or any(type(n)!=int or n<=0 for n in counts) or math.prod(counts)>10_000_000 or min(size)<=0:raise ValueError('Invalid grid; maximum 10 million blocks')
        if density is not None:
            finite(density)
            if density<=0:raise ValueError('Density must be positive')
        from pyproj import CRS
        reference=CRS.from_user_input(crs)
        if not reference.is_projected or any(abs(a.unit_conversion_factor-1)>1e-9 for a in reference.axis_info[:2]):raise ValueError('Projected metre CRS required')
        if grade_unit not in ('%','g/t','ppm'):raise ValueError('Invalid grade unit')
        path=Path(path);fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.rainymine-db-');os.close(fd)
        db=sqlite3.connect(temp)
        try:
            db.executescript('''PRAGMA application_id=1380795458;
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE blocks(id INTEGER PRIMARY KEY,x REAL,y REAL,z REAL,dx REAL,dy REAL,dz REAL,grade REAL,density REAL,domain TEXT);
            CREATE TABLE revisions(id INTEGER PRIMARY KEY,label TEXT NOT NULL);
            CREATE TABLE changes(revision INTEGER,block_id INTEGER,og REAL,od REAL,oz TEXT,ng REAL,nd REAL,nz TEXT,PRIMARY KEY(revision,block_id));''')
            meta={'version':1,'origin':list(origin),'counts':list(counts),'size':list(size),'crs':reference.to_string(),'grade_unit':grade_unit,'support':'axis-aligned block centres','classification':'UNCLASSIFIED'}
            db.executemany('INSERT INTO metadata VALUES(?,?)',[('model',json.dumps(meta)),('cursor','0')])
            nx,ny,nz=counts;batch=[]
            for i in range(math.prod(counts)):
                if i%32768==0:
                    if cancel and cancel():raise RuntimeError('Grid creation cancelled')
                    if batch:db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?)',batch);batch=[]
                ijk=(i%nx,(i//nx)%ny,i//(nx*ny))
                batch.append((i,*[origin[a]+(ijk[a]+.5)*size[a] for a in range(3)],*size,None,density,None))
            if batch:db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?)',batch)
            db.commit();db.close();db=None
            with open(temp,'r+b') as stream:os.fsync(stream.fileno())
            os.replace(temp,path)
        finally:
            if db is not None:db.close()
            if os.path.exists(temp):os.unlink(temp)
        return {'blocks':math.prod(counts),'path':str(path),'crs':meta['crs'],'grade_unit':grade_unit}

    def count(self):return self.db.execute('SELECT count(*) FROM blocks').fetchone()[0]

    def _begin(self,label,where='',parameters=()):
        self.db.execute('BEGIN IMMEDIATE')
        cursor=int(self.db.execute('SELECT value FROM metadata WHERE key="cursor"').fetchone()[0])
        self.db.execute('DELETE FROM changes WHERE revision>?',(cursor,));self.db.execute('DELETE FROM revisions WHERE id>?',(cursor,))
        revision=cursor+1
        self.db.execute('INSERT INTO revisions VALUES(?,?)',(revision,label))
        self.db.execute('INSERT INTO changes(revision,block_id,og,od,oz) SELECT ?,id,grade,density,domain FROM blocks '+where,(revision,*parameters))
        return revision

    def _finish(self,revision):
        self.db.execute('''UPDATE changes SET ng=b.grade,nd=b.density,nz=b.domain FROM blocks b WHERE changes.revision=? AND b.id=changes.block_id''',(revision,))
        self.db.execute('UPDATE metadata SET value=? WHERE key="cursor"',(str(revision),))
        # Retain at most 20 revisions and two million changed rows on disk.
        while True:
            stats=self.db.execute('SELECT count(*),min(id) FROM revisions').fetchone()
            rows=self.db.execute('SELECT count(*) FROM changes').fetchone()[0]
            if stats[0]<=20 and rows<=2_000_000:break
            self.db.execute('DELETE FROM changes WHERE revision=?',(stats[1],));self.db.execute('DELETE FROM revisions WHERE id=?',(stats[1],))
        self.db.commit()

    def edit(self,block_id,grade,density,domain):
        if domain=='':domain=None
        if grade is not None:
            finite(grade)
            if grade<0 or (self.meta['grade_unit']=='%' and grade>100):raise ValueError('Invalid grade')
        if density is not None:
            finite(density)
            if density<=0:raise ValueError('Invalid density')
        if domain is not None and (not isinstance(domain,str) or len(domain)>200):raise ValueError('Invalid domain')
        if type(block_id)!=int or not self.db.execute('SELECT 1 FROM blocks WHERE id=?',(block_id,)).fetchone():raise ValueError('Unknown block ID')
        try:
            revision=self._begin('Edit block','WHERE id=?',(block_id,))
            self.db.execute('UPDATE blocks SET grade=?,density=?,domain=? WHERE id=?',(grade,density,domain,block_id));self._finish(revision)
        except Exception:self.db.rollback();raise

    def undo(self,redo=False):
        cursor=int(self.db.execute('SELECT value FROM metadata WHERE key="cursor"').fetchone()[0])
        query='SELECT min(id) FROM revisions WHERE id>?' if redo else 'SELECT id FROM revisions WHERE id=?'
        row=self.db.execute(query,(cursor,)).fetchone()
        if not row or row[0] is None:return False
        revision=row[0];prefix='n' if redo else 'o'
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute(f'''UPDATE blocks SET grade=c.{prefix}g,density=c.{prefix}d,domain=c.{prefix}z FROM changes c WHERE c.revision=? AND c.block_id=blocks.id''',(revision,))
            previous=self.db.execute('SELECT max(id) FROM revisions WHERE id<?',(revision,)).fetchone()[0] or 0
            self.db.execute('UPDATE metadata SET value=? WHERE key="cursor"',(str(revision if redo else previous),));self.db.commit()
        except Exception:self.db.rollback();raise
        return True

    def estimate_idw(self,samples,radius=100.,neighbors=12,minimum=3,power=2.,cancel=None):
        finite(radius,power)
        if radius<=0 or power<=0 or type(neighbors)!=int or type(minimum)!=int or not 1<=minimum<=neighbors<=128:raise ValueError('Invalid search settings')
        values=np.asarray(samples,dtype=np.float64)
        if values.ndim!=2 or values.shape[1]!=4 or not len(values) or not np.isfinite(values).all() or np.any(values[:,3]<0):raise ValueError('Finite x,y,z,grade samples required')
        if self.meta['grade_unit']=='%' and np.any(values[:,3]>100):raise ValueError('Percent grade exceeds 100')
        if len(np.unique(values[:,:3],axis=0))!=len(values):raise ValueError('Resolve duplicate sample locations before estimation')
        tree=cKDTree(values[:,:3]);estimated=0;count=0
        try:
            revision=self._begin('Centre-support IDW')
            reader=self.db.execute('SELECT id,x,y,z FROM blocks ORDER BY id')
            while True:
                rows=reader.fetchmany(32768)
                if not rows:break
                if cancel and cancel():raise RuntimeError('Estimation cancelled; transaction rolled back')
                array=np.asarray(rows,dtype=np.float64)
                distance,index=tree.query(array[:,1:],k=list(range(1,neighbors+1)),distance_upper_bound=radius)
                valid=np.isfinite(distance);safe=np.minimum(index,len(values)-1)
                # Scale by nearest distance to avoid overflow for tiny distances
                # or a large user-supplied exponent; nearest nonzero weight=1.
                nearest=np.maximum(distance[:,0],1e-12)
                nearest=np.where(np.isfinite(nearest),nearest,1.)
                weights=np.where(valid,(nearest[:,None]/np.maximum(distance,1e-12))**power,0.)
                total=weights.sum(axis=1);grades=(weights*values[safe,3]).sum(axis=1)/np.maximum(total,1e-300)
                exact=distance[:,0]<=1e-10;grades[exact]=values[safe[exact,0],3]
                supported=(valid.sum(axis=1)>=minimum)|exact
                self.db.executemany('UPDATE blocks SET grade=? WHERE id=?',[(float(g) if ok else None,int(row[0])) for row,g,ok in zip(rows,grades,supported)])
                count+=len(rows);estimated+=int(supported.sum())
            self._finish(revision)
        except Exception:self.db.rollback();raise
        return {'blocks':count,'estimated':estimated,'unestimated':count-estimated,'method':'centre-support IDW','radius_m':radius,'neighbors':neighbors,'minimum':minimum,'power':power,'sample_sha256':hashlib.sha256(values.tobytes()).hexdigest(),'independent_review_verified':False}

    def totals(self,cutoff=None):
        if cutoff is not None:finite(cutoff)
        where='WHERE grade>=?' if cutoff is not None else ''
        row=self.db.execute('SELECT count(*),sum(grade IS NULL),sum(dx*dy*dz),sum(CASE WHEN density IS NULL THEN 1 ELSE 0 END),sum(dx*dy*dz*density),sum(CASE WHEN grade IS NOT NULL THEN dx*dy*dz*density END),sum(dx*dy*dz*density*grade) FROM blocks '+where,() if cutoff is None else (cutoff,)).fetchone()
        n,unknown,volume,missing_density,tonnes,estimated_tonnes,weighted=row
        factor=.01 if self.meta['grade_unit']=='%' else 1e-6
        return {'blocks':n,'unestimated_blocks':unknown or 0,'volume_m3':volume or 0.,'tonnes':None if missing_density else (tonnes or 0.),'estimated_tonnes':estimated_tonnes or 0.,'contained_metal_tonnes':None if missing_density else (weighted or 0.)*factor,'grade_unit':self.meta['grade_unit'],'cutoff':cutoff,'metal_scope':'estimated blocks only','classification':'UNCLASSIFIED'}

    def preview(self,maximum=100000):
        if type(maximum)!=int or not 1<=maximum<=250000:raise ValueError('Invalid preview size')
        count=self.count();stride=max(1,math.ceil(count/maximum))
        rows=self.db.execute('SELECT id,x,y,z,grade FROM blocks WHERE id % ?=0 ORDER BY id',(stride,)).fetchall()
        xyz=np.array([row[1:4] for row in rows],dtype=np.float64)
        payload={'kind':'points','xyz':xyz,'source_index':np.array([r[0] for r in rows],dtype=np.int64),'source_points':count,'matched_before_sampling':count,'stride':stride,'crs':self.meta['crs']}
        if any(r[4] is not None for r in rows):
            keep=np.array([r[4] is not None for r in rows]);payload.update(kind='blocks',xyz=xyz[keep],source_index=payload['source_index'][keep],grade=np.array([r[4] for r in rows if r[4] is not None]),sizes=np.tile(self.meta['size'],(int(keep.sum()),1)))
            payload['matched_before_sampling']=self.db.execute('SELECT count(*) FROM blocks WHERE grade IS NOT NULL').fetchone()[0]
        return payload

    def export_csv(self,path,cancel=None):
        path=Path(path);fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.rainymine-export-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['id','x','y','z','dx','dy','dz','grade','density','domain'])
                reader=self.db.execute('SELECT * FROM blocks ORDER BY id')
                while True:
                    rows=reader.fetchmany(32768)
                    if not rows:break
                    if cancel and cancel():raise RuntimeError('Export cancelled')
                    writer.writerows(rows)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return {'blocks':self.count(),'crs':self.meta['crs'],'grade_unit':self.meta['grade_unit'],'null':'empty field','domain_empty_string_and_null':'not distinguishable in this CSV; authoritative value remains in database'}

    def export_bundle(self,path,cancel=None):
        import zipfile
        path=Path(path);fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.rainymine-bundle-');os.close(fd)
        try:
            with tempfile.TemporaryDirectory(dir=path.parent) as directory:
                csv_path=Path(directory)/'blocks.csv';report=self.export_csv(csv_path,cancel)
                with csv_path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                manifest={**report,'schema':1,'coordinates':'projected metres XYZ','density_unit':'t/m3','null':'empty CSV field; empty domains normalized to NULL','model':self.meta,'sha256':{'blocks.csv':digest}}
                if cancel and cancel():raise RuntimeError('Export cancelled')
                with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_STORED) as archive:
                    archive.write(csv_path,'blocks.csv');archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False))
                with open(temp,'r+b') as stream:os.fsync(stream.fileno())
                if cancel and cancel():raise RuntimeError('Export cancelled')
                os.replace(temp,path)
            return manifest
        finally:
            if os.path.exists(temp):os.unlink(temp)
