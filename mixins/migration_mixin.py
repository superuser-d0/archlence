import os
import threading

from kivy.clock import Clock
from kivymd.toast import toast


class MigrationMixin:
    """Ayarlar > Veri Yönetimi akışı: CSV dışa aktarma ve dosya seçicili içe
    aktarma. Ağır işler (şifre çözme/şifreleme + DB) diğer mixin'lerdeki
    kalıpla aynı şekilde arka plan thread'inde koşar, UI'ya Clock ile dönülür.
    """

    def export_data_csv(self):
        """Tüm verileri çözülmüş CSV olarak masaüstüne/uygulama dizinine yazar."""
        toast("Veriler dışa aktarılıyor...")

        def _worker():
            try:
                from services.migration_service import export_all_to_csv
                path, count = export_all_to_csv()
                Clock.schedule_once(
                    lambda dt: toast(f"{count} kayıt dışa aktarıldı:\n{path}"), 0)
            except Exception as e:
                print("CSV export error:", e)
                Clock.schedule_once(
                    lambda dt: toast("Dışa aktarma sırasında hata oluştu!"), 0)

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
                toast("Lütfen bir CSV dosyası seçin!")
                return
            self._import_dialog.dismiss()
            self._import_csv_file(selection[0])

        self._import_dialog = MDDialog(
            title="CSV'den İçe Aktar",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="İPTAL",
                             on_release=lambda x: self._import_dialog.dismiss()),
                MDFlatButton(
                    text="İÇE AKTAR",
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
        toast("İçe aktarılıyor, lütfen bekleyin...")

        def _worker():
            try:
                from services.migration_service import import_transactions_from_csv
                imported, skipped, net_delta = import_transactions_from_csv(path)

                def _done(dt):
                    if imported == 0:
                        toast("Dosyada içe aktarılabilir işlem bulunamadı!")
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
                    lambda dt: toast("İçe aktarma sırasında hata oluştu!"), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def show_data_privacy_dialog(self):
        """Veriler ve Gizlilik menüsünü diyalog olarak açar."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.list import MDList, OneLineIconListItem, IconLeftWidget
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.metrics import dp
        
        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(112))
        md_list = MDList()
        
        export_item = OneLineIconListItem(text="CSV Olarak Dışa Aktar")
        export_icon = IconLeftWidget(icon="file-export-outline")
        export_item.add_widget(export_icon)
        export_item.bind(on_release=lambda x: self._on_export_selected(self._data_privacy_dialog))
        
        import_item = OneLineIconListItem(text="CSV'den İçe Aktar")
        import_icon = IconLeftWidget(icon="file-import-outline")
        import_item.add_widget(import_icon)
        import_item.bind(on_release=lambda x: self._on_import_selected(self._data_privacy_dialog))
        
        md_list.add_widget(export_item)
        md_list.add_widget(import_item)
        content.add_widget(md_list)
        
        self._data_privacy_dialog = MDDialog(
            title="Veriler ve Gizlilik",
            type="custom",
            content_cls=content,
        )
        self._data_privacy_dialog.open()

    def _on_export_selected(self, dialog):
        dialog.dismiss()
        self.export_data_csv()

    def _on_import_selected(self, dialog):
        dialog.dismiss()
        self.show_import_csv_dialog()
