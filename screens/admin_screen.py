import os
import csv
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.toast import toast
from kivymd.app import MDApp
from kivy.clock import Clock
from kivy.metrics import dp


class AdminScreen(MDScreen):
    """Yönetici paneli: kayıt istatistikleri, CSV dışa aktarma ve fabrika sıfırlama.

    Bu ekrana yalnızca admin girişi (main.py check_login) sonrası ulaşılır.
    """

    def on_enter(self, *args):
        """Ekran her açıldığında işlem ve bütçe kayıt sayılarını DB'den okuyup gösterir."""
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM transactions")
            t_count = cursor.fetchone()[0]
        except Exception:
            t_count = 0
            
        try:
            cursor.execute("SELECT COUNT(*) FROM monthly_budget_plan")
            b_count = cursor.fetchone()[0]
        except Exception:
            b_count = 0
            
        conn.close()
        
        if 'stats_label' in self.ids:
            self.ids.stats_label.text = f"Toplam İşlem Kaydı: {t_count}\nToplam Bütçe Kalemi: {b_count}"

    def export_to_csv(self):
        """Tüm işlemleri Masaüstü'ne (yoksa Desktop, o da yoksa ev dizinine)
        export.csv olarak yazar. Tutar/açıklama kolonları şifreli haliyle çıkar."""
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM transactions")
            rows = cursor.fetchall()
            
            if not rows:
                toast("Dışa aktarılacak kayıt bulunamadı.")
                return
                
            col_names = [description[0] for description in cursor.description]
            
            home_dir = os.path.expanduser("~")
            desk_dir = os.path.join(home_dir, "Masaüstü")
            if not os.path.exists(desk_dir):
                desk_dir = os.path.join(home_dir, "Desktop")
                if not os.path.exists(desk_dir):
                    desk_dir = home_dir
            
            filepath = os.path.join(desk_dir, "export.csv")
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                writer.writerows(rows)
            toast(f"Dışa aktarıldı: {filepath}")
        except Exception as e:
            toast(f"Hata: {e}")
        finally:
            conn.close()

    def confirm_factory_reset(self):
        self.reset_dialog = MDDialog(
            title="Sistemi Sıfırla",
            text="Tüm veriler silinecek! Onaylıyor musunuz?",
            buttons=[
                MDFlatButton(text="İPTAL", on_release=lambda x: self.reset_dialog.dismiss()),
                MDRaisedButton(text="SIFIRLA", md_bg_color=(0.9, 0.2, 0.2, 1), on_release=self.factory_reset),
            ],
        )
        self.reset_dialog.open()

    def factory_reset(self, *args):
        """Onaylanan sıfırlama: işlem ve bütçe tablolarını boşaltır, admin oturumunu kapatır.
        Kategoriler ve hesap tanımları silinmez (init_db onları yeniden oluşturmaz)."""
        self.reset_dialog.dismiss()
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM transactions")
            cursor.execute("DELETE FROM monthly_budget_plan")
            # Hesaplar Kopuk düzeltmesi: işlemler silinince accounts.balance de
            # sıfırlanır, yoksa tablo artık karşılığı olmayan eski bir bakiyede kalır.
            cursor.execute("UPDATE accounts SET balance = 0")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

        toast("Sistem sıfırlandı!")

        app = MDApp.get_running_app()
        if app:
            app.admin_logout() # type: ignore


