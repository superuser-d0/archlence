import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Kivy headless for testing. "KIVY_WINDOW=mock" was never a real Kivy
# provider (bkz. docs/ROADMAP.md Faz 1 madde 2) — main.py artık gerçek
# pencere kurulamadığında yalnızca ARCHLENCE_HEADLESS=1 açıkça set edildiyse
# sessizce stub sınıflara düşüyor.
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
