"""Managed llama.cpp CPU process and verified one-time local asset installation."""
import hashlib
import json
import os
from pathlib import Path,PureWindowsPath
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

RUNTIME_TAG='b11796'
RUNTIME_URL=f'https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_TAG}/llama-{RUNTIME_TAG}-bin-win-cpu-x64.zip'
RUNTIME_SHA='d3ae3e9f395175b5a1cf8e9a82bbc92d21c1f44201dd0321f0196f8a4d2d0b69'
MODEL_NAME='Qwen3-1.7B-Q4_K_M.gguf'
MODEL_URL='https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/daeb8e2d528a760970442092f6bf1e55c3b659eb/'+MODEL_NAME
MODEL_SHA='d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5'
MODEL_BYTES=1282439264


def data_root():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))/'Rainymine'/'ai'


def bundled_runtime():
    root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return root/'ai'/'runtime'/'llama-server.exe'


def default_paths():
    engine=bundled_runtime()
    if not engine.is_file():engine=data_root()/'runtime'/RUNTIME_TAG/'llama-server.exe'
    bundled=bundled_runtime().parent.parent/'models'/MODEL_NAME
    return engine,bundled if bundled.is_file() else data_root()/'models'/MODEL_NAME


def download_verified(url,destination,digest,maximum_bytes,progress=None,cancel=None):
    """Only approved HTTPS asset sources; partial/invalid downloads never replace files."""
    if not url.startswith(('https://github.com/ggml-org/llama.cpp/releases/download/','https://huggingface.co/ggml-org/')):
        raise ValueError('AI asset URL зөвшөөрөгдөөгүй.')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.is_file() and file_sha(destination)==digest:return destination
    temporary=destination.with_name(destination.name+'.part');h=hashlib.sha256();count=0
    try:
        with urllib.request.urlopen(url,timeout=30) as response,temporary.open('wb') as output:
            total=int(response.headers.get('Content-Length',0))
            if total>maximum_bytes:raise ValueError('AI таталт хүлээгдсэн хэмжээнээс их.')
            while True:
                if cancel and cancel():raise RuntimeError('AI таталтыг цуцаллаа.')
                chunk=response.read(1024*1024)
                if not chunk:break
                count+=len(chunk)
                if count>maximum_bytes:raise ValueError('AI таталт хэт их.')
                output.write(chunk);h.update(chunk)
                if progress:progress(count,total)
        if h.hexdigest()!=digest:raise ValueError('AI файлын SHA256 таарсангүй. Хуучин файлыг өөрчлөөгүй.')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def extract_runtime(archive,destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if sum(f.file_size for f in z.infolist())>600_000_000:raise ValueError('AI runtime archive хэт их.')
        for f in z.infolist():
            p=Path(f.filename)
            if p.is_absolute() or PureWindowsPath(f.filename).drive or '..' in p.parts or '\\' in f.filename or ((f.external_attr>>16)&0o170000)==0o120000:
                raise ValueError('AI archive path буруу.')
        with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
            z.extractall(tmp);servers=list(Path(tmp).rglob('llama-server.exe'))
            if len(servers)!=1:raise ValueError('Runtime дотор llama-server.exe олдсонгүй.')
            source=servers[0].parent
            if destination.exists():shutil.rmtree(destination)
            shutil.copytree(source,destination)
    return destination/'llama-server.exe'


def install_assets(progress=None,cancel=None):
    if sys.platform!='win32':raise ValueError('Автомат setup Windows x64-д зориулагдсан; бусад орчинд engine/GGUF файлаа сонгоно.')
    engine,model=default_paths()
    if not engine.is_file():
        archive=download_verified(RUNTIME_URL,data_root()/'downloads'/f'llama-{RUNTIME_TAG}.zip',RUNTIME_SHA,200_000_000,progress,cancel)
        engine=extract_runtime(archive,data_root()/'runtime'/RUNTIME_TAG)
    model=download_verified(MODEL_URL,model,MODEL_SHA,MODEL_BYTES+1024,progress,cancel)
    return str(engine),str(model)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Local AI redirect зөвшөөрөхгүй.')


class LocalEngine:
    def __init__(self,executable,model):
        self.executable=Path(executable);self.model=Path(model);self.process=None;self.port=None
        self.key=secrets.token_urlsafe(32);self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def command(self,port):
        return [str(self.executable.resolve()),'--model',str(self.model.resolve()),'--host','127.0.0.1','--port',str(port),
                '--ctx-size','4096','--parallel','1','--threads',str(max(1,min(8,(os.cpu_count() or 2)-1))),
                '--n-gpu-layers','0','--jinja','--api-key',self.key]
    def start(self,cancel=None):
        if self.process and self.process.poll() is None:return
        if not self.executable.is_file() or not self.model.is_file():raise ValueError('Local AI engine/model алга. Анх тохируулах эсвэл файл сонгоно уу.')
        with self.model.open('rb') as f:
            if f.read(4)!=b'GGUF':raise ValueError('GGUF model файл биш.')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        env=os.environ.copy()
        # Never inherit endpoint/auth/HF configuration from the parent environment.
        for name in list(env):
            if name.startswith(('LLAMA_ARG_','HF_','HUGGING_FACE_')):env.pop(name)
        self.process=subprocess.Popen(self.command(self.port),cwd=self.executable.resolve().parent,env=env,
                                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        deadline=time.monotonic()+180
        try:
            while time.monotonic()<deadline:
                if cancel and cancel():raise RuntimeError('AI ачаалалтыг цуцаллаа.')
                if self.process.poll() is not None:raise RuntimeError(f'Local AI engine хаагдлаа (exit {self.process.returncode}). CPU/engine/model тохирлыг шалгана уу.')
                try:
                    if self.request('/health',timeout=1).get('status')=='ok':return
                except (OSError,ValueError):pass
                time.sleep(.2)
            raise RuntimeError('Local model ачаалах хугацаа хэтэрлээ. RAM/model хэмжээг шалгана уу.')
        except Exception:self.stop();raise
    def request(self,path,payload=None,timeout=60):
        if path not in ('/health','/v1/chat/completions'):raise ValueError('Local AI route буруу.')
        data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
        request=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path,data=data,
                                     headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key})
        with self.opener.open(request,timeout=timeout) as response:
            raw=response.read(1000001)
            if len(raw)>1000000:raise ValueError('Local AI response хэт их.')
            return json.loads(raw)
    def complete(self,messages,max_tokens=128):
        if type(max_tokens)!=int or not 1<=max_tokens<=1024:raise ValueError('Local response token budget must be 1–1024')
        response=self.request('/v1/chat/completions',{'messages':messages,'temperature':0,'max_tokens':max_tokens,
            'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object'}})
        return response['choices'][0]['message']['content']
    def stop(self):
        process=self.process;self.process=None
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
