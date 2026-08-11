"""Migration matrisi, `/tmp` temizlendikten sonra da kurulabilmeli.

NEDEN VAR: `_ensure_worktree` "eksikse kendisi kurar" diye düzeltilmişti ve
docstring'i `/tmp` temizliği vakasını kapattığını söylüyordu. Kapatmamıştı:
dizin silinince kayıt `.git/worktrees` altında KALIYOR, `git worktree add`
da "missing but already registered" ile reddediyor. `_main`'in `finally`
bloğundaki `prune` hatadan SONRA koştuğu için gözlenen davranış şuydu —
birinci koşum kırmızı, ikinci koşum yeşil.

CI'da temiz clone olduğu için hiç görünmüyordu; bedeli yalnız kapıyı elle
doğrulamak isteyen kişi ödüyordu, yani düzeltmenin hedeflediği kişi.

Buradaki iki test birlikte anlamlı: birincisi vakanın kapandığını, ikincisi
KAPATMA BİÇİMİNİN sağlam olduğunu sabitliyor. `prune` yerine `add -f`
kullanmak birinciyi geçirir ama ikinciyi kırar — ayakta duran bir worktree'nin
kaydını da ezerdi.
"""

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.audit import check_schema_consistency as matrix


def _git(*args, cwd):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, text=True, capture_output=True, check=True,
    )


class WorktreeProvisioningTest(unittest.TestCase):
    """Gerçek `git` ile koşuyor; kapı da gerçek `git` kullanıyor."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.worktrees = root / "worktrees"

        _git("init", "--quiet", "-b", "main", cwd=self.repo)
        (self.repo / "file.txt").write_text("v1\n", encoding="utf-8")
        _git("add", "file.txt", cwd=self.repo)
        _git("commit", "--quiet", "-m", "ilk", cwd=self.repo)
        _git("tag", "v0.0.1", cwd=self.repo)

        # `_ensure_worktree` modül sabitinden depo kökünü okuyor.
        self._saved_root = matrix.CURRENT_ROOT
        matrix.CURRENT_ROOT = self.repo
        self.addCleanup(self._restore_root)

    def _restore_root(self):
        matrix.CURRENT_ROOT = self._saved_root

    def _registered(self):
        listed = _git("worktree", "list", "--porcelain", cwd=self.repo)
        return listed.stdout

    def test_stale_registration_does_not_block_setup(self):
        """ASIL HATA: dizin silinmiş ama kayıt duruyorsa yine kurulabilmeli."""
        target = self.worktrees / "archlence-audit-v001"
        self.assertTrue(matrix._ensure_worktree(target, "v0.0.1"))

        # `/tmp` temizliğini simüle et: dizin gider, kayıt kalır.
        subprocess.run(["rm", "-rf", str(target)], check=True)
        self.assertIn("archlence-audit-v001", self._registered())
        self.assertFalse(target.exists())

        # Düzeltme öncesi burası "missing but already registered" ile
        # `SystemExit` atıyordu.
        self.assertTrue(matrix._ensure_worktree(target, "v0.0.1"))
        self.assertTrue((target / "file.txt").exists())

    def test_existing_worktree_is_left_alone(self):
        """`add -f`'e kayarsak bu test kırılır — ayakta olanı ezmemeli.

        Kurulumu kapı yapmadıysa (geliştirici elle kurduysa) `False` döner ve
        `_main` onu temizleme listesine ALMAZ; içeriğine de dokunulmaz.
        """
        target = self.worktrees / "archlence-audit-v001"
        self.worktrees.mkdir(parents=True, exist_ok=True)
        _git("worktree", "add", "--quiet", "--detach", str(target), "v0.0.1",
             cwd=self.repo)
        marker = target / "geliştiricinin-dosyası.txt"
        marker.write_text("elle kuruldu\n", encoding="utf-8")

        self.assertFalse(matrix._ensure_worktree(target, "v0.0.1"))
        self.assertTrue(marker.exists(), "Var olan worktree yeniden kurulmuş.")

    def test_missing_tag_fails_loudly(self):
        """Etiket yoksa sessizce atlanmamalı — kapı ölçmeden yeşile dönerdi."""
        with self.assertRaises(SystemExit):
            matrix._ensure_worktree(self.worktrees / "yok", "v9.9.9")


if __name__ == "__main__":
    unittest.main()
