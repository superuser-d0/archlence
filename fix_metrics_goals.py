import sys

with open('main.py', 'r') as f:
    lines = f.readlines()

start_idx = 0
for i, l in enumerate(lines):
    if l.startswith("        if not cat_data:"):
        start_idx = i
        break

end_idx = 0
for i, l in enumerate(lines):
    if l.startswith("        anim.start(self)"):
        end_idx = i
        break

replacement = """        if self.root and 'metric_val_income' in self.root.ids:
            from kivy.clock import Clock
            from kivy.metrics import dp
            from kivy.animation import Animation

            self.root.ids.metric_val_income.text = f"{total_income:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")
            self.root.ids.metric_val_expense.text = f"{total_expense:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

            if total_income > 0:
                savings_rate = ((total_income - total_expense) / total_income) * 100
                self.root.ids.metric_val_savings.text = f"%{savings_rate:.1f}".replace(".", ",")
            else:
                self.root.ids.metric_val_savings.text = "%0,0"

            cards = [
                self.root.ids.metric_card_income,
                self.root.ids.metric_card_expense,
                self.root.ids.metric_card_savings,
                self.root.ids.metric_card_trend
            ]

            for i, card in enumerate(cards):
                card.opacity = 0
                def animate_card(dt, c=card):
                    orig_y = c.y
                    c.y = orig_y - dp(40)
                    Animation(opacity=1, y=orig_y, d=0.6, t='out_cubic').start(c)
                Clock.schedule_once(animate_card, 0.1 + (i * 0.15))
"""

lines = lines[:start_idx] + [replacement] + lines[end_idx+1:]

with open('main.py', 'w') as f:
    f.writelines(lines)

