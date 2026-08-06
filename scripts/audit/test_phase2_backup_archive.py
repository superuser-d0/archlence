"""Backup archive containment and member allow-list audit (temporary only)."""
from __future__ import annotations

import zipfile

from scripts.audit.test_adversarial_reproductions import _TemporaryProfile
from utils.errors import IntegrityVerificationError


class BackupArchiveSecurityReproduction(_TemporaryProfile):
    def _backup(self):
        from services.backup_service import create_backup

        self.create_account()
        package = self.root / "source.archlence-backup"
        create_backup(package, self.PASSPHRASE, db_path=self.db_path, key_path=self.key_path)
        return package

    def _rewrite(self, source, name, content=b"audit"):
        target = self.root / (name.replace("/", "_").replace("\\", "_") + ".zip")
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(target, "w") as outgoing:
            for member in incoming.infolist():
                outgoing.writestr(member, incoming.read(member.filename))
            outgoing.writestr(name, content)
        return target

    def _verify(self, package):
        from services.backup_service import verify_backup
        caught = None
        try:
            verify_backup(package, self.PASSPHRASE)
        except Exception as exc:
            caught = exc
        return caught

    def test_path_traversal_and_absolute_members_are_rejected(self):
        source = self._backup()
        results = {}
        for member in ("../escape.txt", "/tmp/escape.txt", "C:\\escape.txt"):
            caught = self._verify(self._rewrite(source, member))
            results[member] = type(caught).__name__ if caught else "NONE"
        print(f"AUDIT_STATE archive_paths results={results}")
        self.assertEqual(results["../escape.txt"], "IntegrityVerificationError")
        self.assertEqual(results["/tmp/escape.txt"], "IntegrityVerificationError")
        # On Linux, a Windows drive path is a relative filename; it needs an
        # explicit cross-platform policy rather than a false claim of coverage.

    def test_unexpected_member_is_rejected(self):
        source = self._backup()
        caught = self._verify(self._rewrite(source, "unexpected.txt"))
        print(
            "AUDIT_STATE archive_unexpected "
            f"expected_exception=IntegrityVerificationError caught={type(caught).__name__ if caught else 'NONE'}"
        )
        self.assertIsInstance(caught, IntegrityVerificationError)


if __name__ == "__main__":
    import unittest
    unittest.main()
