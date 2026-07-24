"""Para değerleri için Kivy'den bağımsız biçimlendirme yardımcıları."""


def format_try(value: float) -> str:
    """İşareti koruyarak Türkçe ayraçlarla TL tutarı döndürür."""
    sign = "-" if value < 0 else ""
    amount = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}₺{amount}"
