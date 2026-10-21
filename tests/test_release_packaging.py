import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('release_packaging', Path(__file__).parents[1] / 'scripts/prepare_release.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackagingTests(unittest.TestCase):
    def test_rejects_missing_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Rainymine/Rainymine.exe', b'MZ')
            with self.assertRaisesRegex(ValueError, 'llama-server'):
                module.validate_archive(path)

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('../outside', b'x')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                module.validate_archive(path)

    def test_rejects_wrong_offline_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Rainymine/Rainymine.exe', b'MZ')
                archive.writestr('Rainymine/ai/runtime/llama-server.exe', b'MZ')
                archive.writestr('Rainymine/ai/models/model.gguf', b'wrong model')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                module.validate_archive(path, True)


if __name__ == '__main__':
    unittest.main()
