import os
import subprocess
import sys
import textwrap
import unittest


class StartupImportTest(unittest.TestCase):
    def test_main_module_imports_without_system_exit(self):
        env = os.environ.copy()
        env.pop("KIVY_WINDOW", None)
        env.pop("KIVY_NO_ARGS", None)
        env.setdefault("PYTHONPATH", os.getcwd())

        script = textwrap.dedent(
            """
            import importlib
            import os
            import sys

            os.environ.setdefault('KIVY_NO_ARGS', '1')
            os.environ.setdefault('KIVY_WINDOW', 'mock')

            module = importlib.import_module('main')
            assert module.FinoraApp is not None
            print('imported')
            """
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
        self.assertIn("imported", completed.stdout)


if __name__ == "__main__":
    unittest.main()
