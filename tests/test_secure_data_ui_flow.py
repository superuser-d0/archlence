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
            "doğrulandı" in str(call.args[0])
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
        self.assertTrue(any("mevcut veri korundu" in item for item in messages))
        self.assertFalse(any("Restore tamamlandı" in item for item in messages))

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
            "4 alan" in str(call.args[0])
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
            "doğrulandı" in str(call.args[0])
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
        self.assertTrue(any("içe aktarılamadı" in item for item in messages))
        self.assertFalse(any("içe aktarıldı" in item for item in messages))


if __name__ == "__main__":
    unittest.main()
