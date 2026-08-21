import os

_ARCHLENCE_HEADLESS = os.environ.get("ARCHLENCE_HEADLESS", "").strip().lower() in (
    "1", "true", "yes",
)

if _ARCHLENCE_HEADLESS:


    def toast(*args, **kwargs):
        return None
else:
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
