import os
import csv
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.toast import toast
from kivy.clock import Clock
from kivy.metrics import dp


class AdminScreen(MDScreen):
    def on_enter(self, *args):
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
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM transactions")
            rows = cursor.fetchall()
            
            if not rows:
                from kivymd.toast import toast
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
                
            from kivymd.toast import toast
            toast(f"Dışa aktarıldı: {filepath}")
        except Exception as e:
            from kivymd.toast import toast
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
        self.reset_dialog.dismiss()
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM transactions")
            cursor.execute("DELETE FROM monthly_budget_plan")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
            
        from kivymd.toast import toast
        toast("Sistem sıfırlandı!")
        
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        app.admin_logout()


