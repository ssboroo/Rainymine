"""Bootstrap loads optional Mesa before importing Qt or VTK."""
import os
import sys
from pathlib import Path

_mesa_handles=[]
if sys.platform=='win32' and os.environ.get('RAINYMINE_SOFTWARE')=='1':
    import ctypes
    root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    drivers=root/'software-rendering'
    if not (drivers/'opengl32.dll').is_file():
        raise RuntimeError('Software rendering drivers not found. Use the complete Windows package.')
    os.environ['GALLIUM_DRIVER']='llvmpipe'
    _mesa_handles.append(os.add_dll_directory(str(drivers)))
    for name in ('libglapi.dll','libgallium_wgl.dll','opengl32.dll'):
        _mesa_handles.append(ctypes.WinDLL(str(drivers/name)))

from rainymine.ui import main
if __name__=='__main__':
    raise SystemExit(main())
