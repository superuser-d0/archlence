import os
import threading
from datetime import datetime
from pathlib import Path

from kivy.clock import Clock
from kivymd.toast import toast
from ui.i18n import tr as _t


class MigrationMixin:
    """Ayarlar > Veri Yönetimi akışı: CSV dışa aktarma ve dosya seçicili içe
    aktarma. Ağır işler (şifre çözme/şifreleme + DB) diğer mixin'lerdeki
    kalıpla aynı şekilde arka plan thread'inde koşar, UI'ya Clock ile dönülür.
    """

    def export_data_csv(self):
        """Tüm verileri çözülmüş CSV olarak masaüstüne/uygulama dizinine yazar."""
        toast(_t("Veriler dışa aktarılıyor..."))

        def _worker():
            try:
                from services.migration_service import export_all_to_csv
                path, count = export_all_to_csv()
                Clock.schedule_once(
                    lambda dt: toast(_t(f"{count} kayıt dışa aktarıldı:\n{path}")), 0)
            except Exception as e:
                print("CSV export error:", e)
                Clock.schedule_once(
                    lambda dt: toast(_t("Dışa aktarma sırasında hata oluştu!")), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def show_import_csv_dialog(self):
        """CSV seçtiren dosya seçici diyaloğunu açar."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.uix.filechooser import FileChooserListView

        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height="420dp",
        )
        chooser = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.csv", "*.CSV"],
        )
        content.add_widget(chooser)

        def _confirm(instance):
            selection = chooser.selection
            if not selection:
                toast(_t("Lütfen bir CSV dosyası seçin!"))
                return
            self._import_dialog.dismiss()
            self._import_csv_file(selection[0])

        self._import_dialog = MDDialog(
            title=_t("CSV'den İçe Aktar"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text=_t("İPTAL"),
                             on_release=lambda x: self._import_dialog.dismiss()),
                MDFlatButton(
                    text=_t("İÇE AKTAR"),
                    theme_text_color="Custom",
                    text_color=(0.08, 0.72, 0.42, 1),
                    on_release=_confirm,
                ),
            ],
        )
        self._import_dialog.open()

    def _import_csv_file(self, path):
        """Seçilen CSV'yi arka planda içeri alır; bitince listeleri ve
        bakiyeyi tazeler."""
        toast(_t("İçe aktarılıyor, lütfen bekleyin..."))

        def _worker():
            try:
                from services.migration_service import import_transactions_from_csv
                imported, skipped, net_delta = import_transactions_from_csv(path)

                def _done(dt):
                    if imported == 0:
                        toast(_t("Dosyada içe aktarılabilir işlem bulunamadı!"))
                        return
                    sign = "+" if net_delta >= 0 else "-"
                    msg = f"{imported} işlem içe aktarıldı (bakiye etkisi: {sign}₺{abs(net_delta):,.2f})"
                    if skipped:
                        msg += f", {skipped} satır atlandı"
                    toast(msg)
                    # Bakiye, grafikler ve işlem listesi yeni kayıtları yansıtsın
                    self.refresh_dashboard_data()
                    self.safe_refresh_charts()
                    if hasattr(self, "generate_financial_advice"):
                        self.generate_financial_advice()

                Clock.schedule_once(_done, 0)
            except Exception as e:
                print("CSV import error:", e)
                Clock.schedule_once(
                    lambda dt: toast(_t("İçe aktarma sırasında hata oluştu!")), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def show_data_privacy_dialog(self):
        """Veriler ve Gizlilik menüsünü diyalog olarak açar."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.list import MDList, OneLineIconListItem, IconLeftWidget
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.metrics import dp
        
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(448)
        )
        md_list = MDList()
        
        export_item = OneLineIconListItem(text=_t("CSV Olarak Dışa Aktar"))
        export_icon = IconLeftWidget(icon="file-export-outline")
        export_item.add_widget(export_icon)
        export_item.bind(on_release=lambda x: self._on_export_selected(self._data_privacy_dialog))
        
        import_item = OneLineIconListItem(text=_t("CSV'den İçe Aktar"))
        import_icon = IconLeftWidget(icon="file-import-outline")
        import_item.add_widget(import_icon)
        import_item.bind(on_release=lambda x: self._on_import_selected(self._data_privacy_dialog))
        
        md_list.add_widget(export_item)
        md_list.add_widget(import_item)

        backup_item = OneLineIconListItem(text=_t("Güvenli Backup Oluştur"))
        backup_item.add_widget(IconLeftWidget(icon="backup-restore"))
        backup_item.bind(
            on_release=lambda _x: self._on_backup_selected(
                self._data_privacy_dialog
            )
        )
        restore_item = OneLineIconListItem(text=_t("Backup Geri Yükle"))
        restore_item.add_widget(IconLeftWidget(icon="database-import-outline"))
        restore_item.bind(
            on_release=lambda _x: self._on_restore_selected(
                self._data_privacy_dialog
            )
        )
        migration_item = OneLineIconListItem(
            text=_t("Legacy Şifrelemeyi Taşı")
        )
        migration_item.add_widget(IconLeftWidget(icon="shield-sync-outline"))
        migration_item.bind(
            on_release=lambda _x: self._on_migration_selected(
                self._data_privacy_dialog
            )
        )
        recovery_export_item = OneLineIconListItem(
            text=_t("Anahtar Kurtarma Paketi Oluştur")
        )
        recovery_export_item.add_widget(IconLeftWidget(icon="key-arrow-right"))
        recovery_export_item.bind(
            on_release=lambda _x: self._on_recovery_export_selected(
                self._data_privacy_dialog
            )
        )
        recovery_import_item = OneLineIconListItem(
            text=_t("Anahtar Kurtarma Paketi İçe Aktar")
        )
        recovery_import_item.add_widget(IconLeftWidget(icon="key-arrow-left"))
        recovery_import_item.bind(
            on_release=lambda _x: self._on_recovery_import_selected(
                self._data_privacy_dialog
            )
        )
        rotation_item = OneLineIconListItem(
            text=_t("Şifreleme Anahtarını Döndür")
        )
        rotation_item.add_widget(IconLeftWidget(icon="key-sync"))
        rotation_item.bind(
            on_release=lambda _x: self._on_key_rotation_selected(
                self._data_privacy_dialog
            )
        )

        md_list.add_widget(backup_item)
        md_list.add_widget(restore_item)
        md_list.add_widget(migration_item)
        md_list.add_widget(recovery_export_item)
        md_list.add_widget(recovery_import_item)
        md_list.add_widget(rotation_item)
        content.add_widget(md_list)
        
        self._data_privacy_dialog = MDDialog(
            title=_t("Veriler ve Gizlilik"),
            type="custom",
            content_cls=content,
        )
        self._data_privacy_dialog.open()

    def _on_recovery_export_selected(self, dialog):
        dialog.dismiss()
        self._password_dialog(
            _t("Anahtar Kurtarma Paketi"),
            _t("Paket ham anahtar içermez; parolayı ayrı bir yerde saklayın."),
            self._export_key_recovery,
        )

    def _export_key_recovery(self, passphrase):
        from utils.app_paths import data_dir

        destination = (
            Path(data_dir()) / "backups"
            / f"key-recovery-{datetime.now():%Y%m%d-%H%M%S}.json"
        )

        def work(_cancel):
            from services.key_recovery_service import export_recovery_package
            from utils.crypto import active_key_provider

            return export_recovery_package(
                destination, passphrase, active_key_provider()
            )

        self.background_tasks.submit(
            "key-recovery-export",
            work,
            on_success=lambda path: toast(
                _t(f"Kurtarma paketi doğrulandı:\n{path}")
            ),
            on_error=lambda exc: self._secure_operation_error(
                "Kurtarma paketi oluşturulamadı", exc
            ),
            replace=False,
        )

    def _on_recovery_import_selected(self, dialog):
        dialog.dismiss()
        self._show_recovery_import_dialog()

    def _show_recovery_import_dialog(self):
        from kivy.metrics import dp
        from kivy.uix.filechooser import FileChooserListView
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.dialog import MDDialog

        chooser = FileChooserListView(
            path=os.path.expanduser("~"), filters=["*.json"]
        )
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(420)
        )
        content.add_widget(chooser)

        def choose(_button):
            if not chooser.selection:
                toast(_t("Lütfen bir kurtarma paketi seçin!"))
                return
            selected = chooser.selection[0]
            file_dialog.dismiss()
            self._password_dialog(
                _t("Anahtar Kurtarma Paketi"),
                _t("Paket veritabanını açamıyorsa anahtar değiştirilmeyecek."),
                lambda password: self._import_key_recovery(
                    selected, password
                ),
            )

        file_dialog = MDDialog(
            title=_t("Kurtarma Paketi Seç"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("İPTAL"),
                    on_release=lambda _x: file_dialog.dismiss(),
                ),
                MDRaisedButton(text=_t("SEÇ"), on_release=choose),
            ],
        )
        file_dialog.open()

    def _import_key_recovery(self, package, passphrase):
        def work(_cancel):
            from database.db import DB_NAME
            from services.key_recovery_service import import_recovery_package
            from utils.crypto import active_key_provider

            return import_recovery_package(
                package, passphrase, active_key_provider(), DB_NAME
            )

        self.background_tasks.submit(
            "key-recovery-import",
            work,
            on_success=lambda _result: toast(_t(
                "Kurtarma anahtarı veritabanıyla doğrulandı ve içe aktarıldı."
            )),
            on_error=lambda exc: self._secure_operation_error(
                "Kurtarma paketi içe aktarılamadı", exc
            ),
            replace=False,
        )

    def _on_key_rotation_selected(self, dialog):
        dialog.dismiss()
        self._password_dialog(
            _t("Şifreleme Anahtarını Döndür"),
            _t("Önce doğrulanmış backup alınır; hata olursa veritabanı "
               "ve anahtar birlikte geri alınır."),
            self._rotate_encryption_key,
        )

    def _rotate_encryption_key(self, passphrase):
        import hashlib
        import uuid
        from database.db import DB_NAME
        from utils.app_paths import data_dir
        from utils.crypto import active_key_provider

        provider = active_key_provider()
        current = provider.load_key()
        if current is None:
            self._secure_operation_error(
                "Anahtar rotasyonu başlatılamadı",
                RuntimeError("Aktif anahtar bulunamadı."),
            )
            return
        backup = (
            Path(data_dir()) / "backups"
            / f"pre-rotation-{datetime.now():%Y%m%d-%H%M%S}.backup"
        )
        expected = hashlib.sha256(current).hexdigest()

        def work(_cancel):
            from services.key_recovery_service import rotate_encryption_key

            return rotate_encryption_key(
                db_path=DB_NAME,
                provider=provider,
                backup_path=backup,
                backup_passphrase=passphrase,
                rotation_id=str(uuid.uuid4()),
                expected_fingerprint=expected,
            )

        self.background_tasks.submit(
            "key-rotation",
            work,
            on_success=lambda result: toast(_t(
                f"Anahtar rotasyonu tamamlandı: "
                f"{result['rotated_fields']} alan. Backup: "
                f"{result['backup_path']}"
            )),
            on_error=lambda exc: self._secure_operation_error(
                "Anahtar rotasyonu geri alındı", exc
            ),
            replace=False,
        )

    def _on_export_selected(self, dialog):
        dialog.dismiss()
        self.export_data_csv()

    def _on_import_selected(self, dialog):
        dialog.dismiss()
        self.show_import_csv_dialog()

    def _password_dialog(self, title, explanation, callback):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.textfield import MDTextField
        from kivy.metrics import dp

        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(150),
            spacing=dp(8),
        )
        content.add_widget(MDLabel(
            text=explanation,
            theme_text_color="Secondary",
            font_style="Caption",
        ))
        password = MDTextField(
            hint_text=_t("Kurtarma Parolası (en az 12 karakter)"),
            password=True,
            multiline=False,
        )
        content.add_widget(password)

        def confirm(_button):
            value = password.text
            if len(value) < 12:
                toast(_t("Kurtarma parolası en az 12 karakter olmalıdır."))
                return
            dialog.dismiss()
            callback(value)

        dialog = MDDialog(
            title=title,
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("İPTAL"),
                    on_release=lambda _x: dialog.dismiss(),
                ),
                MDRaisedButton(text=_t("DEVAM"), on_release=confirm),
            ],
        )
        dialog.open()

    def _on_backup_selected(self, dialog):
        dialog.dismiss()
        self._password_dialog(
            _t("Güvenli Backup"),
            _t("Parola uygulama tarafından saklanmaz. Kaybedilirse backup açılamaz."),
            self._create_verified_backup,
        )

    def _create_verified_backup(self, passphrase):
        from utils.app_paths import data_dir

        destination = (
            Path(data_dir()) / "backups"
            / f"archlence-{datetime.now():%Y%m%d-%H%M%S}.backup"
        )
        toast(_t("Backup oluşturuluyor ve doğrulanıyor…"))

        def work(_cancel):
            from services.backup_service import create_backup

            return create_backup(destination, passphrase)

        self.background_tasks.submit(
            "secure-backup",
            work,
            on_success=lambda result: toast(
                _t(f"Backup doğrulandı:\n{result['path']}")
            ),
            on_error=lambda exc: self._secure_operation_error(
                "Backup oluşturulamadı", exc
            ),
            replace=False,
        )

    def _on_restore_selected(self, dialog):
        dialog.dismiss()
        self.show_restore_backup_dialog()

    def show_restore_backup_dialog(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.uix.filechooser import FileChooserListView
        from kivy.metrics import dp

        chooser = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=["*.backup", "*.archlence-backup", "*.zip"],
        )
        content = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(420)
        )
        content.add_widget(chooser)

        def choose(_button):
            if not chooser.selection:
                toast(_t("Lütfen bir backup dosyası seçin!"))
                return
            selected = chooser.selection[0]
            file_dialog.dismiss()
            self._password_dialog(
                _t("Backup Geri Yükle"),
                _t("Mevcut verinin güvenlik backup'ı alınacak. Doğrulama "
                   "başarısızsa hiçbir dosya değiştirilmeyecek."),
                lambda password: self._restore_verified_backup(
                    selected, password
                ),
            )

        file_dialog = MDDialog(
            title=_t("Backup Dosyası Seç"),
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text=_t("İPTAL"),
                    on_release=lambda _x: file_dialog.dismiss(),
                ),
                MDRaisedButton(text=_t("SEÇ"), on_release=choose),
            ],
        )
        file_dialog.open()

    def _restore_verified_backup(self, package, passphrase):
        toast(_t("Backup doğrulanıyor; mevcut veri güvenceye alınıyor…"))

        def work(_cancel):
            from services.backup_service import restore_backup

            return restore_backup(package, passphrase)

        def success(result):
            toast(_t(
                "Restore tamamlandı. Güvenlik backup'ı:\n"
                f"{result['safety_backup_path']}"
            ))
            self.refresh_dashboard_data()

        self.background_tasks.submit(
            "secure-restore",
            work,
            on_success=success,
            on_error=lambda exc: self._secure_operation_error(
                "Restore başarısız; mevcut veri korundu", exc
            ),
            replace=False,
        )

    def _on_migration_selected(self, dialog):
        dialog.dismiss()
        from services.crypto_migration_service import inspect_legacy_encryption
        from database.db import DB_NAME

        plan = inspect_legacy_encryption(db_path=DB_NAME)
        if plan.legacy_fields == 0:
            toast(_t("Taşınacak legacy şifreli kayıt bulunamadı."))
            return
        self._password_dialog(
            _t("Legacy Şifreleme Migration'ı"),
            _t(
                f"{plan.legacy_fields} alan / {plan.affected_records} kayıt "
                "taşınacak. Önce doğrulanmış backup alınır; hata olursa "
                "transaction geri alınır."
            ),
            lambda password: self._run_legacy_migration(password),
        )

    def _run_legacy_migration(self, passphrase):
        from utils.app_paths import data_dir

        backup = (
            Path(data_dir()) / "backups"
            / f"pre-migration-{datetime.now():%Y%m%d-%H%M%S}.backup"
        )
        toast(_t("Migration başladı; veriler transaction içinde taşınıyor…"))

        def work(_cancel):
            from services.crypto_migration_service import (
                migrate_legacy_encryption,
            )

            return migrate_legacy_encryption(passphrase, backup)

        self.background_tasks.submit(
            "legacy-migration",
            work,
            on_success=lambda result: toast(_t(
                f"Migration tamamlandı: {result['migrated_fields']} alan. "
                f"Backup: {result['backup_path']}"
            )),
            on_error=lambda exc: self._secure_operation_error(
                "Migration geri alındı", exc
            ),
            replace=False,
        )

    @staticmethod
    def _secure_operation_error(message, exc):
        from utils.logging_config import get_logger

        get_logger().error(
            "%s", message,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        toast(_t(f"{message}. Ayrıntılar uygulama loguna kaydedildi."))
