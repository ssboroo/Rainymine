"""Validate version consistency and generate Inno version declarations."""
import argparse
import ast
import json
from pathlib import Path
import re


def version(root):
    module=ast.parse((Path(root)/'rainymine/__init__.py').read_text(encoding='utf-8'))
    value=next(ast.literal_eval(node.value) for node in module.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets))
    if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\.[1-9]\d*)?',value):raise ValueError('Invalid release version')
    return value


def check(root):
    root=Path(root);value=version(root);config=json.loads((root/'release/config.json').read_text(encoding='utf-8'))
    expected=[f'Rainymine-{value}-Setup-x64.exe',f'Rainymine-{value}-Windows-x64.zip',f'Rainymine-{value}-AI-Offline-x64.zip']
    if config.get('version')!=value or config.get('tag')!='v'+value or config.get('files')!=expected:raise ValueError('App/config/tag/artifact versions differ')
    if '-rc.' in value and (config.get('prerelease') is not True or config.get('draft') is not True):raise ValueError('Release candidate must remain draft and prerelease')
    return value


def write_installer(root):
    root=Path(root);value=check(root);target=root/'dist/Version.iss';target.parent.mkdir(exist_ok=True)
    numeric=value.split('-')[0]+'.0'
    target.write_text(f'#define AppVersion "{value}"\n#define AppNumericVersion "{numeric}"\n',encoding='utf-8')
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--check',action='store_true');parser.add_argument('--write-installer',action='store_true')
    args=parser.parse_args();value=check(args.root)
    if args.write_installer:write_installer(args.root)
    print(value)
