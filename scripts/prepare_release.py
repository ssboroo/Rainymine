"""Assemble a traceable release candidate without declaring production readiness."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_archive(path, offline=False):
    with zipfile.ZipFile(path) as archive:
        names = [name.replace('\\', '/') for name in archive.namelist()]
        for name in names:
            if name.startswith('/') or '..' in name.split('/'):
                raise ValueError('Unsafe archive entry: ' + name)
        for suffix in ('/Rainymine.exe', '/ai/runtime/llama-server.exe'):
            if not any(('/' + name).endswith(suffix) for name in names):
                raise ValueError('Missing ' + suffix)
        if offline:
            models = [name for name in names if name.endswith('.gguf')]
            if len(models) != 1:
                raise ValueError('Expected exactly one offline model')
            with archive.open(models[0]) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != 'd2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5':
                raise ValueError('Offline model hash mismatch')
        return [{'path': entry.filename, 'bytes': entry.file_size} for entry in archive.infolist()]


def prepare(root, dist):
    config = json.loads((root / 'release/config.json').read_text(encoding='utf-8'))
    if config['source_commit'] == 'CURRENT_BUILD':
        if not os.environ.get('GITHUB_ACTIONS') or not os.environ.get('GITHUB_RUN_ID'):
            raise ValueError('Release provenance requires a GitHub Actions build')
        config['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if config['source_commit'] != os.environ.get('GITHUB_SHA'):
            raise ValueError('Checked out source differs from workflow commit')
        config['source_tree'] = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=root, text=True).strip()
        config['source_run_id'] = int(os.environ['GITHUB_RUN_ID'])
        config['source_run_url'] = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
    if config['draft'] is not True or config['prerelease'] is not True:
        raise ValueError('Unapproved production publication is disabled')
    records = []
    inventories = {}
    for name in config['files']:
        if Path(name).name != name:
            raise ValueError('Invalid release filename')
        path = dist / name
        if not path.is_file():
            matches = [candidate for candidate in dist.rglob(name) if candidate.is_file()]
            if len(matches) == 1:
                import shutil
                shutil.copy2(matches[0], path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or empty asset: ' + name)
        if path.suffix == '.exe':
            with path.open('rb') as stream:
                if stream.read(2) != b'MZ':
                    raise ValueError('Invalid Windows executable')
        elif path.suffix == '.zip':
            inventories[name] = validate_archive(path, 'AI-Offline' in name)
        records.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
    inventory_path = dist / 'package-inventory.json'
    inventory_path.write_text(json.dumps(inventories, indent=2), encoding='utf-8')
    kit = dist / ('Rainymine-' + config['version'] + '-Release-Kit.zip')
    with zipfile.ZipFile(kit, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root / 'release').glob('*')):
            if path.is_file():
                archive.write(path, 'release/' + path.name)
        for name in ('README.md', 'CHANGELOG.md', 'ACCEPTANCE.md', 'MICROMINE_SCOPE.md', 'DESIGN.md', 'docs/BRANDBOOK.mn.md',
                     'assets/brandbook-2026.jpg', 'assets/rainymine-brand.svg', 'assets/brandmark.png',
                     'assets/splash.svg', 'assets/splash-new.png', 'assets/splash-background.jpg', 'docs/TOOLS.mn.md'):
            if (root / name).is_file():
                archive.write(root / name, name)
        for path in sorted(list((root / 'assets').glob('*LICENSE*')) + list((root / 'assets').glob('*NOTICES*'))):
            archive.write(path, 'third-party/' + path.name)
        archive.write(inventory_path, inventory_path.name)
    records.append({'name': kit.name, 'bytes': kit.stat().st_size, 'sha256': digest(kit)})
    manifest = dict(config, assets=records, production_ready=False,
                    inventory_scope='ZIP file inventory, not a complete SBOM or license audit',
                    automated_checks=['Windows executable header', 'portable executable/runtime presence',
                                      'offline model SHA256', 'asset SHA256 and size'])
    manifest_path = dist / 'release-manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    check_paths = [dist / item['name'] for item in records] + [inventory_path, manifest_path]
    (dist / 'SHA256SUMS.txt').write_text(''.join(digest(path) + '  ' + path.name + '\n' for path in check_paths), encoding='utf-8')
    for line in (dist / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        if digest(dist / name) != expected:
            raise ValueError('Post-write checksum mismatch')
    print('Verified release candidate assets:', len(check_paths))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, required=True)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], args.dist)
