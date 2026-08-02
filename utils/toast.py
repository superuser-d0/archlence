import os

_ARCHLENCE_HEADLESS = os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in (
    "1", "true", "yes",
)

try:
    from kivymd.uix.snackbar import MDSnackbar
    from kivymd.uix.label import MDLabel
    from kivy.metrics import dp

    def toast(text, duration=2.5, **kwargs):
        """
        Custom high-quality toast replacing the blurry default KivyMD toast.
        Uses MDSnackbar to ensure native resolution rendering.
        """
        sb = MDSnackbar(
            MDLabel(
                text=str(text),
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
            ),
            radius=[dp(8), dp(8), dp(8), dp(8)],
            md_bg_color=(0.15, 0.15, 0.15, 0.95),
            duration=duration
        )
        sb.open()
except (ImportError, AttributeError) as exc:
    # main.py'deki "Graceful KivyMD Mocking" ile aynı sözleşme: gerçek bir
    # masaüstü ortamda bu import başarısız oluyorsa gizlenmemeli (sessiz
    # sızma). Yalnızca ARCHLENCE_HEADLESS=1 altında (birim testleri) no-op'a
    # düşülür — headless test ortamının kivymd stub'ları `kivymd.uix.snackbar`
    # sağlamıyor, bu da bu modülü içe aktaran her mixin'i import anında
    # çökertiyordu (bkz. tests/test_scenario_mixin.py, test_insights_mixin.py).
    if not _ARCHLENCE_HEADLESS:
        raise
    import warnings
    warnings.warn(f"utils.toast: MDSnackbar import failed; using no-op fallback: {exc}")

    def toast(*args, **kwargs):
        return None
