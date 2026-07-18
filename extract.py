import re

with open('main.py', 'r') as f:
    lines = f.readlines()

def get_class(class_name, lines):
    start = -1
    for i, line in enumerate(lines):
        if line.startswith(f"class {class_name}("):
            start = i
            break
    if start == -1: return []
    
    end = start + 1
    while end < len(lines):
        if re.match(r'^(class|def) ', lines[end]) or (lines[end].strip() and not lines[end].startswith(' ') and not lines[end].startswith('#')):
            # We reached the next top-level block
            break
        end += 1
    return lines[start:end]

charts = ["CurvedTrendChart", "DashboardChartManager", "HorizontalBarChart", "LiquidWaveWidget", "PieChart"]
components = ["CategorySettingItem", "RightButtonsContainer", "BudgetListItem", "LegendItem", "LegendWidget"]
screens = ["AdminScreen"]

def write_out(filename, classes, imports):
    with open(filename, 'w') as f:
        f.write(imports)
        for c in classes:
            code = get_class(c, lines)
            f.writelines(code)
            f.write("\n")

charts_imports = """import math
from math import sin, cos, radians
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import NumericProperty, ColorProperty
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, RoundedRectangle, Ellipse, Mesh, Rectangle
from kivy.core.text import Label as CoreLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.app import MDApp
from services.transaction_service import TransactionService

# Forward import
from ui.components import LegendWidget

"""

comp_imports = """from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import TwoLineAvatarIconListItem, IRightBodyTouch
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.metrics import dp

"""

admin_imports = """import os
import csv
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.toast import toast
from kivy.clock import Clock
from kivy.metrics import dp
from database.db import connect_db
from database.init_db import create_tables

"""

import os
os.makedirs('ui', exist_ok=True)
os.makedirs('screens', exist_ok=True)

write_out('ui/charts.py', charts, charts_imports)
write_out('ui/components.py', components, comp_imports)
write_out('screens/admin_screen.py', screens, admin_imports)

