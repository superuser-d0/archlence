import re

with open('main.py', 'r') as f:
    lines = f.readlines()

def remove_class(class_name, lines):
    start = -1
    for i, line in enumerate(lines):
        if line.startswith(f"class {class_name}("):
            start = i
            break
    if start == -1: return lines
    
    end = start + 1
    while end < len(lines):
        if re.match(r'^(class|def) ', lines[end]) or (lines[end].strip() and not lines[end].startswith(' ') and not lines[end].startswith('#')):
            break
        end += 1
        
    return lines[:start] + lines[end:]

to_remove = [
    "CurvedTrendChart", "DashboardChartManager", "HorizontalBarChart", "LiquidWaveWidget", "PieChart",
    "CategorySettingItem", "RightButtonsContainer", "BudgetListItem", "LegendItem", "LegendWidget",
    "AdminScreen"
]

for c in to_remove:
    lines = remove_class(c, lines)

# Add imports after the initial kivy imports
import_idx = 0
for i, line in enumerate(lines):
    if line.startswith("class FinoraApp("):
        import_idx = i
        break

new_imports = """
from ui.charts import CurvedTrendChart, HorizontalBarChart, LiquidWaveWidget, PieChart, DashboardChartManager
from ui.components import CategorySettingItem, RightButtonsContainer, BudgetListItem, LegendItem, LegendWidget
from screens.admin_screen import AdminScreen

"""

lines.insert(import_idx, new_imports)

with open('main.py', 'w') as f:
    f.writelines(lines)

