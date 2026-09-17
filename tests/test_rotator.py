import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RotatorTests(unittest.TestCase):
    def test_config_from_env(self):
        path = ROOT / 'rotator.py'
        self.assertTrue(path.exists(), 'нет подготовленного ротатора')
        tree = ast.parse(path.read_text())
        values = {n.targets[0].id: ast.unparse(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
        for key in ('API_ID', 'API_HASH'):
            self.assertIn('os.environ', values[key])

    def test_bio(self):
        path = ROOT / 'rotator.py'
        if not path.exists():
            self.skipTest('ждём исходник')
        tree = ast.parse(path.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_about')
        scope = {'BIO_LIMIT': 70}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
        self.assertEqual(scope['build_about'](0, 2, 'пример'), '1/2 пример | shpateil.fun')
        self.assertEqual(len(scope['build_about'](0, 1, 'я' * 100)), 70)


if __name__ == '__main__':
    unittest.main()
