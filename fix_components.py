import re

with open('/home/cem/Documents/finora/ui/components.py', 'r') as f:
    content = f.read()

# Find the start of Builder.load_string('''\n<PremiumCreditCardWidget>:
# and replace the PremiumCreditCardWidget part.

new_kv = '''<PremiumCreditCardWidget>:
    size_hint: None, None
    size: "300dp", "420dp"
    orientation: "vertical"
    padding: "12dp"
    spacing: "12dp"
    elevation: 1
    radius: [dp(20)]
    style: "outlined"
    md_bg_color: app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else (1, 1, 1, 1)

    # Üst Kısım: Siyah Grafik Kart
    MDFloatLayout:
        size_hint_y: None
        height: "170dp"
        
        canvas.before:
            Color:
                rgba: 0.1, 0.11, 0.13, 1
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [dp(16)]
                
        MDLabel:
            text: "Finora"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            font_style: "H6"
            bold: True
            pos_hint: {"x": 0.08, "top": 0.90}
            adaptive_height: True
            
        MDIcon:
            icon: "contactless-payment"
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_size: "24sp"
            pos_hint: {"right": 0.92, "top": 0.90}
            
        MDLabel:
            text: root.masked_number
            theme_text_color: "Custom"
            text_color: 0.7, 0.7, 0.7, 1
            font_style: "Subtitle2"
            pos_hint: {"x": 0.08, "center_y": 0.45}
            adaptive_height: True
            
        MDLabel:
            text: root.card_name.upper()
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            font_style: "Caption"
            pos_hint: {"x": 0.08, "y": 0.15}
            adaptive_height: True

        MDLabel:
            text: "VISA"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            font_style: "H6"
            italic: True
            bold: True
            pos_hint: {"right": 0.92, "y": 0.12}
            halign: "right"
            adaptive_height: True

    # Orta Kısım: Başlık ve Rozet
    MDBoxLayout:
        size_hint_y: None
        height: "30dp"
        orientation: "horizontal"
        MDLabel:
            text: root.card_name
            font_style: "Subtitle1"
            bold: True
        MDCard:
            size_hint: None, None
            size: "80dp", "24dp"
            md_bg_color: 0.9, 0.9, 1, 1 if app.theme_cls.theme_style == "Light" else (0.2, 0.2, 0.3, 1)
            radius: [dp(8)]
            elevation: 0
            MDLabel:
                text: "Kredi Kartı"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 0.3, 0.3, 0.8, 1 if app.theme_cls.theme_style == "Light" else (0.6, 0.6, 1, 1)
                halign: "center"
                valign: "center"

    # Limit / Borç Bilgileri
    MDBoxLayout:
        size_hint_y: None
        height: "40dp"
        orientation: "horizontal"
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: "Kullanılabilir Limit"
                font_style: "Caption"
                theme_text_color: "Secondary"
            MDLabel:
                text: root.available_limit
                font_style: "Subtitle1"
                bold: True
        MDBoxLayout:
            orientation: "vertical"
            MDLabel:
                text: "Güncel Borç"
                font_style: "Caption"
                theme_text_color: "Secondary"
                halign: "right"
            MDLabel:
                text: root.current_debt
                font_style: "Subtitle1"
                bold: True
                theme_text_color: "Error"
                halign: "right"

    # Progress bar (mock)
    MDProgressBar:
        value: 40
        color: app.theme_cls.primary_color
        size_hint_y: None
        height: "4dp"

    Widget:
        size_hint_y: None
        height: "4dp"

    # Araçlar (Toggles)
    MDBoxLayout:
        size_hint_y: None
        height: "32dp"
        orientation: "horizontal"
        MDIcon:
            icon: "web"
            size_hint_x: None
            width: "32dp"
            theme_text_color: "Secondary"
        MDLabel:
            text: "İnternet Alışverişi"
            font_style: "Caption"
        MDSwitch:
            active: True
            width: "48dp"

    MDBoxLayout:
        size_hint_y: None
        height: "32dp"
        orientation: "horizontal"
        MDIcon:
            icon: "snowflake"
            size_hint_x: None
            width: "32dp"
            theme_text_color: "Secondary"
        MDLabel:
            text: "Kartı Dondur"
            font_style: "Caption"
        MDSwitch:
            active: False
            width: "48dp"

    Widget:
        size_hint_y: 1

    # Butonlar
    MDBoxLayout:
        size_hint_y: None
        height: "40dp"
        spacing: "8dp"
        orientation: "horizontal"
        MDFlatButton:
            text: "Ekstre"
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
        MDFlatButton:
            text: "Borç Öde"
            size_hint_x: 0.5
            line_color: app.theme_cls.primary_color
            theme_text_color: "Custom"
            text_color: app.theme_cls.primary_color
'''

# Use regex to replace the <PremiumCreditCardWidget> rule
# It starts at <PremiumCreditCardWidget>: and ends before <BentoAccountWidget>:
pattern = r'<PremiumCreditCardWidget>:.*?(?=<BentoAccountWidget>:)'
new_content = re.sub(pattern, new_kv, content, flags=re.DOTALL)

with open('/home/cem/Documents/finora/ui/components.py', 'w') as f:
    f.write(new_content)

