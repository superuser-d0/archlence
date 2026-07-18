import re
import os

with open('main.py', 'r') as f:
    lines = f.readlines()

def get_method_lines(method_name, lines):
    start = -1
    for i, line in enumerate(lines):
        if line.startswith(f"    def {method_name}("):
            start = i
            break
    if start == -1: return [], lines
    
    end = start + 1
    while end < len(lines):
        if re.match(r'^    def ', lines[end]) or re.match(r'^class ', lines[end]) or (lines[end].strip() and not lines[end].startswith(' ') and not lines[end].startswith('#')):
            break
        end += 1
        
    extracted = lines[start:end]
    new_lines = lines[:start] + lines[end:]
    return extracted, new_lines

groups = {
    'AssetMixin': [
        'show_add_asset_dialog', '_select_asset_type', '_save_new_asset',
        'load_active_assets', 'render_active_assets', '_sell_asset',
        '_execute_sell', 'load_asset_history', 'render_asset_history'
    ],
    'DebtMixin': [
        'add_loan_to_debts', 'load_active_debts', 'render_active_debts',
        'close_debt_completely', 'pay_debt_installments'
    ],
    'CalculatorMixin': [
        'open_calculator', 'calculate_compound', 'calculate_loan', 'export_plan_to_pdf'
    ],
    'TransactionMixin': [
        'show_add_dialog', 'on_segment_active', 'open_category_menu',
        'set_category', 'save_transaction', 'load_recent_transactions'
    ]
}

os.makedirs('mixins', exist_ok=True)

for mixin_name, methods in groups.items():
    mixin_lines = []
    
    # Prepend basic imports that mixins might need
    mixin_lines.append("import os\n")
    mixin_lines.append("from kivy.clock import Clock\n")
    mixin_lines.append("from kivy.metrics import dp\n")
    mixin_lines.append("from kivymd.toast import toast\n")
    mixin_lines.append("from kivymd.uix.button import MDFlatButton, MDRaisedButton\n")
    mixin_lines.append("from kivymd.uix.dialog import MDDialog\n")
    mixin_lines.append("from kivymd.uix.textfield import MDTextField\n")
    mixin_lines.append("from kivymd.uix.boxlayout import MDBoxLayout\n")
    mixin_lines.append("from kivymd.uix.menu import MDDropdownMenu\n")
    mixin_lines.append("from kivymd.uix.segmentedcontrol import MDSegmentedControl, MDSegmentedControlItem\n")
    mixin_lines.append("from kivymd.uix.list import OneLineListItem, TwoLineAvatarIconListItem, IconLeftWidget, IconRightWidget, IRightBodyTouch, OneLineAvatarIconListItem\n")
    mixin_lines.append("from kivymd.uix.label import MDLabel\n")
    mixin_lines.append("from database.db import connect_db\n")
    mixin_lines.append("from services.transaction_service import TransactionService\n")
    mixin_lines.append("from services.asset_service import AssetService\n")
    mixin_lines.append("from ui.components import CategorySettingItem, RightButtonsContainer, BudgetListItem, LegendItem, LegendWidget\n")
    mixin_lines.append("\n\n")
    
    mixin_lines.append(f"class {mixin_name}:\n")
    
    for m in methods:
        extracted, lines = get_method_lines(m, lines)
        if extracted:
            mixin_lines.extend(extracted)
        else:
            print(f"Warning: Method {m} not found!")
            
    # Write to file
    filename = f"mixins/{mixin_name.replace('Mixin', '').lower()}_mixin.py"
    with open(filename, 'w') as f:
        f.writelines(mixin_lines)

# Inject Mixin inheritance into main.py
for i, line in enumerate(lines):
    if line.startswith("class FinoraApp("):
        # We replace "class FinoraApp(MDApp):" with multiple inheritance
        lines[i] = "class FinoraApp(MDApp, AssetMixin, DebtMixin, CalculatorMixin, TransactionMixin):\n"
        
        # Insert imports for mixins
        import_stmt = (
            "from mixins.asset_mixin import AssetMixin\n"
            "from mixins.debt_mixin import DebtMixin\n"
            "from mixins.calculator_mixin import CalculatorMixin\n"
            "from mixins.transaction_mixin import TransactionMixin\n\n"
        )
        lines.insert(i, import_stmt)
        break

with open('main.py', 'w') as f:
    f.writelines(lines)

