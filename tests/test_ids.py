import os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

def main():
    from kivy.lang import Builder
    from kivymd.app import MDApp
    from kivy.properties import ColorProperty, StringProperty

    class IdsApp(MDApp):
        home_circle_color = ColorProperty((0, 0, 0, 0))
        active_category_type = StringProperty("income")
        language = StringProperty("tr")
        theme_name = StringProperty("standard")

        def tr(self, text, language=None):
            return text

        def _noop(self, *args, **kwargs):
            return None

        admin_logout = apply_theme = change_home_filter = check_login = _noop
        setup_pin = _noop
        confirm_delete_all_data = contact_us = load_categories = _noop
        load_recent_transactions = on_accounts_tab_enter = _noop
        on_assets_tab_enter = open_add_account_dialog = open_calculator = _noop
        open_language_dialog = open_scenario_sandbox = refresh_asset_prices = _noop
        show_add_asset_dialog = show_add_dialog = show_balance_history_dialog = _noop
        show_budget_planner = show_budget_trend = show_data_privacy_dialog = toggle_theme = _noop
        toggle_wealth_visibility = update_category_importance = _noop

        def authentication_screen(self):
            return "pin_setup"

        def build(self):


            Builder.load_file("ui/tools.kv")
            return Builder.load_file("ui/dashboard.kv")

        def on_start(self):
            from kivy.clock import Clock
            print("IDS:", list(self.root.ids.keys()))


            Clock.schedule_once(lambda _dt: self.stop(), 0.5)

    IdsApp().run()


if __name__ == "__main__":
    main()
