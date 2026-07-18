import sys, os

# Setup Kivy headless for testing
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_WINDOW"] = "headless"

from main import FinoraApp
try:
    app = FinoraApp()
    # Need to load KV or build root to get root.ids
    app.build()
    app.update_metrics_and_goals()
    print("Metrics updated successfully!")
    print("Income:", app.root.ids.metric_val_income.text)
except Exception as e:
    import traceback
    traceback.print_exc()
