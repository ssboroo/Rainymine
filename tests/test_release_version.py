import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('release_version',Path(__file__).parents[1]/'scripts/release_version.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ReleaseVersionTests(unittest.TestCase):
    def test_actual_configuration_and_generated_numeric_version(self):
        root=Path(__file__).parents[1];self.assertEqual(module.check(root),'1.0.0-rc.1')
        with tempfile.TemporaryDirectory() as d:
            target=Path(d);(target/'rainymine').mkdir();(target/'release').mkdir()
            shutil.copyfile(root/'rainymine/__init__.py',target/'rainymine/__init__.py')
            shutil.copyfile(root/'release/config.json',target/'release/config.json')
            text=module.write_installer(target).read_text(encoding='utf-8')
            self.assertIn('AppVersion "1.0.0-rc.1"',text);self.assertIn('AppNumericVersion "1.0.0.0"',text)
            config=json.loads((target/'release/config.json').read_text());config['prerelease']=False
            (target/'release/config.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):module.check(target)
            config['prerelease']=True;config['files']=['stale.zip'];(target/'release/config.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):module.check(target)
