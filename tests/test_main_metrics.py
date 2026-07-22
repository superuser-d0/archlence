import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Kivy headless for testing
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_WINDOW"] = "mock"

def main():
    from main import FinoraApp

    app = FinoraApp()
    app.build()
    app.update_metrics_and_goals()
    print("Metrics updated successfully!")
    print("Income:", app.root.ids.metric_val_income.text)


if __name__ == "__main__":
    main()
