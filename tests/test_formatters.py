"""Tutar maskeleme ve ayrıştırma testleri (Görev #7).

Para ayrıştırması sessiz hataların en pahalı olduğu yer: maskeleme girdiyi
`"250.000"` hâline getiriyor ve bunu `float()`'a vermek 250.0 üretir — yani
250 bin lira 250 liraya döner. Bu paket o sınıf hataları kilitler.
"""
import os
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import formatters
from utils.formatters import (
    canonical_amount_text,
    filter_amount_keystroke,
    format_amount_input,
    format_amount_value,
    parse_amount,
    parse_amount_to_float,
)


class ParseAmountTest(unittest.TestCase):
    """Görev tarifindeki (a) maddesi ve yakın komşuları."""

    def test_turkish_format(self):
        self.assertAlmostEqual(parse_amount("1.500,50"), 1500.50, places=2)

    def test_english_format(self):
        self.assertAlmostEqual(parse_amount("15,000.00"), 15000.00, places=2)

    def test_garbage_raises(self):
        for bad in ("abc", "12abc", "₺₺", "--"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    parse_amount(bad)

    def test_garbage_returns_default_in_safe_variant(self):
        for bad in ("abc", "", None, "12abc"):
            with self.subTest(value=bad):
                self.assertEqual(parse_amount_to_float(bad), 0.0)

    def test_safe_variant_honours_custom_default(self):
        self.assertEqual(parse_amount_to_float("abc", default=-1.0), -1.0)

    def test_grouped_text_is_not_read_as_decimal(self):
        """Maskelemenin ürettiği metin doğru okunmalı — kritik vaka.

        float("250.000") 250.0 verir; burada 250000.0 beklenir.
        """
        self.assertAlmostEqual(parse_amount("250.000"), 250000.0, places=2)
        self.assertAlmostEqual(parse_amount("1.500"), 1500.0, places=2)
        self.assertAlmostEqual(parse_amount("1.234.567"), 1234567.0, places=2)

    def test_non_grouped_dot_is_decimal(self):
        """Üçerli gruplama kalıbına UYMAYAN nokta ondalıktır."""
        self.assertAlmostEqual(parse_amount("250.5"), 250.5, places=2)
        self.assertAlmostEqual(parse_amount("250.55"), 250.55, places=2)

    def test_plain_integer_and_decimal(self):
        self.assertAlmostEqual(parse_amount("1500"), 1500.0, places=2)
        self.assertAlmostEqual(parse_amount("0,99"), 0.99, places=2)

    def test_currency_symbol_and_spaces_tolerated(self):
        self.assertAlmostEqual(parse_amount(" ₺1.500,50 "), 1500.50, places=2)

    def test_negative_is_rejected(self):
        """Yön Gelir/Gider seçimiyle belirlenir; eksi tutar kabul edilmez."""
        with self.assertRaises(ValueError):
            parse_amount("-500")

    def test_empty_is_rejected(self):
        for blank in ("", "   ", None):
            with self.subTest(value=blank):
                with self.assertRaises(ValueError):
                    parse_amount(blank)


class LiveMaskTest(unittest.TestCase):
    """Canlı biçimlendirme (BÖLÜM 1)."""

    def test_thousands_separator_inserted(self):
        self.assertEqual(format_amount_input("250000"), "250.000")
        self.assertEqual(format_amount_input("1500"), "1.500")
        self.assertEqual(format_amount_input("1234567"), "1.234.567")

    def test_short_numbers_untouched(self):
        for value in ("1", "15", "150"):
            with self.subTest(value=value):
                self.assertEqual(format_amount_input(value), value)

    def test_decimal_separator_is_preserved_while_typing(self):
        """'1500,' yazarken virgül silinmemeli, yoksa kuruş yazılamaz."""
        self.assertEqual(format_amount_input("1500,"), "1.500,")
        self.assertEqual(format_amount_input("1500,5"), "1.500,5")
        self.assertEqual(format_amount_input("1500,50"), "1.500,50")

    def test_decimals_clamped_to_two(self):
        self.assertEqual(format_amount_input("15,9999"), "15,99")

    def test_leading_zeros_collapsed(self):
        self.assertEqual(format_amount_input("000123"), "123")
        self.assertEqual(format_amount_input("0"), "0")

    def test_bare_decimal_gets_zero_prefix(self):
        self.assertEqual(format_amount_input(",5"), "0,5")

    def test_empty_stays_empty(self):
        self.assertEqual(format_amount_input(""), "")

    def test_mask_is_idempotent(self):
        """Maskelenmiş metni yeniden maskelemek değeri bozmamalı."""
        for value in ("250000", "1500,5", "1234567", "0,99"):
            once = format_amount_input(value)
            with self.subTest(value=value):
                self.assertEqual(format_amount_input(once), once)


class CanonicalValueTest(unittest.TestCase):
    """Maskelenmiş metnin kanonik (ayrıştırmaya hazır) hâli."""

    def test_canonical_strips_grouping(self):
        self.assertEqual(canonical_amount_text("250.000"), "250000")
        self.assertEqual(canonical_amount_text("1.500,50"), "1500.50")

    def test_canonical_parses_back_to_same_number(self):
        for typed, expected in (
            ("250000", 250000.0),
            ("1500,5", 1500.5),
            ("1234567,89", 1234567.89),
            ("0,99", 0.99),
        ):
            with self.subTest(typed=typed):
                displayed = format_amount_input(typed)
                canonical = canonical_amount_text(displayed)
                self.assertAlmostEqual(float(canonical), expected, places=2)

    def test_canonical_of_empty_is_empty(self):
        self.assertEqual(canonical_amount_text(""), "")


class FormatAmountValueTest(unittest.TestCase):
    """Programatik atama yolu — 100x hatanın önlendiği yer."""

    def test_value_formatted_with_turkish_separators(self):
        self.assertEqual(format_amount_value(1500.0), "1.500,00")
        self.assertEqual(format_amount_value(250000), "250.000,00")
        self.assertEqual(format_amount_value(149.99), "149,99")

    def test_round_trip_through_mask_is_stable(self):
        """set_amount ile yazılan metin maskelemeden geçince değişmemeli."""
        for value in (1500.0, 1500.5, 250000, 149.99, 0, 1234567.89):
            with self.subTest(value=value):
                displayed = format_amount_value(value)
                self.assertEqual(format_amount_input(displayed), displayed)
                self.assertAlmostEqual(
                    parse_amount(displayed), float(value), places=2)

    def test_raw_float_string_would_have_been_misread(self):
        """Neden set_amount şart: ham f"{v:.2f}" metni maskede 100x şişiyor.

        Bu test doğru davranışı değil, KAÇINILAN tuzağı belgeliyor.
        """
        self.assertEqual(format_amount_input("1500.00"), "150.000")
        self.assertEqual(format_amount_value(1500.00), "1.500,00")

    def test_negative_value_rejected(self):
        with self.assertRaises(ValueError):
            format_amount_value(-5)


class _FakeField:
    """TextInput'un maskeleme için kullandığı yüzeyi taklit eder.

    Gerçek MDTextField, pencere ağacına bağlı olmadan `insert_text`'i yok
    sayıyor (headless ortam kısıtı), o yüzden imleç matematiği burada
    deterministik biçimde sınanır.
    """

    def __init__(self, text=""):
        self._text = text
        self.cursor = (0, 0)
        self.input_filter = None
        self._callbacks = []

    # --- TextInput API'sinin maskelemenin dokunduğu kısmı ---
    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        # İmlece DOKUNULMAZ. Gerçek `TextInput.insert_text` de böyle davranır:
        # ÖNCE metni yazar (bu on_text'i tetikler), imleci ANCAK SONRA
        # ilerletir. Bu sıralama kritik — bkz. insert_text() aşağıda.
        self._text = value
        for callback in list(self._callbacks):
            callback(self, value)

    def bind(self, **kwargs):
        if "text" in kwargs:
            self._callbacks.append(kwargs["text"])

    def cursor_index(self):
        return self.cursor[0]

    def get_cursor_from_index(self, index):
        return (index, 0)

    # --- Kivy TextInput.insert_text'in GERÇEK sırası ---
    def insert_text(self, substring, from_undo=False):
        """filtre -> metni yaz (on_text burada) -> imleci İLERLET.

        DÜZELTME: bu sınıf eskiden imleci metinden ÖNCE
        güncelliyordu ve `type_at` docstring'i bunu "gerçek insert_text
        akışı" diye anlatıyordu. Gerçek Kivy'de sıra TAM TERSİ. Yanlış model
        yüzünden buradaki imleç testleri, üretimde sayıyı bozan bir hatayı
        (yazılan 1234567 -> alanda 1.235.674) yeşil gösteriyordu; gerçek bir
        SDL2/GL penceresinde MDTextField ile ölçülerek doğrulandı.
        """
        if self.input_filter is not None:
            substring = self.input_filter(substring, from_undo)
        if not substring:
            return
        index = self.cursor_index()
        self.text = self._text[:index] + substring + self._text[index:]
        self.cursor = (index + len(substring), 0)

    def do_backspace(self, from_undo=False, mode="bkspc"):
        index = self.cursor_index()
        if index == 0:
            return
        self.text = self._text[:index - 1] + self._text[index:]
        self.cursor = (index - 1, 0)

    # --- Test yardımcısı: imleci konumlandırıp gerçek giriş yolundan yazar ---
    def type_at(self, chars, index=None):
        if index is not None:
            self.cursor = (index, 0)
        else:
            self.cursor = (len(self._text), 0)
        for char in chars:
            self.insert_text(char)


class CursorPositionTest(unittest.TestCase):
    """İmlecin biçimlendirme sonrası sona zıplamaması (BÖLÜM 1.1)."""

    def _field(self, text=""):
        from utils.formatters import attach_amount_mask
        return attach_amount_mask(_FakeField(text))

    def test_typing_at_end_keeps_cursor_at_end(self):
        field = self._field()
        field.type_at("250000")
        self.assertEqual(field.text, "250.000")
        self.assertEqual(field.cursor_index(), len(field.text))

    def test_inserting_in_middle_keeps_cursor_after_typed_digit(self):
        """'1.234' içinde 1'den sonra 9 yazınca imleç 9'un ardında kalmalı."""
        field = self._field()
        field.type_at("1234")
        self.assertEqual(field.text, "1.234")

        field.type_at("9", index=1)          # "19.234"
        self.assertEqual(field.text, "19.234")
        # Anlamlı karakter sayısı: "1", "9" -> imleç 2. indekste
        self.assertEqual(field.cursor_index(), 2)

    def test_cursor_accounts_for_newly_inserted_group_separator(self):
        """Ayraç eklendiğinde imleç bir hane KAYMAMALI."""
        field = self._field()
        field.type_at("999")
        self.assertEqual(field.text, "999")
        field.type_at("9")                   # "9.999" — ayraç doğdu
        self.assertEqual(field.text, "9.999")
        self.assertEqual(field.cursor_index(), len(field.text))

    def test_canonical_value_tracked_on_every_change(self):
        from utils.formatters import read_amount
        field = self._field()
        field.type_at("250000")
        self.assertAlmostEqual(read_amount(field), 250000.0, places=2)
        field.type_at(",50")
        self.assertAlmostEqual(read_amount(field), 250000.50, places=2)

    def test_filter_is_installed_by_attach(self):
        field = self._field()
        field.type_at("12abc34")
        self.assertEqual(field.text, "1.234")

    def test_read_amount_rejects_empty_field(self):
        from utils.formatters import read_amount
        field = self._field()
        with self.assertRaises(ValueError):
            read_amount(field)

    def test_read_amount_default_shields_empty_field(self):
        from utils.formatters import read_amount
        field = self._field()
        self.assertEqual(read_amount(field, default=0.0), 0.0)


class KeystrokeFilterTest(unittest.TestCase):
    """Girdi kısıtlamaları (BÖLÜM 1.2)."""

    def test_digits_pass(self):
        self.assertEqual(filter_amount_keystroke("7", "12"), "7")

    def test_letters_and_symbols_blocked(self):
        for bad in ("a", "Z", "!", " ", "€", "/"):
            with self.subTest(char=bad):
                self.assertEqual(filter_amount_keystroke(bad, "12"), "")

    def test_signs_blocked(self):
        for sign in ("-", "+"):
            with self.subTest(sign=sign):
                self.assertEqual(filter_amount_keystroke(sign, ""), "")

    def test_dot_becomes_decimal_comma(self):
        """İngilizce alışkanlıkla yazılan '.' ondalık niyeti sayılır.

        Aksi halde maskelemenin gruplama noktalarından ayırt edilemez ve
        "1500.5" sessizce 15005 olurdu.
        """
        self.assertEqual(filter_amount_keystroke(".", "1500"), ",")

    def test_second_decimal_separator_blocked(self):
        for existing in ("1500,5", "1.500,"):
            for char in (",", "."):
                with self.subTest(existing=existing, char=char):
                    self.assertEqual(
                        filter_amount_keystroke(char, existing), "")

    def test_pasted_text_is_cleaned(self):
        """Yapıştırılan karışık metinden yalnız geçerli karakterler kalır."""
        self.assertEqual(filter_amount_keystroke("1a2b3", ""), "123")
        self.assertEqual(filter_amount_keystroke("12.50abc", ""), "12,50")

    def test_pasted_text_keeps_single_separator(self):
        self.assertEqual(filter_amount_keystroke("1.2.3", ""), "1,23")

    def test_pasted_negative_loses_only_its_sign(self):
        """"-500" yapıştırılınca 500 kalır; yön Gelir/Gider seçimiyle belirlenir.

        Tutarı tamamen düşürmek kullanıcının yazdığı sayıyı sessizce yok
        etmek olurdu; işareti düşürmek ise büyüklüğü koruyup anlamsız olan
        yönü atar. Bu davranış kasıtlıdır.
        """
        self.assertEqual(filter_amount_keystroke("-500", ""), "500")


if __name__ == "__main__":
    unittest.main()


class AmountMaskScramblingRegressionTest(unittest.TestCase):
    """Kullanıcı raporu: tutar yazarken rakamlar karışıyordu.

    İmleç bir karakter geride kalınca SONRAKİ hane yanlış konuma giriyor ve
    kullanıcı doğru rakamı yazdığı hâlde hesaba bambaşka bir tutar giriyordu.
    Bu, imleç testlerinden ayrı tutuluyor: buradaki asıl iddia "imleç şu
    indekste" değil, "yazılan sayı KORUNUYOR".
    """

    def _type(self, keys):
        from utils.formatters import attach_amount_mask
        field = attach_amount_mask(_FakeField())
        field.type_at(keys)
        return field

    def test_typed_digits_are_preserved_exactly(self):
        for keys, expected in [
            ("1234", "1.234"),
            ("12345", "12.345"),
            ("123456", "123.456"),
            ("1234567", "1.234.567"),
            ("12345678", "12.345.678"),
            ("100", "100"),
        ]:
            with self.subTest(keys=keys):
                field = self._type(keys)
                self.assertEqual(
                    field.text, expected,
                    f"'{keys}' yazıldı, alanda '{field.text}' oluştu — "
                    f"rakam sırası bozuldu.",
                )

    def test_typed_value_round_trips_through_read_amount(self):
        from utils.formatters import read_amount
        self.assertEqual(read_amount(self._type("1234567")), 1234567.0)


class AmountUpperBoundTest(unittest.TestCase):
    """Absürt tutarlar alana hiç girememeli.

    Kullanıcı raporu: çok uzun sayı girilince uygulama "sapıtıyor" —
    ekranda ₺112.955.698.541.615.249.872.910,00 gibi toplamlar çıkıyordu.
    float64 yalnız 2**53'e (~9,007e15) kadar tam sayıyı birebir taşır;
    ötesinde bakiye aritmetiği sessizce yuvarlanır. Sınır GİRDİ anında
    uygulanır, böylece mevcut kayıtlar etkilenmez.
    """

    def test_integer_part_is_capped(self):
        limit = formatters.MAX_INTEGER_DIGITS
        full = "9" * limit
        self.assertEqual(
            filter_amount_keystroke("9", full), "",
            "Tam kısım sınıra ulaştığında yeni hane kabul edilmemeli.",
        )

    def test_below_the_cap_still_accepts_digits(self):
        almost = "9" * (formatters.MAX_INTEGER_DIGITS - 1)
        self.assertEqual(filter_amount_keystroke("9", almost), "9")

    def test_cap_stays_within_float64_exact_integer_range(self):
        biggest = 10 ** formatters.MAX_INTEGER_DIGITS - 1
        self.assertLess(
            biggest, 2 ** 53,
            "Sınır, float64'ün tam sayı kesinlik aralığının içinde kalmalı.",
        )

    def test_decimals_are_unaffected_by_the_integer_cap(self):
        """Sınır yalnız TAM kısma uygulanır; kuruş yazımı engellenmemeli."""
        capped = "9" * formatters.MAX_INTEGER_DIGITS + ",5"
        self.assertEqual(filter_amount_keystroke("0", capped), "0")
