"""Reproduce the reviewed conflict resolution using Git CLI in an isolated worktree."""
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'scripts/merge-resolution.json').read_text(encoding='utf-8'))
    def git(*args, cwd=root, check=True):
        return subprocess.run(['git', *args], cwd=cwd, check=check,
                              capture_output=True, text=True, encoding='utf-8')
    parents = manifest['parents']
    resolution = None
    for line in git('rev-list', '--parents', 'HEAD').stdout.splitlines():
        fields = line.split()
        if fields[1:] == parents:
            resolution = fields[0]
            break
    if resolution is None:
        raise RuntimeError('Reviewed two-parent merge is missing from checkout history')
    with tempfile.TemporaryDirectory(prefix='rainymine-merge-') as temporary:
        work = str(Path(temporary) / 'checkout')
        git('worktree', 'add', '--detach', work, parents[0])
        try:
            merged = git('-c', 'user.name=RAINYMINE CI', '-c', 'user.email=ci@rainymine.invalid',
                         'merge', '--no-commit', '--no-ff', parents[1], cwd=work, check=False)
            if merged.returncode not in (0, 1):
                raise RuntimeError(merged.stdout + merged.stderr)
            conflicts = set(git('diff', '--name-only', '--diff-filter=U', cwd=work).stdout.splitlines())
            unexpected = conflicts - set(manifest['expected_conflicts'])
            if unexpected:
                raise RuntimeError('Unexpected merge conflicts: ' + repr(sorted(unexpected)))
            git('restore', '--source=' + resolution, '--staged', '--worktree',
                '--', *manifest['resolution_paths'], cwd=work)
            if git('diff', '--name-only', '--diff-filter=U', cwd=work).stdout.strip():
                raise RuntimeError('Unresolved merge entries remain')
            git('diff', '--cached', '--check', cwd=work)
            actual = git('write-tree', cwd=work).stdout.strip()
            expected = git('rev-parse', resolution + '^{tree}').stdout.strip()
            if actual != expected:
                differences = git('diff', '--cached', '--name-status', resolution, cwd=work).stdout
                raise RuntimeError('CLI merge tree differs from reviewed tree:\n' + differences)
            print('Git CLI merge reproduced:', resolution, 'tree:', actual,
                  'conflicts resolved:', len(conflicts), flush=True)
        finally:
            git('worktree', 'remove', '--force', work, check=False)
            git('worktree', 'prune')


if __name__ == '__main__':
    main()
