"""Atomic per-session recovery, including projects that have never been saved."""
import json
import time
import uuid
from pathlib import Path
from .core import Project, MAX_FILE, atomic_write


class RecoveryStore:
    def __init__(self, root, session=None):
        self.root = Path(root)
        self.session = session or uuid.uuid4().hex
        if not self.session.isalnum():
            raise ValueError('Invalid recovery session')
        self.path = self.root / (self.session + '.recovery')

    def write(self, project, original_path=None):
        document = {'schema': 1, 'saved_at': time.time(),
                    'original_path': str(original_path) if original_path else None,
                    'project': project.to_dict()}
        text = json.dumps(document, ensure_ascii=False, allow_nan=False)
        if len(text.encode('utf-8')) > MAX_FILE:
            raise ValueError('Recovery exceeds project size limit')
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, text)
        return self.path

    def read(self, path):
        path = Path(path)
        if path.resolve().parent != self.root.resolve() or path.suffix != '.recovery':
            raise ValueError('Recovery must be inside the recovery directory')
        if path.stat().st_size > MAX_FILE:
            raise ValueError('Recovery exceeds project size limit')
        document = json.loads(path.read_text(encoding='utf-8'))
        if document.get('schema') != 1:
            raise ValueError('Unsupported recovery schema')
        return Project.from_dict(document['project']), document

    def candidates(self):
        result = []
        for path in self.root.glob('*.recovery'):
            if path == self.path:
                continue
            try:
                project, document = self.read(path)
                result.append({'path': path, 'name': project.name,
                               'saved_at': document['saved_at'],
                               'original_path': document.get('original_path')})
            except (OSError, ValueError, KeyError, TypeError):
                # Preserve damaged snapshots for manual recovery; never delete them.
                continue
        return sorted(result, key=lambda item: item['saved_at'], reverse=True)

    def clear(self):
        self.path.unlink(missing_ok=True)
