"""Regressao do bootstrap: testes sem rede e sem processos externos."""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from scripts import bootstrap_local as mod


class BootstrapLocalTests(unittest.TestCase):
    def test_guidance_for_each_system(self):
        for system, term in [('Windows', 'PowerShell'), ('Darwin', 'Homebrew'), ('Linux', 'APT/YUM')]:
            with self.subTest(system=system):
                guidance = mod.instructions(system)
                self.assertIn(term, guidance)
                self.assertIn('check_environment', guidance)
                self.assertIn('init-env', guidance)

    def test_create_without_printing_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = 'SECRET_VALUE_FOR_TEST_ONLY'
            (root / '.env.example').write_text('KEY=' + value + '\n', encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertTrue(mod.init_env(root))
            self.assertEqual((root / '.env').read_text(), 'KEY=' + value + '\n')
            self.assertNotIn(value, output.getvalue())
            if os.name != 'nt':
                self.assertEqual((root / '.env').stat().st_mode & 0o777, 0o600)

    def test_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env.example').write_text('NEW=\n')
            (root / '.env').write_text('EXISTING=1\n')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(mod.init_env(root))
            self.assertEqual((root / '.env').read_text(), 'EXISTING=1\n')

    def test_missing_template_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                mod.init_env(Path(tmp))

    def test_symlink_template_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'actual').write_text('VALUE=\n')
            try:
                (root / '.env.example').symlink_to(root / 'actual')
            except (OSError, NotImplementedError):
                self.skipTest('Symlink indisponivel')
            with self.assertRaises(RuntimeError):
                mod.init_env(root)


if __name__ == '__main__':
    unittest.main()
