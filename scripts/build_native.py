"""Build pinned Rust/C++ kernels and install the wheel for this interpreter."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
env=dict(os.environ,RUSTUP_TOOLCHAIN='1.85.1')
with tempfile.TemporaryDirectory(prefix='rainymine-native-') as folder:
    subprocess.run([sys.executable,'-m','maturin','build','--release','--locked','--manifest-path',str(root/'native/rainymine_core/Cargo.toml'),'--out',folder],check=True,cwd=root,env=env)
    wheels=list(Path(folder).glob('*.whl'))
    if len(wheels)!=1:raise RuntimeError('Expected one native wheel')
    subprocess.run([sys.executable,'-m','pip','install','--force-reinstall','--no-deps',str(wheels[0])],check=True)
subprocess.run([sys.executable,str(root/'scripts/native_notices.py')],check=True,env=env)
subprocess.run([sys.executable,'-c','import rainymine_core; assert rainymine_core.ENGINE_VERSION == "0.1.0"; print("Rust/C++ kernels loaded")'],check=True)
