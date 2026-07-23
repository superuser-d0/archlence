"""Aylık bütçe planlayıcı mixin'i.

monthly_budget_plan tablosu üzerinde çalışan tüm akış: ay seçici butonları,
planlayıcı diyaloğu, kalem ekleme/düzenleme/silme ve seçili ayın harcanabilir
limit projeksiyonu. main.py'deki FinoraApp gövdesinden taşındı; davranış
değişmedi. Bütçe tutarları şifresiz saklanır (yalnızca transactions/assets/
active_debts tutarları şifrelenir), bu yüzden burada encrypt kullanılmaz;
decrypt yalnızca projeksiyonun okuduğu eski şifreli kayıtlar için gerekir.
"""
import datetime

from kivy.metrics import dp
from kivymd.toast import toast
from kivymd.uix.button import MDRaisedButton

from utils.crypto import decrypt
from ui.i18n import tr as _t

SECRET_KEY = 'finora_secure_2026'


class BudgetMixin:
    def setup_dynamic_months(self):
        """Uygulama açılışında, içinde bulunulan aydan yıl sonuna kadar olan ayları
        gösteren yatay buton listesini (ay seçici) oluşturur.
        """
        import datetime
        MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        
        current_month_index = datetime.datetime.now().month  
        self.active_budget_month = current_month_index
        
        container = getattr(self.root.ids, 'month_selector_container', None)
        if container:
            container.clear_widgets()
            
            from kivymd.uix.button import MDRoundFlatButton
            for i in range(current_month_index, 13):
                month_name = MONTHS[i - 1]
                btn = MDRoundFlatButton(text=_t(month_name))
                btn.bind(on_release=lambda instance, m_idx=i: self.change_budget_month(m_idx))
                container.add_widget(btn)

    def change_budget_month(self, month_index):
        """Ay seçiciden farklı bir ay tıklandığında aktif ayı günceller ve listeyi/projeksiyonu yeniler."""
        self.active_budget_month = month_index
        self.load_budget_list()
        self.generate_next_month_projection()

    def generate_next_month_projection(self):
        """Seçili ay için gelir-gider farkını (harcanabilir limit) hesaplar ve arayüze tavsiye metniyle birlikte yansıtır."""
        import datetime
        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)
        
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. SADECE Bütçe Planlayıcı tablosundan (monthly_budget_plan) ve SEÇİLİ AY'a ait verileri çek
        try:
            cursor.execute("SELECT type, amount FROM monthly_budget_plan WHERE target_month = ?", (target_month,))
        except Exception:
            cursor.execute("SELECT type, amount FROM monthly_budget_plan")
            
        rows = cursor.fetchall()
        planlanan_gelir = 0.0
        planlanan_gider = 0.0
        for t_type, amount in rows:
            # save_budget_item tutarları düz float yazar; yalnızca çok eski
            # kayıtlar şifreli olabilir. Önce düz sayı dene, olmazsa decrypt —
            # eski sıralama (önce decrypt) düz kayıtları 0 sayıp limiti
            # yanlış hesaplıyordu.
            try:
                val = float(amount)
            except (TypeError, ValueError):
                try:
                    val = float(decrypt(str(amount), SECRET_KEY))
                except Exception:
                    val = 0.0
            if t_type == "Gelir" or t_type == "income": planlanan_gelir += val
            elif t_type == "Gider" or t_type == "expense": planlanan_gider += val
        conn.close()
        
        # 2. İZOLE HESAPLAMA (Geçmiş varlıklar veya ekstra harcamalar dahil edilmez)
        harcanabilir_limit = planlanan_gelir - planlanan_gider
        
        # 3. SIFIRIN ALTI KONTROLÜ VE TAVSİYE MANTIĞI
        advice_text = _t("Bütçeniz dengede.")
        icon = "check-circle"
        color = (0.18, 0.8, 0.25, 1) # Yeşil
        
        if harcanabilir_limit < 0:
            advice_text = _t("Dikkat: Planlanan giderler, gelirlerinizi aşıyor. Bütçeniz eksiye düşecek!")
            icon = "close-circle"
            color = (0.9, 0.2, 0.2, 1) # Kırmızı
            
        elif harcanabilir_limit == 0:
            advice_text = _t("Dikkat: Gelir ve gideriniz başa baş. Bütçenizde hiç esneme payı yok.")
            icon = "alert"
            color = (0.95, 0.6, 0.1, 1) # Turuncu
            
        # Arayüz (UI) Güncellemesi
        if hasattr(self.root.ids, 'projection_label'):
            formatted_limit = f"{harcanabilir_limit:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                      "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            try:
                ay_ismi = MONTHS[target_month - 1]
            except:
                ay_ismi = "Ocak"
            self.root.ids.projection_label.text = _t(f"{ay_ismi} Ayı Harcama Limitiniz: {formatted_limit}\n\n{advice_text}")
            self.root.ids.projection_icon.icon = icon
            self.root.ids.projection_icon.text_color = color
            
        return {
            "harcanabilir_limit": harcanabilir_limit,
            "tavsiye": advice_text,
            "tavsiye_ikonu": icon
        }

    def show_budget_planner(self):
        """Bütçe planlama arayüzünü (kalem ekleme/düzenleme diyaloğu) açar."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDRaisedButton, MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout
        from kivymd.uix.selectioncontrol import MDSwitch
        from kivymd.uix.label import MDLabel
        from kivy.core.window import Window
        import datetime

        # ── Outer container: a ScrollView so nothing ever squishes ──────────
        outer_scroll = ScrollView(
            size_hint_y=None,
            height=Window.height * 0.65,
            do_scroll_x=False,
            do_scroll_y=True,
        )

        form_layout = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(25),
            padding=[dp(15), dp(30), dp(15), dp(15)],
        )

        # ── Inputs ───────────────────────────────────────────────────────────
        self.bp_name_input = MDTextField(
            hint_text=_t("Kalem Adı (Örn: Maaş, Kira)"),
            size_hint_y=None,
            height=dp(68),
        )
        self.bp_amount_input = MDTextField(
            hint_text=_t("Tutar (₺)"),
            input_filter="float",
            size_hint_y=None,
            height=dp(68),
        )

        # ── Gelir / Gider segmented control ─────────────────────────────────
        self.bp_type_segment = MDSegmentedControl(size_hint_x=1)
        self.bp_type_segment.add_widget(MDSegmentedControlItem(text=_t("Gelir")))
        self.bp_type_segment.add_widget(MDSegmentedControlItem(text=_t("Gider")))
        self.bp_selected_type = "income"

        def on_seg_active(seg, item):
            self.bp_selected_type = "expense" if item.text == _t("Gider") else "income"

        self.bp_type_segment.bind(on_active=on_seg_active)

        # ── Switch row ───────────────────────────────────────────────────────
        switch_layout = MDBoxLayout(
    orientation="horizontal", 
    size_hint_y=None, 
    height=dp(48), 
    spacing=dp(10),
    padding=[dp(5), 0, dp(45), 0] # Shifted left by reducing left padding and increasing right padding
)
        switch_label = MDLabel(
            text=_t("Mevcut kalemi diğer aylara da uygula"),
            theme_text_color="Primary",
            valign="center",
            halign="left",
            size_hint_x=1,
        )
        self.bp_repeat_switch = MDSwitch(
            pos_hint={"center_y": 0.5},
            active=False,
            size_hint_x=None,
            width=dp(48),
        )
        switch_layout.add_widget(switch_label)
        switch_layout.add_widget(self.bp_repeat_switch)

        # ── Month grid (3 columns → wraps cleanly, never overflows) ─────────
        self.months_grid = GridLayout(
            cols=3,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(0),
            opacity=0,
        )
        upcoming_months = ["Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        for month_name in upcoming_months:
            btn = MDRaisedButton(
                text=_t(month_name),
                size_hint=(1, None),
                height=dp(36),
                md_bg_color=self.theme_cls.primary_color,
                text_color=(1, 1, 1, 1),
                elevation=0,
            )
            btn.month_index = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                               "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"].index(month_name) + 1
            btn.is_selected = False
            btn.bind(on_release=self.toggle_custom_month_button)
            self.months_grid.add_widget(btn)

        def on_switch_active(instance, value):
            if value:
                # 2 rows of 36dp buttons + 8dp spacing + 8dp padding
                self.months_grid.height = dp(80)
                self.months_grid.opacity = 1
            else:
                self.months_grid.height = dp(0)
                self.months_grid.opacity = 0

        self.bp_repeat_switch.bind(active=on_switch_active)

        # ── List area (items populated by load_budget_list) ──────────────────
        self.bp_list_container = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(4),
        )

        # ── Assemble form ────────────────────────────────────────────────────
        form_layout.add_widget(self.bp_name_input)
        form_layout.add_widget(self.bp_amount_input)
        form_layout.add_widget(self.bp_type_segment)
        form_layout.add_widget(switch_layout)
        form_layout.add_widget(self.months_grid)
        form_layout.add_widget(self.bp_list_container)

        outer_scroll.add_widget(form_layout)

        self.bp_dialog = MDDialog(
            title=_t("Bütçe Planlayıcı"),
            type="custom",
            content_cls=outer_scroll,
            buttons=[
                MDFlatButton(text=_t("KAPAT"), on_release=lambda x: self.bp_dialog.dismiss()),
                MDRaisedButton(text=_t("EKLE"), on_release=self.save_budget_item),
            ],
        )
        self.bp_dialog.open()
        self.load_budget_list()

    def load_budget_list(self):
        """Seçili aya ait planlanan gelir ve gider kalemlerini veritabanından çekerek listeyi günceller."""
        # Works with both the new bp_list_container and the old bp_list (MDList)
        container = getattr(self, "bp_list_container", getattr(self, "bp_list", None))
        if container is None:
            return

        container.clear_widgets()

        from database.db import get_connection
        from kivymd.uix.button import MDIconButton
        from kivymd.uix.label import MDLabel
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivy.uix.widget import Widget
        import datetime

        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, type, name, amount FROM monthly_budget_plan WHERE target_month = ?",
                (target_month,),
            )
        except Exception:
            cursor.execute("SELECT id, type, name, amount FROM monthly_budget_plan")

        rows = cursor.fetchall()
        conn.close()

        for item_id, item_type, name, amount in rows:
            type_tr = _t("Gelir" if item_type == "income" else "Gider")
            amount_str = f"{amount:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

            # ── Row: [icon | text column | spacer | edit btn | delete btn] ──
            row = MDBoxLayout(
                orientation="horizontal",
                adaptive_height=True,
                spacing=dp(8),
                padding=[dp(12), dp(8), dp(8), dp(8)],
                size_hint_y=None,
                height=dp(56),
            )

            # Left icon
            left_icon = MDIconButton(
                icon="cash" if item_type == "income" else "cart",
                theme_text_color="Custom",
                text_color=(0.12, 0.53, 0.53, 1),
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(40), dp(40)),
            )

            # Text column
            text_col = MDBoxLayout(
                orientation="vertical",
                adaptive_height=True,
                size_hint_x=1,
                pos_hint={"center_y": 0.5},
            )
            name_lbl = MDLabel(
                text=name,
                adaptive_height=True,
                font_style="Body1",
            )
            sub_lbl = MDLabel(
                text=f"{type_tr} | {amount_str}",
                adaptive_height=True,
                font_style="Caption",
                theme_text_color="Secondary",
            )
            text_col.add_widget(name_lbl)
            text_col.add_widget(sub_lbl)

            # Edit button
            edit_btn = MDIconButton(
                icon="pencil",
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                on_release=lambda x, iid=item_id: self.edit_budget_item(iid),
            )

            # Delete button
            delete_btn = MDIconButton(
                icon="trash-can",
                theme_text_color="Custom",
                text_color=(0.9, 0.2, 0.2, 1),
                pos_hint={"center_y": 0.5},
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                on_release=lambda x, iid=item_id: self.delete_budget_item(iid),
            )

            row.add_widget(left_icon)
            row.add_widget(text_col)
            row.add_widget(edit_btn)
            row.add_widget(delete_btn)

            container.add_widget(row)
            # Simple separator line compatible with KivyMD 1.2.0
            sep = Widget(size_hint_y=None, height=dp(1))
            container.add_widget(sep)

    def save_budget_item(self, *args):
        """Diyalogdan girilen verileri (yeni kalem veya düzenleme) veritabanına kaydeder.
        'Diğer aylara da uygula' açıksa, seçili aylara da kopyalar.
        """
        # Strip ALL invisible characters — prevents the Admin[] artifact
        name = self.bp_name_input.text.strip().replace('\n', '').replace('\r', '')
        if not name:
            toast(_t("Kalem adı boş olamaz!"))
            return
        try:
            amount = float(self.bp_amount_input.text)
        except ValueError:
            toast(_t("Geçerli bir tutar girin!"))
            return

        is_propagate_active = self.bp_repeat_switch.active
        target_month = getattr(self, "active_budget_month", datetime.datetime.now().month)

        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("ALTER TABLE monthly_budget_plan ADD COLUMN target_month INTEGER DEFAULT 1")
        except Exception:
            pass

        if getattr(self, "editing_item_id", None):
            cursor.execute(
                """UPDATE monthly_budget_plan
                   SET type = ?, name = ?, amount = ?, target_month = ?
                   WHERE id = ?""",
                (self.bp_selected_type, name, amount, target_month, self.editing_item_id),
            )
            self.editing_item_id = None
        else:
            cursor.execute(
                """INSERT INTO monthly_budget_plan (type, name, amount, target_month)
                   VALUES (?, ?, ?, ?)""",
                (self.bp_selected_type, name, amount, target_month),
            )

        # Propagate to selected months
        if is_propagate_active:
            MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                      "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            for child in self.months_grid.children:
                if isinstance(child, MDRaisedButton) and getattr(child, "is_selected", False):
                    m_int = getattr(child, "month_index", None)
                    if m_int is None:
                        continue
                    cursor.execute(
                        """INSERT INTO monthly_budget_plan (type, name, amount, target_month)
                           VALUES (?, ?, ?, ?)""",
                        (self.bp_selected_type, name, amount, m_int),
                    )

        conn.commit()
        conn.close()

        self.bp_name_input.text = ""
        self.bp_amount_input.text = ""
        self.load_budget_list()
        self.generate_next_month_projection()
        
    def toggle_custom_month_button(self, btn):
        """Çoklu ay seçimi sırasında (kalem kopyalarken) ay butonlarının basılı/basılmamış durumunu değiştirir."""
        if not getattr(btn, 'is_selected', False):
            btn.is_selected = True
            btn.md_bg_color = self.theme_cls.primary_dark  # seçili: temanın koyu tonu
        else:
            btn.is_selected = False
            btn.md_bg_color = self.theme_cls.primary_color  # seçili değil

    def delete_budget_item(self, item_id):
        """Verilen ID'ye sahip bütçe kalemini siler ve listeyi/projeksiyonu günceller."""
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monthly_budget_plan WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        self.load_budget_list()
        self.generate_next_month_projection()
        toast(_t("Kalem silindi."))

    def edit_budget_item(self, item_id):
        """Silme işleminin yanındaki düzenle butonuna tıklandığında,
        seçili bütçe kaleminin bilgilerini form alanlarına doldurur."""
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT type, name, amount FROM monthly_budget_plan WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.editing_item_id = item_id
            self.bp_selected_type = row[0]
            self.bp_name_input.text = row[1]
            self.bp_amount_input.text = str(row[2])
