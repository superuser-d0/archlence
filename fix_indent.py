import sys

with open('main.py', 'r') as f:
    lines = f.readlines()

start = 552
end = 745

target = lines[start:end]
del lines[start:end]

# Find class FinoraApp(MDApp):
finora_idx = 0
for i, l in enumerate(lines):
    if l.startswith("class FinoraApp(MDApp):"):
        finora_idx = i
        break

# Insert target right after class FinoraApp
lines = lines[:finora_idx+1] + target + lines[finora_idx+1:]

with open('main.py', 'w') as f:
    f.writelines(lines)
