import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev" / "seed_readme_profile.py"


class ReadmeSampleProfileTest(unittest.TestCase):
    def _seed(self, profile, *extra):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--profile", str(profile),
                "--fresh",
                "--as-of", "2026-08-06",
                "--seed", "20260806",
                *extra,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_fresh_generation_is_repeatable_without_duplicates(self):
        with tempfile.TemporaryDirectory() as parent:
            profile = Path(parent) / "sample"
            self._seed(profile)
            first = json.loads((profile / "sample_manifest.json").read_text())
            self._seed(profile)
            second = json.loads((profile / "sample_manifest.json").read_text())

        self.assertEqual(first, second)
        self.assertEqual(second["counts"]["accounts"], 5)
        self.assertEqual(second["counts"]["transactions"], 799)
        self.assertEqual(second["counts"]["active_assets"], 9)
        self.assertEqual(second["counts"]["active_debts"], 3)
        self.assertEqual(second["counts"]["recurring_payments"], 8)

    def test_fresh_refuses_an_unmarked_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            profile = Path(parent) / "not-a-sample"
            profile.mkdir()
            (profile / "keep.txt").write_text("user data", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--profile", str(profile), "--fresh",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((profile / "keep.txt").read_text(), "user data")


if __name__ == "__main__":
    unittest.main()
