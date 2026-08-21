import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


os.environ["KIVY_NO_ARGS"] = "1"
os.environ["ARCHLENCE_HEADLESS"] = "1"

def main():
    from main import ArchlenceApp

    app = ArchlenceApp()
    app.build()
    app.update_metrics_and_goals()
    print("Metrics updated successfully!")
    print("Income:", app.root.ids.metric_val_income.text)


if __name__ == "__main__":
    main()
