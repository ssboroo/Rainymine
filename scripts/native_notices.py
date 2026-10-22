"""Collect license texts for locked native dependencies for binary redistribution."""
import json
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
manifest=root/'native/rainymine_core/Cargo.toml'
metadata=json.loads(subprocess.check_output(['cargo','metadata','--locked','--format-version','1','--manifest-path',str(manifest)],text=True,encoding='utf-8'))
parts=['RAINYMINE native kernel third-party notices\n','MineFlow upstream commit: 6f5dd7091070b1bd85457b3ce9fd95c4e345c983\n', (root/'native/rainymine_core/vendor/mineflow/LICENSE').read_text(encoding='utf-8')]
for package in sorted(metadata['packages'],key=lambda p:p['name']):
 if package['name']=='rainymine_core':continue
 base=Path(package['manifest_path']).parent
 parts.append('\n\n'+package['name']+' '+package['version']+'\nLicense: '+str(package.get('license'))+'\nSource: '+str(package.get('repository'))+'\n')
 files=[p for p in base.iterdir() if p.is_file() and p.name.upper().startswith(('LICENSE','COPYING','NOTICE'))]
 if not files:raise RuntimeError('License text missing for '+package['name'])
 for path in sorted(files):parts.append('\n'+path.name+'\n'+path.read_text(encoding='utf-8'))
output=Path(sys.argv[1]) if len(sys.argv)>1 else root/'assets/NATIVE-NOTICES.txt'
output.write_text('\n'.join(parts),encoding='utf-8');print(output)
