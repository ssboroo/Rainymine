"""Verify the current build's complete checksum set before uploading a draft only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def verified_assets(dist, commit, run):
    manifest = json.loads((dist / 'release-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('draft') is not True or manifest.get('prerelease') is not True or manifest.get('production_ready') is not False:
        raise ValueError('Only an explicitly non-production draft prerelease is allowed')
    if manifest['source_commit'] != commit or str(manifest['source_run_id']) != str(run):
        raise ValueError('Artifact provenance differs from this workflow')
    required = {asset['name'] for asset in manifest['assets']} | {'package-inventory.json', 'release-manifest.json'}
    sums = {}
    for line in (dist / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        sha, name = line.split('  ', 1)
        if Path(name).name != name or '/' in name or '\\' in name or not re.fullmatch('[a-f0-9]{64}', sha) or name in sums:
            raise ValueError('Unsafe or duplicate checksum entry')
        sums[name] = sha
    if set(sums) != required:
        raise ValueError('Incomplete checksum set')
    for name, sha in sums.items():
        path = dist / name
        if not path.is_file():
            matches = [entry for entry in dist.rglob(name) if entry.is_file()]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous asset: ' + name)
            shutil.copy2(matches[0], path)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != sha:
                raise ValueError('Checksum mismatch: ' + name)
    for asset in manifest['assets']:
        if sums[asset['name']] != asset['sha256'] or (dist / asset['name']).stat().st_size != asset['bytes']:
            raise ValueError('Manifest mismatch')
    return manifest, sorted(required | {'SHA256SUMS.txt'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, required=True)
    args = parser.parse_args()
    manifest, names = verified_assets(args.dist, os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID'])
    tag = manifest['tag']
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'isDraft,isPrerelease,targetCommitish'], capture_output=True, text=True)
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        if not release['isDraft'] or not release['isPrerelease'] or release['targetCommitish'] != manifest['source_commit']:
            raise SystemExit('Refusing to change an unrelated or published release')
    else:
        subprocess.run(['gh', 'release', 'create', tag, '--draft', '--prerelease', '--target', manifest['source_commit'], '--title', manifest['title'], '--notes-file', 'release/RELEASE_NOTES.mn.md'], check=True)
    subprocess.run(['gh', 'release', 'upload', tag, '--clobber'] + [str(args.dist / name) for name in names], check=True)
    subprocess.run(['gh', 'release', 'view', tag, '--json', 'url,isDraft,isPrerelease,assets'], check=True)


if __name__ == '__main__':
    main()
