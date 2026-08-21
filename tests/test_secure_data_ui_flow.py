import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mixins.migration_mixin import MigrationMixin


class _ImmediateTasks:
    def submit(self, key, work, *, on_success, on_error, **kwargs):
        try:
            on_success(work(None))
        except Exception as exc:
            on_error(exc)


class _App(MigrationMixin):
    def __init__(self):
        self.background_tasks = _ImmediateTasks()
        self.refreshed = False

    def refresh_dashboard_data(self):
        self.refreshed = True


class SecureDataUiFlowTest(unittest.TestCase):
    def test_backup_reports_success_only_after_backend_verification(self):
        app = _App()
        with mock.patch(
            "services.backup_service.create_backup",
            return_value={"path": "/tmp/verified.backup"},
        ) as create, mock.patch(
            "mixins.migration_mixin.toast"
        ) as toast:
            app._create_verified_backup("uzun-kurtarma-parolasi")
        create.assert_called_once()
        self.assertTrue(any(
            "verified" in str(call.args[0]).lower()
            for call in toast.call_args_list
        ))

    def test_restore_failure_never_refreshes_or_reports_success(self):
        app = _App()
        with mock.patch(
            "services.backup_service.restore_backup",
            side_effect=RuntimeError("injected"),
        ), mock.patch(
            "mixins.migration_mixin.toast"
        ) as toast, mock.patch(
            "utils.logging_config.get_logger"
        ):
            app._restore_verified_backup(
                "/tmp/broken.backup", "uzun-kurtarma-parolasi"
            )
        self.assertFalse(app.refreshed)
        messages = [str(call.args[0]) for call in toast.call_args_list]
        self.assertTrue(any("current data was preserved" in item for item in messages))
        self.assertFalse(any("Restore completed" in item for item in messages))

    def test_migration_success_includes_count_and_backup_path(self):
        app = _App()
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "utils.app_paths.data_dir", return_value=temp
        ), mock.patch(
            "services.crypto_migration_service.migrate_legacy_encryption",
            return_value={
                "migrated_fields": 4,
                "backup_path": str(Path(temp) / "before.backup"),
            },
        ), mock.patch(
            "mixins.migration_mixin.toast"
        ) as toast:
            app._run_legacy_migration("uzun-kurtarma-parolasi")
        self.assertTrue(any(
            "4 fields" in str(call.args[0])
            for call in toast.call_args_list
        ))

    def test_recovery_export_reports_only_verified_backend_result(self):
        app = _App()
        provider = object()
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "utils.app_paths.data_dir", return_value=temp
        ), mock.patch(
            "utils.crypto.active_key_provider", return_value=provider
        ), mock.patch(
            "services.key_recovery_service.export_recovery_package",
            return_value=str(Path(temp) / "recovery.json"),
        ) as export, mock.patch(
            "mixins.migration_mixin.toast"
        ) as toast:
            app._export_key_recovery("uzun-kurtarma-parolasi")
        export.assert_called_once()
        self.assertTrue(any(
            "verified" in str(call.args[0]).lower()
            for call in toast.call_args_list
        ))

    def test_recovery_import_failure_does_not_report_success(self):
        app = _App()
        with mock.patch(
            "services.key_recovery_service.import_recovery_package",
            side_effect=RuntimeError("injected"),
        ), mock.patch(
            "utils.crypto.active_key_provider", return_value=object()
        ), mock.patch(
            "utils.logging_config.get_logger"
        ), mock.patch(
            "mixins.migration_mixin.toast"
        ) as toast:
            app._import_key_recovery(
                "/tmp/tampered.json", "uzun-kurtarma-parolasi"
            )
        messages = [str(call.args[0]) for call in toast.call_args_list]
        self.assertTrue(any("could not be imported" in item for item in messages))
        self.assertFalse(any("verified and imported" in item for item in messages))


if __name__ == "__main__":
    unittest.main()


class RestoreChooserLocationTest(unittest.TestCase):
    """Kullanıcı KENDİ yedeğine uygulamanın içinden ulaşabilmeli.

    Yedekler `data_dir()/backups` altına yazılıyor; Windows'ta bu
    `%LOCALAPPDATA%\\Archlence\\backups`, yani `AppData`nın İÇİNDE. `AppData`
    gizli bir klasör ve Kivy'nin dosya seçicisi gizli girdileri listelemiyor
    (`show_hidden` kod tabanında hiçbir yerde set edilmiyor). Seçici ev
    dizininde açıldığı sürece o klasöre gezinmek imkânsız.

    Gerçek bir Windows 11 makinesinde ölçüldü: kullanıcı geri yükleme
    ekranından kendi yedeğini göremiyordu.
    """

    def test_chooser_opens_where_the_backups_actually_are(self):
        from mixins.migration_mixin import restore_chooser_path

        with tempfile.TemporaryDirectory() as temp:
            backups = Path(temp) / "backups"
            backups.mkdir()
            with mock.patch("utils.app_paths.data_dir", return_value=temp):
                self.assertEqual(restore_chooser_path(), str(backups))

    def test_chooser_falls_back_home_before_the_first_backup(self):
        """Yedek klasörü henüz yoksa var olmayan bir yola açılmamalı."""
        from mixins.migration_mixin import restore_chooser_path

        with tempfile.TemporaryDirectory() as temp:
            with mock.patch("utils.app_paths.data_dir", return_value=temp):
                self.assertEqual(
                    restore_chooser_path(), os.path.expanduser("~"))
