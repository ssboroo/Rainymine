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


class UnicodePackagingTests(unittest.TestCase):
    def test_mongolian_metadata_uses_explicit_utf8_even_on_windows(self):
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'release').mkdir()
            dist = root / 'dist'
            dist.mkdir()
            (dist / 'fixture.exe').write_bytes(b'MZ-test-fixture')
            config = {'source_commit': 'fixture', 'draft': True, 'prerelease': True,
                      'version': '0.7.0', 'title': 'Шинэ ажлын талбар — Монгол', 'files': ['fixture.exe']}
            (root / 'release/config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            (root/'docs').mkdir()
            (root/'docs'/'V1_0.mn.md').write_text('RC заавар',encoding='utf-8')
            original = Path.read_text
            def strict_read(path, *args, **kwargs):
                self.assertEqual(kwargs.get('encoding'), 'utf-8')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'read_text', strict_read):
                module.prepare(root, dist)
            manifest = json.loads((dist / 'release-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['title'], config['title'])
            self.assertFalse(manifest['production_ready'])
            self.assertTrue((dist / 'SHA256SUMS.txt').exists())
            with zipfile.ZipFile(dist/'Rainymine-0.7.0-Release-Kit.zip') as kit:
                self.assertEqual(kit.read('docs/V1_0.mn.md').decode('utf-8'),'RC заавар')
                self.assertEqual(len(kit.namelist()),len(set(kit.namelist())))
