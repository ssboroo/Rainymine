"""Portable, hashed project bundles with consistent SQLite backup snapshots."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile
from .core import Project,MAX_FILE,save_project,load_project
from .disk_model import DiskModel

MAX_PACK_BYTES=5_000_000_000


def _cancel(cancel):
    if cancel and cancel():raise RuntimeError('Төслийн багцын ажиллагааг цуцаллаа.')


def _digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def _check_store(path,project):
    from pyproj import CRS
    with DiskModel(path) as store:
        if CRS.from_user_input(store.meta['crs'])!=CRS.from_user_input(project.crs_code) or store.meta['grade_unit']!=project.grade_unit:
            raise ValueError('Холбоотой блок сангийн CRS / агуулгын нэгж зөрсөн.')
        if store.db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Блок сан гэмтсэн.')
        return store.count()


def export_project_pack(path,project,cancel=None):
    path=Path(path)
    if path.suffix.lower()!='.rmpack':raise ValueError('.rmpack өргөтгөл шаардлагатай.')
    candidate=deepcopy(project);candidate.validate()
    links=candidate.workspace.get('disk_block_stores',[])
    if not isinstance(links,list) or len(links)>32 or any(not isinstance(p,str) for p in links):raise ValueError('Блок сангийн холбоос буруу / 32-оос олон.')
    sources=[Path(p).resolve(strict=True) for p in links]
    if path.resolve() in sources:raise ValueError('Багцыг эх блок сангийн дээр бичихгүй.')
    if sum(p.stat().st_size for p in sources)>MAX_PACK_BYTES:raise ValueError('Блок сангийн нийт хэмжээ 5 GB-аас их.')
    if len(set(sources))!=len(sources):raise ValueError('Блок сангийн холбоос давхардсан.')
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.rainymine-pack-');os.close(fd)
    try:
        with tempfile.TemporaryDirectory(dir=path.parent) as directory:
            root=Path(directory);(root/'stores').mkdir();files={};relative=[];total=0
            for index,source in enumerate(sources):
                _cancel(cancel);name=f'stores/{index}.rmdb';snapshot=root/name
                _check_store(source,candidate)
                started=time.monotonic()
                def progress(status,remaining,pages):
                    _cancel(cancel)
                    if time.monotonic()-started>600:raise TimeoutError('Блок сан snapshot хугацаа хэтэрсэн.')
                src=sqlite3.connect(source);dst=sqlite3.connect(snapshot)
                try:src.backup(dst,pages=256,progress=progress,sleep=.05)
                finally:src.close();dst.close()
                _check_store(snapshot,candidate)
                relative.append(name);total+=snapshot.stat().st_size
                if total>MAX_PACK_BYTES:raise ValueError('Багцын задарсан хэмжээ 5 GB-аас их.')
                files[name]={'bytes':snapshot.stat().st_size,'sha256':_digest(snapshot)}
            candidate.workspace['disk_block_stores']=relative
            save_project(root/'project.rmine',candidate)
            files['project.rmine']={'bytes':(root/'project.rmine').stat().st_size,'sha256':_digest(root/'project.rmine')}
            if total+files['project.rmine']['bytes']>MAX_PACK_BYTES:raise ValueError('Багцын хэмжээ хэтэрсэн.')
            manifest={'schema':1,'format':'RAINYMINE project pack','files':files,'stores':relative,
                      'snapshot_scope':'each SQLite database is a consistent backup; no cross-database transaction',
                      'software_version':__import__('rainymine').__version__}
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
                for name in files:
                    with (root/name).open('rb') as source,archive.open(name,'w',force_zip64=True) as target:
                        while True:
                            _cancel(cancel);chunk=source.read(1048576)
                            if not chunk:break
                            target.write(chunk)
                archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,allow_nan=False))
            with open(temporary,'r+b') as stream:os.fsync(stream.fileno())
            _cancel(cancel);os.replace(temporary,path)
        return manifest
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def import_project_pack(path,destination,cancel=None):
    destination=Path(destination).absolute()
    if destination.exists():raise ValueError('Сэргээх хавтас шинэ, хоосон нэртэй байх ёстой.')
    if not destination.parent.is_dir():raise ValueError('Эх хавтас алга.')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();names=[i.filename for i in entries]
        if len(names)!=len(set(names)) or not 2<=len(names)<=34:raise ValueError('Багцын файлын жагсаалт буруу.')
        if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size>1048576:raise ValueError('Manifest алга / хэт их.')
        manifest=json.loads(archive.read('manifest.json'))
        if not isinstance(manifest,dict) or manifest.get('schema')!=1 or manifest.get('format')!='RAINYMINE project pack':raise ValueError('Багцын хувилбар буруу.')
        files=manifest.get('files');stores=manifest.get('stores')
        if not isinstance(files,dict) or not isinstance(stores,list) or any(not isinstance(n,str) or not re.fullmatch(r'stores/[0-9]+\.rmdb',n) for n in stores) or len(stores)!=len(set(stores)):raise ValueError('Багцын холбоос буруу.')
        if set(files)!={'project.rmine',*stores} or set(names)!={*files,'manifest.json'}:raise ValueError('Багцын файлууд manifest-тэй таарахгүй.')
        total=0
        for info in entries:
            if stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:raise ValueError('Symlink / encrypted багц дэмжихгүй.')
            if info.filename=='manifest.json':continue
            item=files[info.filename]
            if not isinstance(item,dict) or type(item.get('bytes')) is not int or item['bytes']<0 or item['bytes']!=info.file_size or not isinstance(item.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('Файлын хэмжээ / SHA256 буруу.')
            total+=info.file_size
        if total>MAX_PACK_BYTES or files['project.rmine']['bytes']>MAX_FILE:raise ValueError('Задлах хэмжээ хэтэрсэн.')
        if shutil.disk_usage(destination.parent).free<total+16_000_000:raise ValueError('Сул диск хүрэлцэхгүй.')
        temporary=Path(tempfile.mkdtemp(dir=destination.parent,prefix='.rainymine-restore-'))
        try:
            for name,item in files.items():
                _cancel(cancel);target=temporary/name;target.parent.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256();size=0
                with archive.open(name) as source,target.open('xb') as output:
                    while True:
                        _cancel(cancel);chunk=source.read(1048576)
                        if not chunk:break
                        size+=len(chunk)
                        if size>item['bytes']:raise ValueError('Файл зарласан хэмжээнээс их.')
                        digest.update(chunk);output.write(chunk)
                    output.flush();os.fsync(output.fileno())
                if size!=item['bytes'] or digest.hexdigest()!=item['sha256']:raise ValueError('SHA256 / хэмжээ зөрсөн.')
            project=load_project(temporary/'project.rmine')
            if project.workspace.get('disk_block_stores',[])!=stores:raise ValueError('Төслийн холбоос manifest-тэй зөрсөн.')
            for name in stores:_cancel(cancel);_check_store(temporary/name,project)
            project.workspace['disk_block_stores']=[str(destination/name) for name in stores]
            save_project(temporary/'project.rmine',project)
            _cancel(cancel)
            if destination.exists():raise ValueError('Сэргээх хавтас аль хэдийн үүссэн.')
            os.rename(temporary,destination)
            return project,destination/'project.rmine',manifest
        finally:
            if temporary.exists():shutil.rmtree(temporary)
